from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from dillon_finances.actors import ActorContext, actor_context_from_json, actor_context_to_json, derive_actor_context
from dillon_finances.category_service import category_display_name, category_identity_for_value, resolve_category_key
from dillon_finances.models import CanonicalTransaction, DecisionEvent, ValidationFinding


class DecisionEventError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DecisionEventRequest(BaseModel):
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    decision_type: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    proposed_value: Optional[Any] = None
    approved_value: Optional[Any] = None
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    notes: Optional[str] = None
    suggestion_source: str = "owner"
    explicit_user_action: bool = False
    supersedes_event_id: Optional[str] = None
    reverts_event_id: Optional[str] = None


DECISION_TYPE_FIELDS = {
    "category_change": "category",
    "subcategory_change": "subcategory",
    "review_status_change": "review_status",
    "review_reason_change": "review_reason",
    "transfer_flag_status": "transfer_status",
    "reimbursement_candidate_status": "reimbursement_status",
    "medical_tax_candidate_status": "medical_tax_status",
    "project_candidate_flag": "project_candidate",
    "side_hustle_candidate_flag": "side_hustle_candidate",
}

STATUS_VALUES = {
    "review_status": {"unreviewed", "needs_review", "reviewed", "approved"},
    "transfer_status": {"none", "candidate", "confirmed", "not_transfer"},
    "reimbursement_status": {"none", "candidate", "submitted", "reimbursed", "not_reimbursable"},
    "medical_tax_status": {"none", "candidate", "tax_relevant", "not_relevant"},
}

TEXT_FIELDS = {"category", "subcategory", "review_reason"}
BOOLEAN_FIELDS = {"project_candidate", "side_hustle_candidate"}
HIGH_IMPACT_FIELDS = {
    "reimbursement_status",
    "medical_tax_status",
    "project_candidate",
    "side_hustle_candidate",
}
SUGGESTION_SOURCES = {"owner", "user", "rule", "import_heuristic", "codex", "future_ai_proposal"}


def _text_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _public_value(field_name: str, value: Optional[str]) -> Any:
    if value is None:
        return None
    if field_name in BOOLEAN_FIELDS:
        return value == "true"
    return value


def _normalize_value(field_name: str, value: Any, *, session: Session | None = None) -> str:
    if field_name in BOOLEAN_FIELDS:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower()
        raise DecisionEventError(
            "invalid_controlled_value",
            f"{field_name} must be true or false.",
        )

    if value is None:
        raise DecisionEventError(
            "invalid_controlled_value",
            f"{field_name} requires an approved value.",
        )

    normalized = _text_value(value).strip()
    if not normalized:
        raise DecisionEventError(
            "invalid_controlled_value",
            f"{field_name} requires a non-empty approved value.",
        )

    if field_name == "category":
        if session is None:
            return normalized
        category_key = resolve_category_key(session, normalized)
        if category_key is None:
            raise DecisionEventError(
                "unknown_category",
                "Category decisions must use an existing category key, display label, or alias.",
            )
        return category_key

    if field_name in STATUS_VALUES and normalized not in STATUS_VALUES[field_name]:
        raise DecisionEventError(
            "invalid_controlled_value",
            f"{field_name} must be one of: {', '.join(sorted(STATUS_VALUES[field_name]))}.",
        )

    max_length = 255 if field_name == "review_reason" else 120
    if field_name in TEXT_FIELDS and len(normalized) > max_length:
        raise DecisionEventError(
            "invalid_controlled_value",
            f"{field_name} must be {max_length} characters or fewer.",
        )
    return normalized


