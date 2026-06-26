from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_from_json, actor_context_to_json, derive_actor_context
from family_finance_os.approvals import (
    ApprovalRequestCreate,
    ApprovalServiceError,
    create_approval_request,
    is_approval_mode_enabled,
    review_requires_approval,
    serialize_approval_request,
)
from family_finance_os.decision_events import (
    DECISION_TYPE_FIELDS,
    DecisionEventError,
    DecisionEventRequest,
    create_decision_event,
    derive_decision_state,
    _normalize_value,
)
from family_finance_os.models import CanonicalTransaction, Suggestion, SuggestionEvent
from family_finance_os.permissions import (
    ActionKey,
    DataScopeKey,
    PermissionDeniedError,
    PermissionEvaluator,
)


ACTIVE_STATUS = "active"
TERMINAL_SUGGESTION_STATUSES = frozenset(
    {"accepted_direct", "converted_to_approval_request", "dismissed", "stale", "superseded"}
)

SUGGESTION_EVENT_TYPES = frozenset(
    {"created", "dismissed", "accepted_direct", "converted_to_approval_request", "stale", "superseded"}
)


class SuggestionServiceError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class SuggestionCreate(BaseModel):
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    action_key: str = Field(min_length=1)
    decision_type: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    proposed_value: Any
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    suggestion_source: str = "user"
    notes: Optional[str] = None


class SuggestionActionRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    notes: Optional[str] = None
    explicit_user_action: bool = True


