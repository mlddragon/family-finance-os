from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_to_json, derive_actor_context
from family_finance_os.models import ElevatedModeEvent, utc_now_iso
from family_finance_os.permissions import (
    ActionKey,
    DataScopeKey,
    PermissionDeniedError,
    PermissionEvaluation,
    PermissionEvaluator,
    action_is_mutating,
)


INACTIVITY_TIMEOUT = timedelta(minutes=15)

_request_elevated_session_id: ContextVar[Optional[str]] = ContextVar(
    "elevated_session_id",
    default=None,
)


class ElevatedContext(str, Enum):
    SYSTEM_ADMINISTRATION = "system_administration"
    FINANCIAL_GOVERNANCE = "financial_governance"


class ElevatedModeEventType(str, Enum):
    ENTERED = "entered"
    EXITED = "exited"
    EXPIRED = "expired"


SYSTEM_ADMINISTRATION_PURPOSE_CODES = frozenset(
    {
        "user_group_permission_management",
        "source_or_system_settings",
        "maintenance_health_review",
        "runtime_troubleshooting",
    }
)

FINANCIAL_GOVERNANCE_PURPOSE_CODES = frozenset(
    {
        "approval_rule_change",
        "governance_setting_change",
        "threshold_risk_rule_review",
        "monthly_close_governance_review",
    }
)

PURPOSE_CODES_REQUIRING_NOTE = frozenset({"approval_rule_change"})

PURPOSE_CODES_BY_CONTEXT: dict[ElevatedContext, frozenset[str]] = {
    ElevatedContext.SYSTEM_ADMINISTRATION: SYSTEM_ADMINISTRATION_PURPOSE_CODES,
    ElevatedContext.FINANCIAL_GOVERNANCE: FINANCIAL_GOVERNANCE_PURPOSE_CODES,
}

ELEVATION_ALLOWED_ACTIONS: dict[ElevatedContext, frozenset[ActionKey]] = {
    ElevatedContext.SYSTEM_ADMINISTRATION: frozenset({ActionKey.RUNTIME_SETTINGS_MANAGE}),
    ElevatedContext.FINANCIAL_GOVERNANCE: frozenset({ActionKey.APPROVAL_RULES_CONFIGURE}),
}

CONTEXT_ENTER_REQUIREMENTS: dict[ElevatedContext, list[tuple[ActionKey, DataScopeKey]]] = {
    ElevatedContext.SYSTEM_ADMINISTRATION: [
        (ActionKey.RUNTIME_SETTINGS_MANAGE, DataScopeKey.RUNTIME_SETTINGS),
        (ActionKey.USERS_GROUPS_PERSONAS_MANAGE, DataScopeKey.USER_GROUP_PERSONA_ADMIN),
    ],
    ElevatedContext.FINANCIAL_GOVERNANCE: [
        (ActionKey.APPROVAL_RULES_CONFIGURE, DataScopeKey.APPROVAL_RULE_CONFIGURATION),
    ],
}


@dataclass(frozen=True)
class ActiveElevatedSession:
    session_id: str
    context: ElevatedContext
    purpose_code: str
    note: str
    actor: str
    actor_context: ActorContext
    correlation_id: str
    entered_at: datetime
    last_activity_at: datetime


class ElevatedModeError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ElevatedModeEnterRequest(BaseModel):
    context: ElevatedContext
    purpose_code: str = Field(min_length=1)
    note: str = ""
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None


class ElevatedModeExitRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None


class ElevatedModeTouchRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def set_request_elevated_session_id(session_id: Optional[str]) -> Token:
    return _request_elevated_session_id.set(session_id)


def reset_request_elevated_session_id(token: Token) -> None:
    _request_elevated_session_id.reset(token)


def current_elevated_session_id() -> Optional[str]:
    return _request_elevated_session_id.get()


def purpose_codes_payload() -> dict[str, list[str]]:
    return {
        ElevatedContext.SYSTEM_ADMINISTRATION.value: sorted(SYSTEM_ADMINISTRATION_PURPOSE_CODES),
        ElevatedContext.FINANCIAL_GOVERNANCE.value: sorted(FINANCIAL_GOVERNANCE_PURPOSE_CODES),
    }


def elevated_mode_metadata_payload() -> dict[str, Any]:
    return {
        "purpose_codes": purpose_codes_payload(),
        "purpose_requires_note": sorted(PURPOSE_CODES_REQUIRING_NOTE),
    }


