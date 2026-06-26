from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_from_json, actor_context_to_json, derive_actor_context
from family_finance_os.decision_events import (
    DECISION_TYPE_FIELDS,
    HIGH_IMPACT_FIELDS,
    DecisionEventRequest,
    create_decision_event,
    derive_decision_state,
    _normalize_value,
)
from family_finance_os.models import (
    ApprovalRequest,
    ApprovalRequestEvent,
    CanonicalTransaction,
    Setting,
    utc_now_iso,
)
from family_finance_os.settings_service import _load_value


APPROVAL_MODE_DOMAIN = "approval"
APPROVAL_MODE_SETTING_KEY = "approval.approval_mode_enabled"
HIGH_VALUE_THRESHOLD_SETTING_KEY = "approval.high_value_threshold"
DEFAULT_HIGH_VALUE_THRESHOLD = Decimal("500")
EXPIRATION_DAYS = 14

PENDING_STATUS = "pending"
TERMINAL_STATUSES = frozenset({"approved", "rejected", "cancelled", "expired"})

APPROVAL_EVENT_TYPES = frozenset(
    {"proposed", "approved", "rejected", "cancelled", "expired", "superseded", "applied"}
)


class ApprovalServiceError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ApprovalRequestCreate(BaseModel):
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    action_key: str = Field(min_length=1)
    decision_type: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    proposed_value: Any
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    policy_trigger: str = Field(min_length=1)
    notes: Optional[str] = None
    source_suggestion_id: Optional[str] = None
    suggestion_source: str = "user"


class ApprovalActionRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    notes: Optional[str] = None


def _load_setting(session: Session, domain: str, setting_key: str, default: Any) -> Any:
    record = session.scalar(
        select(Setting).where(
            Setting.domain == domain,
            Setting.setting_key == setting_key,
        )
    )
    if record is None:
        return default
    return _load_value(record.value_json)


def is_approval_mode_enabled(session: Session) -> bool:
    return bool(
        _load_setting(
            session,
            APPROVAL_MODE_DOMAIN,
            APPROVAL_MODE_SETTING_KEY,
            False,
        )
    )


def get_high_value_threshold(session: Session) -> Decimal:
    raw_value = _load_setting(
        session,
        APPROVAL_MODE_DOMAIN,
        HIGH_VALUE_THRESHOLD_SETTING_KEY,
        DEFAULT_HIGH_VALUE_THRESHOLD,
    )
    try:
        return Decimal(str(raw_value))
    except Exception as exc:
        raise ApprovalServiceError(
            "invalid_high_value_threshold",
            "High-value threshold setting must be numeric.",
        ) from exc


def require_approval_mode(session: Session) -> None:
    if not is_approval_mode_enabled(session):
        raise ApprovalServiceError(
            "approval_mode_disabled",
            "Approval mode is disabled.",
            status_code=409,
        )


def _expires_at_iso(from_timestamp: Optional[str] = None) -> str:
    base = datetime.fromisoformat(from_timestamp or utc_now_iso())
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return (base + timedelta(days=EXPIRATION_DAYS)).isoformat()


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _transaction_amount_magnitude(canonical: CanonicalTransaction) -> Decimal:
    return abs(Decimal(canonical.amount))


def high_value_trigger_applies(session: Session, canonical: CanonicalTransaction) -> bool:
    threshold = get_high_value_threshold(session)
    return _transaction_amount_magnitude(canonical) >= threshold


def high_impact_trigger_applies(field_name: str) -> bool:
    return field_name in HIGH_IMPACT_FIELDS


def resolve_approval_trigger(
    session: Session,
    canonical: CanonicalTransaction,
    field_name: str,
) -> Optional[str]:
    if high_value_trigger_applies(session, canonical):
        return "high_value"
    if high_impact_trigger_applies(field_name):
        return "high_impact_field"
    return None


def review_requires_approval(
    session: Session,
    *,
    canonical: CanonicalTransaction,
    field_name: str,
    direct_authority: bool,
) -> tuple[bool, Optional[str]]:
    if not is_approval_mode_enabled(session):
        return False, None

    if not direct_authority:
        return True, "lacking_authority"

    trigger = resolve_approval_trigger(session, canonical, field_name)
    if trigger is not None:
        return True, trigger

    return False, None


def _pending_request_for_target(
    session: Session,
    *,
    target_type: str,
    target_id: str,
    action_key: str,
    field_name: str,
) -> Optional[ApprovalRequest]:
    return session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.target_type == target_type,
            ApprovalRequest.target_id == target_id,
            ApprovalRequest.action_key == action_key,
            ApprovalRequest.field_name == field_name,
            ApprovalRequest.status == PENDING_STATUS,
        )
    )