def _validate_suggestion_fields(request: SuggestionCreate) -> None:
    if request.target_type != "canonical_transaction":
        raise SuggestionServiceError(
            "target_type_not_allowed",
            "Suggestions must attach to canonical transactions in v1.",
        )
    if request.decision_type not in DECISION_TYPE_FIELDS:
        raise SuggestionServiceError(
            "decision_type_not_allowed",
            f"{request.decision_type} is not allowed in v1.",
        )
    expected_field = DECISION_TYPE_FIELDS[request.decision_type]
    if request.field_name != expected_field:
        raise SuggestionServiceError(
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


def _append_suggestion_event(
    session: Session,
    *,
    suggestion: Suggestion,
    event_type: str,
    actor: str,
    actor_context: Optional[ActorContext] = None,
    notes: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> SuggestionEvent:
    if event_type not in SUGGESTION_EVENT_TYPES:
        raise SuggestionServiceError(
            "suggestion_event_type_not_allowed",
            f"{event_type} is not an allowed suggestion event type.",
        )

    event = SuggestionEvent(
        suggestion_id=suggestion.id,
        event_type=event_type,
        actor=actor,
        actor_context_json=actor_context_to_json(derive_actor_context(actor, actor_context)),
        notes=notes.strip() if notes else None,
        metadata_json=json.dumps(metadata, sort_keys=True) if metadata is not None else None,
    )
    session.add(event)
    return event


def serialize_suggestion(suggestion: Suggestion) -> dict[str, Any]:
    return {
        "id": suggestion.id,
        "target_type": suggestion.target_type,
        "target_id": suggestion.target_id,
        "action_key": suggestion.action_key,
        "decision_type": suggestion.decision_type,
        "field_name": suggestion.field_name,
        "previous_value": suggestion.previous_value,
        "proposed_value": suggestion.proposed_value,
        "status": suggestion.status,
        "proposer_actor": suggestion.proposer_actor,
        "proposer_actor_context": actor_context_from_json(suggestion.proposer_actor_context_json),
        "suggestion_source": suggestion.suggestion_source,
        "notes": suggestion.notes,
        "decision_event_id": suggestion.decision_event_id,
        "approval_request_id": suggestion.approval_request_id,
        "created_at": suggestion.created_at,
        "updated_at": suggestion.updated_at,
    }


def _get_active_suggestion(session: Session, suggestion_id: str) -> Suggestion:
    suggestion = session.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise SuggestionServiceError(
            "suggestion_not_found",
            "Suggestion not found.",
            status_code=404,
        )
    if suggestion.status != ACTIVE_STATUS:
        raise SuggestionServiceError(
            "suggestion_not_active",
            f"Suggestion is already {suggestion.status}.",
            status_code=409,
        )
    return suggestion


def create_suggestion(session: Session, request: SuggestionCreate) -> dict[str, Any]:
    _validate_suggestion_fields(request)

    canonical = session.get(CanonicalTransaction, request.target_id)
    if canonical is None:
        raise SuggestionServiceError(
            "target_not_found",
            "Canonical transaction not found.",
            status_code=404,
        )

    proposed_value = _normalize_value(request.field_name, request.proposed_value, session=session)
    previous_value = _derive_previous_value(session, canonical, request.field_name)
    if proposed_value == previous_value:
        raise SuggestionServiceError(
            "no_effect_suggestion",
            "The proposed value already matches the current reviewed state.",
            status_code=409,
        )

    actor_context = derive_actor_context(request.actor, request.actor_context)
    suggestion = Suggestion(
        target_type=request.target_type,
        target_id=request.target_id,
        action_key=request.action_key,
        decision_type=request.decision_type,
        field_name=request.field_name,
        previous_value=previous_value,
        proposed_value=proposed_value,
        status=ACTIVE_STATUS,
        proposer_actor=request.actor,
        proposer_actor_context_json=actor_context_to_json(actor_context),
        suggestion_source=request.suggestion_source,
        notes=request.notes.strip() if request.notes else None,
    )
    session.add(suggestion)
    session.flush()
    _append_suggestion_event(
        session,
        suggestion=suggestion,
        event_type="created",
        actor=request.actor,
        actor_context=actor_context,
        notes=request.notes,
    )
    session.commit()
    session.refresh(suggestion)
    return {"suggestion": serialize_suggestion(suggestion)}


def list_suggestions(
    session: Session,
    *,
    status: Optional[str] = None,
    target_id: Optional[str] = None,
) -> dict[str, Any]:
    query = select(Suggestion).order_by(Suggestion.created_at, Suggestion.id)
    if status is not None:
        query = query.where(Suggestion.status == status)
    if target_id is not None:
        query = query.where(Suggestion.target_id == target_id)
    suggestions = session.scalars(query).all()
    return {
        "approval_mode_enabled": is_approval_mode_enabled(session),
        "suggestions": [serialize_suggestion(item) for item in suggestions],
    }


def dismiss_suggestion(
    session: Session,
    suggestion_id: str,
    action: SuggestionActionRequest,
) -> dict[str, Any]:
    suggestion = _get_active_suggestion(session, suggestion_id)
    actor_context = derive_actor_context(action.actor, action.actor_context)
    suggestion.status = "dismissed"
    _append_suggestion_event(
        session,
        suggestion=suggestion,
        event_type="dismissed",
        actor=action.actor,
        actor_context=actor_context,
        notes=action.notes,
    )
    session.commit()
    session.refresh(suggestion)
    return {"suggestion": serialize_suggestion(suggestion)}


def _decision_request_from_suggestion(
    suggestion: Suggestion,
    *,
    actor: str,
    actor_context: Optional[ActorContext],
    notes: Optional[str],
    explicit_user_action: bool,
) -> DecisionEventRequest:
    return DecisionEventRequest(
        target_type=suggestion.target_type,
        target_id=suggestion.target_id,
        decision_type=suggestion.decision_type,
        field_name=suggestion.field_name,
        proposed_value=suggestion.proposed_value,
        approved_value=suggestion.proposed_value,
        actor=actor,
        actor_context=actor_context,
        notes=notes or suggestion.notes,
        suggestion_source=suggestion.suggestion_source,
        explicit_user_action=explicit_user_action,
    )


def _approval_request_from_suggestion(
    suggestion: Suggestion,
    *,
    actor: str,
    actor_context: Optional[ActorContext],
    policy_trigger: str,
    notes: Optional[str],
) -> ApprovalRequestCreate:
    return ApprovalRequestCreate(
        target_type=suggestion.target_type,
        target_id=suggestion.target_id,
        action_key=suggestion.action_key,
        decision_type=suggestion.decision_type,
        field_name=suggestion.field_name,
        proposed_value=suggestion.proposed_value,
        actor=actor,
        actor_context=actor_context,
        policy_trigger=policy_trigger,
        notes=notes or suggestion.notes,
        source_suggestion_id=suggestion.id,
        suggestion_source=suggestion.suggestion_source,
    )


def convert_suggestion_to_approval(
    session: Session,
    suggestion_id: str,
    action: SuggestionActionRequest,
) -> dict[str, Any]:
    suggestion = _get_active_suggestion(session, suggestion_id)
    actor_context = derive_actor_context(action.actor, action.actor_context)

    canonical = session.get(CanonicalTransaction, suggestion.target_id)
    if canonical is None:
        raise SuggestionServiceError(
            "target_not_found",
            "Canonical transaction not found.",
            status_code=404,
        )

    evaluator = PermissionEvaluator(session)
    evaluation = evaluator.evaluate(
        actor_context,
        ActionKey.REVIEW_DECIDE.value,
        DataScopeKey.REVIEW_DECISIONS.value,
    )
    requires_approval, trigger = review_requires_approval(
        session,
        canonical=canonical,
        field_name=suggestion.field_name,
        direct_authority=evaluation.allowed,
    )
    if not requires_approval:
        raise SuggestionServiceError(
            "approval_not_required",
            "This suggestion can be accepted directly without an approval request.",
            status_code=409,
        )

    approval_result = create_approval_request(
        session,
        _approval_request_from_suggestion(
            suggestion,
            actor=action.actor,
            actor_context=actor_context,
            policy_trigger=trigger or "manual_conversion",
            notes=action.notes,
        ),
    )
    approval_request = approval_result["approval_request"]
    suggestion.status = "converted_to_approval_request"
    suggestion.approval_request_id = approval_request["id"]
    _append_suggestion_event(
        session,
        suggestion=suggestion,
        event_type="converted_to_approval_request",
        actor=action.actor,
        actor_context=actor_context,
        notes=action.notes,
        metadata={"approval_request_id": approval_request["id"]},
    )
    session.commit()
    session.refresh(suggestion)
    return {
        "suggestion": serialize_suggestion(suggestion),
        "approval_request": approval_request,
    }


def accept_suggestion(
    session: Session,
    suggestion_id: str,
    action: SuggestionActionRequest,
) -> dict[str, Any]:
    if not action.explicit_user_action:
        raise SuggestionServiceError(
            "explicit_user_action_required",
            "Accepting a suggestion requires an explicit owner save action.",
        )

    suggestion = _get_active_suggestion(session, suggestion_id)
    actor_context = derive_actor_context(action.actor, action.actor_context)

    canonical = session.get(CanonicalTransaction, suggestion.target_id)
    if canonical is None:
        raise SuggestionServiceError(
            "target_not_found",
            "Canonical transaction not found.",
            status_code=404,
        )

    evaluator = PermissionEvaluator(session)
    evaluation = evaluator.evaluate(
        actor_context,
        ActionKey.REVIEW_DECIDE.value,
        DataScopeKey.REVIEW_DECISIONS.value,
    )
    if not evaluation.allowed and not evaluation.suggestion_allowed:
        raise PermissionDeniedError(
            ActionKey.REVIEW_DECIDE.value,
            DataScopeKey.REVIEW_DECISIONS.value,
            suggestion_allowed=False,
        )

    requires_approval, trigger = review_requires_approval(
        session,
        canonical=canonical,
        field_name=suggestion.field_name,
        direct_authority=evaluation.allowed,
    )
    if requires_approval:
        if not is_approval_mode_enabled(session):
            raise SuggestionServiceError(
                "direct_accept_not_allowed",
                "This suggestion must be reviewed by an eligible actor with direct authority.",
                status_code=403,
            )
        approval_result = convert_suggestion_to_approval(session, suggestion_id, action)
        return {
            "route": "approval_request",
            **approval_result,
        }

    if not evaluation.allowed:
        raise SuggestionServiceError(
            "direct_accept_not_allowed",
            "This suggestion must be reviewed by an eligible actor with direct authority.",
            status_code=403,
        )

    decision_result = create_decision_event(
        session,
        _decision_request_from_suggestion(
            suggestion,
            actor=action.actor,
            actor_context=actor_context,
            notes=action.notes,
            explicit_user_action=action.explicit_user_action,
        ),
    )
    suggestion.status = "accepted_direct"
    suggestion.decision_event_id = decision_result["event"]["id"]
    _append_suggestion_event(
        session,
        suggestion=suggestion,
        event_type="accepted_direct",
        actor=action.actor,
        actor_context=actor_context,
        notes=action.notes,
        metadata={"decision_event_id": decision_result["event"]["id"]},
    )
    session.commit()
    session.refresh(suggestion)
    return {
        "route": "decision_event",
        "suggestion": serialize_suggestion(suggestion),
        "decision": decision_result,
    }


def route_review_decide(
    session: Session,
    request: DecisionEventRequest,
    *,
    evaluator: Optional[PermissionEvaluator] = None,
) -> dict[str, Any]:
    actor_context = derive_actor_context(request.actor, request.actor_context)
    permission_evaluator = evaluator or PermissionEvaluator(session)
    evaluation = permission_evaluator.evaluate(
        actor_context,
        ActionKey.REVIEW_DECIDE.value,
        DataScopeKey.REVIEW_DECISIONS.value,
    )

    if not evaluation.allowed and not evaluation.suggestion_allowed:
        raise PermissionDeniedError(
            ActionKey.REVIEW_DECIDE.value,
            DataScopeKey.REVIEW_DECISIONS.value,
            suggestion_allowed=False,
        )

    if request.target_type != "canonical_transaction":
        raise SuggestionServiceError(
            "target_type_not_allowed",
            "Ledger review decisions must attach to canonical transactions.",
        )

    canonical = session.get(CanonicalTransaction, request.target_id)
    if canonical is None:
        raise SuggestionServiceError(
            "target_not_found",
            "Canonical transaction not found.",
            status_code=404,
        )

    if request.decision_type not in DECISION_TYPE_FIELDS:
        raise SuggestionServiceError(
            "decision_type_not_allowed",
            f"{request.decision_type} is not allowed in v1.",
        )
    expected_field = DECISION_TYPE_FIELDS[request.decision_type]
    if request.field_name != expected_field:
        raise SuggestionServiceError(
            "field_decision_type_mismatch",
            f"{request.decision_type} must write {expected_field}.",
        )

    requires_approval, trigger = review_requires_approval(
        session,
        canonical=canonical,
        field_name=request.field_name,
        direct_authority=evaluation.allowed,
    )

    if requires_approval:
        if not is_approval_mode_enabled(session):
            if not evaluation.allowed:
                suggestion_result = create_suggestion(
                    session,
                    SuggestionCreate(
                        target_type=request.target_type,
                        target_id=request.target_id,
                        action_key=ActionKey.REVIEW_DECIDE.value,
                        decision_type=request.decision_type,
                        field_name=request.field_name,
                        proposed_value=request.approved_value or request.proposed_value,
                        actor=request.actor,
                        actor_context=request.actor_context,
                        suggestion_source=request.suggestion_source,
                        notes=request.notes,
                    ),
                )
                return {"route": "suggestion", **suggestion_result}
            raise SuggestionServiceError(
                "approval_mode_disabled",
                "Approval mode is disabled.",
                status_code=409,
            )

        approval_result = create_approval_request(
            session,
            ApprovalRequestCreate(
                target_type=request.target_type,
                target_id=request.target_id,
                action_key=ActionKey.REVIEW_DECIDE.value,
                decision_type=request.decision_type,
                field_name=request.field_name,
                proposed_value=request.approved_value or request.proposed_value,
                actor=request.actor,
                actor_context=request.actor_context,
                policy_trigger=trigger or "approval_required",
                notes=request.notes,
                suggestion_source=request.suggestion_source,
            ),
        )
        return {"route": "approval_request", **approval_result}

    if evaluation.allowed:
        try:
            decision_result = create_decision_event(session, request)
        except DecisionEventError as exc:
            raise SuggestionServiceError(exc.code, exc.message, status_code=exc.status_code) from exc
        return {"route": "decision_event", **decision_result}

    suggestion_result = create_suggestion(
        session,
        SuggestionCreate(
            target_type=request.target_type,
            target_id=request.target_id,
            action_key=ActionKey.REVIEW_DECIDE.value,
            decision_type=request.decision_type,
            field_name=request.field_name,
            proposed_value=request.approved_value or request.proposed_value,
            actor=request.actor,
            actor_context=request.actor_context,
            suggestion_source=request.suggestion_source,
            notes=request.notes,
        ),
    )
    return {"route": "suggestion", **suggestion_result}