def apply_elevated_mode_restriction(
    evaluation: PermissionEvaluation,
    action_key: ActionKey,
    elevated_session: Optional[ActiveElevatedSession],
) -> PermissionEvaluation:
    if elevated_session is None or not action_is_mutating(action_key):
        return evaluation

    allowed_actions = ELEVATION_ALLOWED_ACTIONS.get(elevated_session.context, frozenset())
    if action_key in allowed_actions and evaluation.allowed:
        return evaluation

    return PermissionEvaluation(
        allowed=False,
        suggestion_allowed=False,
        action_key=evaluation.action_key,
        data_scope_key=evaluation.data_scope_key,
        action_effect=evaluation.action_effect,
        scope_access=evaluation.scope_access,
        denied_reason="elevated_mode_read_only",
    )


def serialize_active_session(session: ActiveElevatedSession) -> dict[str, Any]:
    return {
        "active": True,
        "session_id": session.session_id,
        "context": session.context.value,
        "purpose_code": session.purpose_code,
        "note": session.note,
        "actor": session.actor,
        "actor_context": session.actor_context.model_dump(exclude_none=True),
        "correlation_id": session.correlation_id,
        "entered_at": session.entered_at.isoformat(),
        "last_activity_at": session.last_activity_at.isoformat(),
        "expires_at": (session.last_activity_at + INACTIVITY_TIMEOUT).isoformat(),
    }


def inactive_status_payload() -> dict[str, Any]:
    return {"active": False, **elevated_mode_metadata_payload()}


class ElevatedModeRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, ActiveElevatedSession] = {}

    def reset(self) -> None:
        self._sessions.clear()

    def _is_expired(self, session: ActiveElevatedSession, *, now: Optional[datetime] = None) -> bool:
        reference = now or utc_now()
        return reference - session.last_activity_at > INACTIVITY_TIMEOUT

    def _append_event(
        self,
        db_session: Session,
        *,
        event_type: ElevatedModeEventType,
        elevated_context: ElevatedContext,
        purpose_code: str,
        note: str,
        session_id: str,
        correlation_id: str,
        actor_context: ActorContext,
        exit_reason: Optional[str] = None,
    ) -> ElevatedModeEvent:
        event = ElevatedModeEvent(
            event_type=event_type.value,
            actor_context_json=actor_context_to_json(actor_context),
            context=elevated_context.value,
            purpose_code=purpose_code,
            note=note,
            session_id=session_id,
            correlation_id=correlation_id,
            exit_reason=exit_reason,
            recorded_at=utc_now_iso(),
        )
        db_session.add(event)
        return event

    def _expire_session(
        self,
        db_session: Session,
        session: ActiveElevatedSession,
    ) -> None:
        self._append_event(
            db_session,
            event_type=ElevatedModeEventType.EXPIRED,
            elevated_context=session.context,
            purpose_code=session.purpose_code,
            note=session.note,
            session_id=session.session_id,
            correlation_id=session.correlation_id,
            actor_context=session.actor_context,
            exit_reason="inactivity_timeout",
        )
        del self._sessions[session.session_id]

    def get_active(
        self,
        db_session: Session,
        session_id: Optional[str],
        *,
        now: Optional[datetime] = None,
    ) -> Optional[ActiveElevatedSession]:
        if not session_id:
            return None

        session = self._sessions.get(session_id)
        if session is None:
            return None

        if self._is_expired(session, now=now):
            self._expire_session(db_session, session)
            db_session.commit()
            return None

        return session

    def _require_enter_permissions(
        self,
        db_session: Session,
        actor_context: ActorContext,
        context: ElevatedContext,
    ) -> None:
        evaluator = PermissionEvaluator(db_session)
        for action_key, data_scope_key in CONTEXT_ENTER_REQUIREMENTS[context]:
            evaluation = evaluator.evaluate(
                actor_context,
                action_key.value,
                data_scope_key.value,
            )
            if not evaluation.allowed:
                raise ElevatedModeError(
                    "elevated_mode_permission_denied",
                    (
                        f"Actor lacks permission to enter {context.value} elevated mode "
                        f"({action_key.value})."
                    ),
                    status_code=403,
                )

    def enter(
        self,
        db_session: Session,
        payload: ElevatedModeEnterRequest,
        *,
        session_id: Optional[str] = None,
        has_unsaved_edits: bool = False,
    ) -> ActiveElevatedSession:
        if has_unsaved_edits:
            raise ElevatedModeError(
                "elevated_mode_unsaved_edits",
                "Unsaved workflow edits must be saved or discarded before entering elevated mode.",
                status_code=409,
            )

        resolved_context = derive_actor_context(payload.actor, payload.actor_context)
        valid_purpose_codes = PURPOSE_CODES_BY_CONTEXT[payload.context]
        if payload.purpose_code not in valid_purpose_codes:
            raise ElevatedModeError(
                "invalid_purpose_code",
                f"Purpose code {payload.purpose_code!r} is not valid for {payload.context.value}.",
                status_code=422,
            )

        resolved_note = payload.note.strip()
        if payload.purpose_code in PURPOSE_CODES_REQUIRING_NOTE and not resolved_note:
            raise ElevatedModeError(
                "elevated_mode_note_required",
                f"Purpose {payload.purpose_code!r} requires a note.",
                status_code=422,
            )

        self._require_enter_permissions(db_session, resolved_context, payload.context)

        resolved_session_id = session_id or str(uuid4())
        existing = self.get_active(db_session, resolved_session_id)
        if existing is not None:
            raise ElevatedModeError(
                "elevated_mode_already_active",
                "An elevated mode session is already active. Exit before entering again.",
                status_code=409,
            )

        correlation_id = str(uuid4())
        now = utc_now()
        active = ActiveElevatedSession(
            session_id=resolved_session_id,
            context=payload.context,
            purpose_code=payload.purpose_code,
            note=resolved_note,
            actor=payload.actor,
            actor_context=resolved_context,
            correlation_id=correlation_id,
            entered_at=now,
            last_activity_at=now,
        )
        self._sessions[resolved_session_id] = active
        self._append_event(
            db_session,
            event_type=ElevatedModeEventType.ENTERED,
            elevated_context=payload.context,
            purpose_code=payload.purpose_code,
            note=resolved_note,
            session_id=resolved_session_id,
            correlation_id=correlation_id,
            actor_context=resolved_context,
        )
        db_session.commit()
        return active

    def exit(
        self,
        db_session: Session,
        session_id: str,
        payload: ElevatedModeExitRequest,
    ) -> None:
        session = self.get_active(db_session, session_id)
        if session is None:
            raise ElevatedModeError(
                "elevated_mode_not_active",
                "No active elevated mode session was found for this session id.",
                status_code=404,
            )

        actor_context = derive_actor_context(payload.actor, payload.actor_context)
        self._append_event(
            db_session,
            event_type=ElevatedModeEventType.EXITED,
            elevated_context=session.context,
            purpose_code=session.purpose_code,
            note=session.note,
            session_id=session.session_id,
            correlation_id=session.correlation_id,
            actor_context=actor_context,
            exit_reason="manual_exit",
        )
        del self._sessions[session_id]
        db_session.commit()

    def touch(
        self,
        db_session: Session,
        session_id: str,
        payload: ElevatedModeTouchRequest,
    ) -> ActiveElevatedSession:
        session = self.get_active(db_session, session_id)
        if session is None:
            raise ElevatedModeError(
                "elevated_mode_not_active",
                "No active elevated mode session was found for this session id.",
                status_code=404,
            )

        derive_actor_context(payload.actor, payload.actor_context)
        refreshed = ActiveElevatedSession(
            session_id=session.session_id,
            context=session.context,
            purpose_code=session.purpose_code,
            note=session.note,
            actor=session.actor,
            actor_context=session.actor_context,
            correlation_id=session.correlation_id,
            entered_at=session.entered_at,
            last_activity_at=utc_now(),
        )
        self._sessions[session_id] = refreshed
        return refreshed

    def status(
        self,
        db_session: Session,
        session_id: Optional[str],
    ) -> dict[str, Any]:
        active = self.get_active(db_session, session_id)
        if active is None:
            return inactive_status_payload()
        return {
            **serialize_active_session(active),
            **elevated_mode_metadata_payload(),
        }


_registry: Optional[ElevatedModeRegistry] = None


def get_elevated_mode_registry() -> ElevatedModeRegistry:
    global _registry
    if _registry is None:
        _registry = ElevatedModeRegistry()
    return _registry


def reset_elevated_mode_registry() -> ElevatedModeRegistry:
    global _registry
    _registry = ElevatedModeRegistry()
    return _registry


def elevated_mode_http_error(exc: ElevatedModeError) -> dict[str, Any]:
    return {"code": exc.code, "message": exc.message}