def _append_approval_event(
    session: Session,
    *,
    approval_request: ApprovalRequest,
    event_type: str,
    actor: str,
    actor_context: Optional[ActorContext] = None,
    notes: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> ApprovalRequestEvent:
    if event_type not in APPROVAL_EVENT_TYPES:
        raise ApprovalServiceError(
            "approval_event_type_not_allowed",
            f"{event_type} is not an allowed approval request event type.",
        )

    event = ApprovalRequestEvent(
        approval_request_id=approval_request.id,
        event_type=event_type,
        actor=actor,
        actor_context_json=actor_context_to_json(derive_actor_context(actor, actor_context)),
        notes=notes.strip() if notes else None,
        metadata_json=json.dumps(metadata, sort_keys=True) if metadata is not None else None,
    )
    session.add(event)
    return event


def _validate_decision_request_fields(request: ApprovalRequestCreate) -> None:
    if request.target_type != "canonical_transaction":
        raise ApprovalServiceError(
            "target_type_not_allowed",
            "Approval requests must attach to canonical transactions in v1.",
        )
    if request.decision_type not in DECISION_TYPE_FIELDS:
        raise ApprovalServiceError(
            "decision_type_not_allowed",
            f"{request.decision_type} is not allowed in v1.",
        )
    expected_field = DECISION_TYPE_FIELDS[request.decision_type]
    if request.field_name != expected_field:
        raise ApprovalServiceError(
            "field_decision_type_mismatch",
            f"{request.decision_type} must write {expected_field}.",
        )


def _derive_previous_value(
    session: Session,
    canonical: CanonicalTransaction,
    field_name: str,
) -> Optional[str]:
    current_state = derive_decision_state(session, canonical)
    previous_key = (
        "category_key_current"
        if field_name == "category"
        else f"{field_name}_current"
        if field_name == "subcategory"
        else field_name
    )
    previous_public_value = current_state.get(previous_key)
    if previous_public_value is None:
        return None
    return _normalize_value(field_name, previous_public_value, session=session)


def expire_stale_approval_requests(session: Session) -> list[ApprovalRequest]:
    now = _parse_timestamp(utc_now_iso())
    pending = session.scalars(
        select(ApprovalRequest).where(ApprovalRequest.status == PENDING_STATUS)
    ).all()
    expired: list[ApprovalRequest] = []
    for request in pending:
        if _parse_timestamp(request.expires_at) > now:
            continue
        request.status = "expired"
        _append_approval_event(
            session,
            approval_request=request,
            event_type="expired",
            actor="system",
            notes="Approval request expired after 14 days.",
        )
        expired.append(request)
    return expired


def serialize_approval_request(request: ApprovalRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "target_type": request.target_type,
        "target_id": request.target_id,
        "action_key": request.action_key,
        "decision_type": request.decision_type,
        "field_name": request.field_name,
        "previous_value": request.previous_value,
        "proposed_value": request.proposed_value,
        "status": request.status,
        "proposer_actor": request.proposer_actor,
        "proposer_actor_context": actor_context_from_json(request.proposer_actor_context_json),
        "policy_trigger": request.policy_trigger,
        "expires_at": request.expires_at,
        "source_suggestion_id": request.source_suggestion_id,
        "notes": request.notes,
        "applied_decision_event_id": request.applied_decision_event_id,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


def create_approval_request(
    session: Session,
    request: ApprovalRequestCreate,
) -> dict[str, Any]:
    require_approval_mode(session)
    _validate_decision_request_fields(request)

    canonical = session.get(CanonicalTransaction, request.target_id)
    if canonical is None:
        raise ApprovalServiceError(
            "target_not_found",
            "Canonical transaction not found.",
            status_code=404,
        )

    existing_pending = _pending_request_for_target(
        session,
        target_type=request.target_type,
        target_id=request.target_id,
        action_key=request.action_key,
        field_name=request.field_name,
    )
    if existing_pending is not None:
        raise ApprovalServiceError(
            "pending_approval_request_exists",
            "Only one pending approval request is allowed per target, action, and field.",
            status_code=409,
        )

    proposed_value = _normalize_value(request.field_name, request.proposed_value, session=session)
    previous_value = _derive_previous_value(session, canonical, request.field_name)
    if proposed_value == previous_value:
        raise ApprovalServiceError(
            "no_effect_approval_request",
            "The proposed value already matches the current reviewed state.",
            status_code=409,
        )

    actor_context = derive_actor_context(request.actor, request.actor_context)
    approval_request = ApprovalRequest(
        target_type=request.target_type,
        target_id=request.target_id,
        action_key=request.action_key,
        decision_type=request.decision_type,
        field_name=request.field_name,
        previous_value=previous_value,
        proposed_value=proposed_value,
        status=PENDING_STATUS,
        proposer_actor=request.actor,
        proposer_actor_context_json=actor_context_to_json(actor_context),
        policy_trigger=request.policy_trigger,
        expires_at=_expires_at_iso(),
        source_suggestion_id=request.source_suggestion_id,
        notes=request.notes.strip() if request.notes else None,
    )
    session.add(approval_request)
    session.flush()
    _append_approval_event(
        session,
        approval_request=approval_request,
        event_type="proposed",
        actor=request.actor,
        actor_context=actor_context,
        notes=request.notes,
        metadata={"policy_trigger": request.policy_trigger},
    )
    session.commit()
    session.refresh(approval_request)
    return {"approval_request": serialize_approval_request(approval_request)}


def list_approval_requests(
    session: Session,
    *,
    status: Optional[str] = None,
    target_id: Optional[str] = None,
) -> dict[str, Any]:
    expire_stale_approval_requests(session)
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at, ApprovalRequest.id)
    if status is not None:
        query = query.where(ApprovalRequest.status == status)
    if target_id is not None:
        query = query.where(ApprovalRequest.target_id == target_id)
    requests = session.scalars(query).all()
    session.commit()
    return {
        "approval_mode_enabled": is_approval_mode_enabled(session),
        "approval_requests": [serialize_approval_request(item) for item in requests],
    }


def _get_pending_request(session: Session, request_id: str) -> ApprovalRequest:
    expire_stale_approval_requests(session)
    approval_request = session.get(ApprovalRequest, request_id)
    if approval_request is None:
        raise ApprovalServiceError(
            "approval_request_not_found",
            "Approval request not found.",
            status_code=404,
        )
    if approval_request.status != PENDING_STATUS:
        raise ApprovalServiceError(
            "approval_request_not_pending",
            f"Approval request is already {approval_request.status}.",
            status_code=409,
        )
    if _parse_timestamp(approval_request.expires_at) <= _parse_timestamp(utc_now_iso()):
        approval_request.status = "expired"
        _append_approval_event(
            session,
            approval_request=approval_request,
            event_type="expired",
            actor="system",
            notes="Approval request expired after 14 days.",
        )
        session.commit()
        raise ApprovalServiceError(
            "approval_request_expired",
            "Approval request expired and must be proposed again.",
            status_code=409,
        )
    return approval_request


def _ensure_not_proposer(approval_request: ApprovalRequest, actor: str) -> None:
    if approval_request.proposer_actor == actor:
        raise ApprovalServiceError(
            "proposer_cannot_approve",
            "The proposer cannot approve their own approval request.",
            status_code=403,
        )


def approve_approval_request(
    session: Session,
    request_id: str,
    action: ApprovalActionRequest,
) -> dict[str, Any]:
    require_approval_mode(session)
    approval_request = _get_pending_request(session, request_id)
    _ensure_not_proposer(approval_request, action.actor)

    canonical = session.get(CanonicalTransaction, approval_request.target_id)
    if canonical is None:
        raise ApprovalServiceError(
            "target_not_found",
            "Canonical transaction not found.",
            status_code=404,
        )

    actor_context = derive_actor_context(action.actor, action.actor_context)
    decision_payload = DecisionEventRequest(
        target_type=approval_request.target_type,
        target_id=approval_request.target_id,
        decision_type=approval_request.decision_type,
        field_name=approval_request.field_name,
        proposed_value=approval_request.proposed_value,
        approved_value=approval_request.proposed_value,
        actor=action.actor,
        actor_context=actor_context,
        notes=action.notes or approval_request.notes,
        suggestion_source="user",
        explicit_user_action=True,
    )
    decision_result = create_decision_event(session, decision_payload)
    approval_request.status = "approved"
    approval_request.applied_decision_event_id = decision_result["event"]["id"]
    _append_approval_event(
        session,
        approval_request=approval_request,
        event_type="approved",
        actor=action.actor,
        actor_context=actor_context,
        notes=action.notes,
    )
    _append_approval_event(
        session,
        approval_request=approval_request,
        event_type="applied",
        actor=action.actor,
        actor_context=actor_context,
        notes=action.notes,
        metadata={"decision_event_id": decision_result["event"]["id"]},
    )
    session.commit()
    session.refresh(approval_request)
    return {
        "approval_request": serialize_approval_request(approval_request),
        "decision": decision_result,
    }


def reject_approval_request(
    session: Session,
    request_id: str,
    action: ApprovalActionRequest,
) -> dict[str, Any]:
    require_approval_mode(session)
    approval_request = _get_pending_request(session, request_id)
    _ensure_not_proposer(approval_request, action.actor)

    actor_context = derive_actor_context(action.actor, action.actor_context)
    approval_request.status = "rejected"
    _append_approval_event(
        session,
        approval_request=approval_request,
        event_type="rejected",
        actor=action.actor,
        actor_context=actor_context,
        notes=action.notes,
    )
    session.commit()
    session.refresh(approval_request)
    return {"approval_request": serialize_approval_request(approval_request)}


def cancel_approval_request(
    session: Session,
    request_id: str,
    action: ApprovalActionRequest,
) -> dict[str, Any]:
    require_approval_mode(session)
    approval_request = _get_pending_request(session, request_id)
    if approval_request.proposer_actor != action.actor:
        raise ApprovalServiceError(
            "only_proposer_can_cancel",
            "Only the proposer can cancel a pending approval request.",
            status_code=403,
        )

    actor_context = derive_actor_context(action.actor, action.actor_context)
    approval_request.status = "cancelled"
    _append_approval_event(
        session,
        approval_request=approval_request,
        event_type="cancelled",
        actor=action.actor,
        actor_context=actor_context,
        notes=action.notes,
    )
    session.commit()
    session.refresh(approval_request)
    return {"approval_request": serialize_approval_request(approval_request)}