def _previous_value_text(field_name: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    return _normalize_value(field_name, value)


def _decision_events_for_target(session: Session, target_id: str) -> list[DecisionEvent]:
    return session.scalars(
        select(DecisionEvent)
        .where(
            DecisionEvent.target_type == "canonical_transaction",
            DecisionEvent.target_id == target_id,
        )
        .order_by(DecisionEvent.created_at, DecisionEvent.id)
    ).all()


def _inactive_event_ids(events: list[DecisionEvent]) -> set[str]:
    inactive: set[str] = set()
    for event in events:
        if event.supersedes_event_id:
            inactive.add(event.supersedes_event_id)
        if event.reverts_event_id:
            inactive.add(event.reverts_event_id)
    return inactive


def _primary_imported_fact(canonical: CanonicalTransaction):
    return next(
        iter(
            sorted(
                canonical.imported_rows,
                key=lambda imported_row: (imported_row.posted_date, imported_row.source_row_number),
            )
        ),
        None,
    )


def derive_decision_state(
    session: Session,
    canonical: CanonicalTransaction,
) -> dict[str, Any]:
    primary_fact = _primary_imported_fact(canonical)
    original_category = primary_fact.initial_category if primary_fact else None
    original_subcategory = primary_fact.initial_subcategory if primary_fact else None
    original_category_identity = category_identity_for_value(session, original_category)
    state: dict[str, Any] = {
        "category_original": original_category_identity["display_name"],
        "category_key_original": original_category_identity["category_key"],
        "category_display_name_original": original_category_identity["display_name"],
        "subcategory_original": original_subcategory,
        "category_current": original_category_identity["display_name"],
        "category_key_current": original_category_identity["category_key"],
        "category_display_name_current": original_category_identity["display_name"],
        "subcategory_current": original_subcategory,
        "review_status": "unreviewed",
        "review_reason": None,
        "transfer_status": "none",
        "reimbursement_status": "none",
        "medical_tax_status": "none",
        "project_candidate": False,
        "side_hustle_candidate": False,
        "decision_history_count": 0,
    }

    events = _decision_events_for_target(session, canonical.id)
    inactive_ids = _inactive_event_ids(events)
    for event in events:
        if event.id in inactive_ids:
            continue
        if event.field_name == "category":
            category_key = _public_value(event.field_name, event.approved_value)
            display_name = category_display_name(session, category_key) or category_key
            state["category_key_current"] = category_key
            state["category_display_name_current"] = display_name
            state["category_current"] = display_name
        elif event.field_name == "subcategory":
            state["subcategory_current"] = _public_value(event.field_name, event.approved_value)
        else:
            state[event.field_name] = _public_value(event.field_name, event.approved_value)

    state["decision_history_count"] = len(events)
    return state


def serialize_decision_event(
    event: DecisionEvent,
    *,
    active: bool = True,
) -> dict[str, Any]:
    return {
        "id": event.id,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "decision_type": event.decision_type,
        "field_name": event.field_name,
        "previous_value": _public_value(event.field_name, event.previous_value),
        "proposed_value": _public_value(event.field_name, event.proposed_value),
        "approved_value": _public_value(event.field_name, event.approved_value),
        "actor": event.actor,
        "actor_context": actor_context_from_json(event.actor_context_json),
        "notes": event.notes,
        "suggestion_source": event.suggestion_source,
        "supersedes_event_id": event.supersedes_event_id,
        "reverts_event_id": event.reverts_event_id,
        "active": active,
        "created_at": event.created_at,
    }


def decision_history(session: Session, canonical: CanonicalTransaction) -> list[dict[str, Any]]:
    events = _decision_events_for_target(session, canonical.id)
    inactive_ids = _inactive_event_ids(events)
    return [
        serialize_decision_event(event, active=event.id not in inactive_ids)
        for event in events
    ]


def _open_blocking_validation_exists(session: Session, canonical: CanonicalTransaction) -> bool:
    if canonical.status == "ambiguous":
        return True
    finding = session.scalar(
        select(ValidationFinding).where(
            ValidationFinding.target_type == "canonical_transaction",
            ValidationFinding.target_id == canonical.id,
            ValidationFinding.severity == "blocking",
            ValidationFinding.status == "open",
        )
    )
    return finding is not None


def _referenced_event(
    session: Session,
    *,
    event_id: Optional[str],
    target_id: str,
    field_name: str,
    reference_type: str,
) -> Optional[DecisionEvent]:
    if event_id is None:
        return None
    event = session.get(DecisionEvent, event_id)
    if event is None:
        raise DecisionEventError(
            f"{reference_type}_event_not_found",
            f"Referenced decision event {event_id} was not found.",
            status_code=404,
        )
    if event.target_type != "canonical_transaction" or event.target_id != target_id:
        raise DecisionEventError(
            "event_target_mismatch",
            "Referenced decision event belongs to a different target.",
        )
    if event.field_name != field_name:
        raise DecisionEventError(
            "event_field_mismatch",
            "Referenced decision event belongs to a different field.",
        )
    return event


def _validate_request(
    session: Session,
    request: DecisionEventRequest,
    canonical: CanonicalTransaction,
    approved_value: str,
) -> dict[str, Any]:
    if request.suggestion_source not in SUGGESTION_SOURCES:
        raise DecisionEventError(
            "suggestion_source_not_allowed",
            f"{request.suggestion_source} is not an allowed suggestion source.",
        )
    if not request.explicit_user_action:
        raise DecisionEventError(
            "explicit_user_action_required",
            "Controlled decisions require an explicit owner save action.",
        )
    if request.decision_type not in DECISION_TYPE_FIELDS:
        raise DecisionEventError(
            "decision_type_not_allowed",
            f"{request.decision_type} is not allowed in v1.",
        )
    expected_field = DECISION_TYPE_FIELDS[request.decision_type]
    if request.field_name != expected_field:
        raise DecisionEventError(
            "field_decision_type_mismatch",
            f"{request.decision_type} must write {expected_field}.",
        )

    if _open_blocking_validation_exists(session, canonical):
        raise DecisionEventError(
            "target_blocked_by_validation",
            "This transaction has blocking validation and cannot receive review decisions.",
            status_code=409,
        )

    current_state = derive_decision_state(session, canonical)
    if request.field_name == "subcategory" and not current_state["category_current"]:
        raise DecisionEventError(
            "category_required_for_subcategory",
            "A category is required before setting a subcategory.",
        )

    previous_key = "category_key_current" if request.field_name == "category" else (
        f"{request.field_name}_current"
        if request.field_name == "subcategory"
        else request.field_name
    )
    previous_public_value = current_state.get(previous_key)
    previous_value = _previous_value_text(request.field_name, previous_public_value)
    if approved_value == previous_value and not request.reverts_event_id:
        raise DecisionEventError(
            "no_effect_decision",
            "The approved value already matches the current reviewed state.",
            status_code=409,
        )

    superseded_event = _referenced_event(
        session,
        event_id=request.supersedes_event_id,
        target_id=canonical.id,
        field_name=request.field_name,
        reference_type="supersedes",
    )
    reverted_event = _referenced_event(
        session,
        event_id=request.reverts_event_id,
        target_id=canonical.id,
        field_name=request.field_name,
        reference_type="reverts",
    )

    notes_required = (
        request.field_name in HIGH_IMPACT_FIELDS
        or request.suggestion_source in {"codex", "future_ai_proposal"}
        or superseded_event is not None
        or reverted_event is not None
    )
    if notes_required and not (request.notes and request.notes.strip()):
        raise DecisionEventError(
            "required_note_missing",
            "High-impact, supersede, revert, and AI/Codex-suggested decisions require an owner note.",
        )

    return {
        "previous_value": previous_value,
        "superseded_event": superseded_event,
        "reverted_event": reverted_event,
    }


def create_decision_event(
    session: Session,
    request: DecisionEventRequest,
) -> dict[str, Any]:
    if request.target_type != "canonical_transaction":
        raise DecisionEventError(
            "target_type_not_allowed",
            "Ledger review decisions must attach to canonical transactions.",
        )

    canonical = session.get(CanonicalTransaction, request.target_id)
    if canonical is None:
        raise DecisionEventError(
            "target_not_found",
            "Canonical transaction not found.",
            status_code=404,
        )

    approved_value = _normalize_value(request.field_name, request.approved_value, session=session)
    proposed_value = (
        _normalize_value(request.field_name, request.proposed_value, session=session)
        if request.proposed_value is not None
        else approved_value
    )
    validation_context = _validate_request(session, request, canonical, approved_value)

    event = DecisionEvent(
        target_type="canonical_transaction",
        target_id=canonical.id,
        decision_type=request.decision_type,
        field_name=request.field_name,
        previous_value=validation_context["previous_value"],
        proposed_value=proposed_value,
        approved_value=approved_value,
        actor=request.actor,
        actor_context_json=actor_context_to_json(derive_actor_context(request.actor, request.actor_context)),
        notes=request.notes.strip() if request.notes else None,
        suggestion_source=request.suggestion_source,
        supersedes_event_id=request.supersedes_event_id,
        reverts_event_id=request.reverts_event_id,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return {
        "event": serialize_decision_event(event),
        "current_state": derive_decision_state(session, canonical),
    }
