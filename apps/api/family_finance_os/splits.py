from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_to_json, derive_actor_context
from family_finance_os.models import (
    CanonicalTransaction,
    Category,
    DecisionEvent,
    FinancialGoal,
    FundPool,
    Receipt,
    ReceiptLineItem,
    TransactionAllocation,
)


MONEY_QUANT = Decimal("0.01")
ALLOCATION_SOURCES = {"manual", "receipt_promoted", "import_heuristic", "rule_suggestion"}


class SplitsError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AllocationLineRequest(BaseModel):
    amount: Decimal
    category_id: str = Field(min_length=1)
    subcategory: Optional[str] = None
    fund_pool_id: Optional[str] = None
    financial_goal_id: Optional[str] = None
    memo: Optional[str] = None
    source: str = "manual"


class TransactionAllocationsPutRequest(BaseModel):
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None
    lines: list[AllocationLineRequest] = Field(default_factory=list)
    note: Optional[str] = None


class TransactionAllocationsDeleteRequest(BaseModel):
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None
    note: Optional[str] = None


class ReceiptPromotionRequest(BaseModel):
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None
    receipt_id: str = Field(min_length=1)
    confirm: bool = False
    note: Optional[str] = None


class ReceiptPromoteToSplitsRequest(BaseModel):
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None
    transaction_id: str = Field(min_length=1)
    confirm: bool = False
    note: Optional[str] = None


def list_transaction_allocations(session: Session, transaction_id: str) -> dict[str, Any]:
    transaction = _get_transaction(session, transaction_id)
    allocations = _active_allocations(session, transaction.id)
    return _allocations_payload(session, transaction, allocations)


def replace_transaction_allocations(
    session: Session,
    transaction_id: str,
    request: TransactionAllocationsPutRequest,
) -> dict[str, Any]:
    transaction = _get_transaction(session, transaction_id)
    if not request.lines:
        raise SplitsError("allocation_lines_required", "At least one allocation line is required.")

    prepared_lines = [_prepare_line(session, line) for line in request.lines]
    total = sum((line["amount"] for line in prepared_lines), Decimal("0.00")).quantize(MONEY_QUANT)
    transaction_amount = _money_decimal(transaction.amount)
    if total != transaction_amount:
        raise SplitsError(
            "allocation_total_mismatch",
            "Allocation lines must sum exactly to the transaction amount.",
            detail_status_code(),
        )

    before = [_serialize_allocation(session, allocation) for allocation in _active_allocations(session, transaction.id)]
    for allocation in _active_allocations(session, transaction.id):
        allocation.status = "superseded"

    group_id = str(uuid4())
    event = _record_decision(
        session,
        transaction=transaction,
        decision_type="transaction_split_replace",
        previous_value=before,
        approved_value=[
            _line_decision_payload(line_number=index, line=line)
            for index, line in enumerate(prepared_lines, start=1)
        ],
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    allocations = []
    for index, line in enumerate(prepared_lines, start=1):
        allocation = TransactionAllocation(
            canonical_transaction_id=transaction.id,
            allocation_group_id=group_id,
            line_number=index,
            amount=line["amount"],
            category_id=line["category_id"],
            subcategory=line["subcategory"],
            fund_pool_id=line["fund_pool_id"],
            financial_goal_id=line["financial_goal_id"],
            memo=line["memo"],
            source=line["source"],
            status="active",
            decision_event_id=event.id,
        )
        session.add(allocation)
        allocations.append(allocation)
    session.commit()
    for allocation in allocations:
        session.refresh(allocation)
    return {**_allocations_payload(session, transaction, allocations), "event": _serialize_event(event)}


def delete_transaction_allocations(
    session: Session,
    transaction_id: str,
    request: TransactionAllocationsDeleteRequest,
) -> dict[str, Any]:
    transaction = _get_transaction(session, transaction_id)
    allocations = _active_allocations(session, transaction.id)
    before = [_serialize_allocation(session, allocation) for allocation in allocations]
    for allocation in allocations:
        allocation.status = "voided"
    event = _record_decision(
        session,
        transaction=transaction,
        decision_type="transaction_split_delete",
        previous_value=before,
        approved_value=[],
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    return {**_allocations_payload(session, transaction, []), "event": _serialize_event(event)}


def promote_receipt_lines_to_allocations(
    session: Session,
    transaction_id: str,
    request: ReceiptPromotionRequest,
) -> dict[str, Any]:
    transaction = _get_transaction(session, transaction_id)
    if not request.confirm:
        raise SplitsError(
            "receipt_promotion_confirmation_required",
            "Receipt lines can be promoted to splits only after explicit confirmation.",
        )
    receipt = session.get(Receipt, request.receipt_id)
    if receipt is None or receipt.canonical_transaction_id != transaction.id:
        raise SplitsError(
            "receipt_not_linked_to_transaction",
            "Receipt promotion requires a receipt linked to this transaction.",
            404,
        )
    lines = session.scalars(
        select(ReceiptLineItem)
        .where(ReceiptLineItem.receipt_id == receipt.id)
        .order_by(ReceiptLineItem.line_number)
    ).all()
    if not lines:
        raise SplitsError("receipt_lines_required", "Receipt promotion requires at least one line item.")
    missing_category = next((line for line in lines if not line.category_id), None)
    if missing_category is not None:
        raise SplitsError(
            "receipt_line_category_required",
            "All receipt lines must have a category before promotion to splits.",
        )
    transaction_amount = _money_decimal(transaction.amount)
    signed_line_amounts = [_allocation_amount_from_receipt_line(transaction, line.line_total) for line in lines]
    line_total = sum(signed_line_amounts, Decimal("0.00")).quantize(MONEY_QUANT)
    if line_total != transaction_amount:
        raise SplitsError(
            "receipt_promotion_total_mismatch",
            "Receipt line totals must equal the transaction amount before promotion to splits.",
        )
    allocation_lines = [
        AllocationLineRequest(
            amount=amount,
            category_id=line.category_id,
            subcategory=line.subcategory,
            fund_pool_id=line.fund_pool_id,
            memo=line.item_description,
            source="receipt_promoted",
        )
        for line, amount in zip(lines, signed_line_amounts)
    ]
    put_request = TransactionAllocationsPutRequest(
        actor=request.actor,
        actor_context=request.actor_context,
        lines=allocation_lines,
        note=request.note,
    )
    result = replace_transaction_allocations(session, transaction_id, put_request)
    receipt = session.get(Receipt, request.receipt_id)
    if receipt is not None:
        receipt.applied_as_split_decision_event_id = result["event"]["id"]
        receipt.review_status = "reviewed"
        receipt.status = "matched"
        session.commit()
    return {**result, "receipt_id": request.receipt_id}


def _active_allocations(session: Session, transaction_id: str) -> list[TransactionAllocation]:
    return session.scalars(
        select(TransactionAllocation)
        .where(
            TransactionAllocation.canonical_transaction_id == transaction_id,
            TransactionAllocation.status == "active",
        )
        .order_by(TransactionAllocation.line_number)
    ).all()


def _get_transaction(session: Session, transaction_id: str) -> CanonicalTransaction:
    transaction = session.get(CanonicalTransaction, transaction_id)
    if transaction is None:
        raise SplitsError("transaction_not_found", "Transaction not found.", 404)
    return transaction


def _prepare_line(session: Session, line: AllocationLineRequest) -> dict[str, Any]:
    amount = _money_decimal(line.amount)
    if amount == Decimal("0.00"):
        raise SplitsError("allocation_amount_invalid", "Allocation amount must be non-zero.")
    if session.get(Category, line.category_id) is None:
        raise SplitsError("allocation_category_invalid", "Allocation category must exist.")
    if line.fund_pool_id and session.get(FundPool, line.fund_pool_id) is None:
        raise SplitsError("allocation_fund_pool_invalid", "Allocation fund pool must exist.")
    if line.financial_goal_id and session.get(FinancialGoal, line.financial_goal_id) is None:
        raise SplitsError("allocation_financial_goal_invalid", "Allocation financial goal must exist.")
    if line.source not in ALLOCATION_SOURCES:
        raise SplitsError("allocation_source_invalid", "Allocation source is not supported.")
    return {
        "amount": amount,
        "category_id": line.category_id,
        "subcategory": _clean_optional(line.subcategory),
        "fund_pool_id": line.fund_pool_id,
        "financial_goal_id": line.financial_goal_id,
        "memo": _clean_optional(line.memo),
        "source": line.source,
    }


def _allocations_payload(
    session: Session,
    transaction: CanonicalTransaction,
    allocations: list[TransactionAllocation],
) -> dict[str, Any]:
    transaction_amount = _money_decimal(transaction.amount)
    allocated = sum((_money_decimal(allocation.amount) for allocation in allocations), Decimal("0.00")).quantize(MONEY_QUANT)
    remainder = (transaction_amount - allocated).quantize(MONEY_QUANT)
    return {
        "transaction_id": transaction.id,
        "allocations": [_serialize_allocation(session, allocation) for allocation in allocations],
        "summary": {
            "transaction_amount": _money(transaction_amount),
            "allocated": _money(allocated),
            "remainder": _money(remainder),
            "balanced": bool(allocations) and remainder == Decimal("0.00"),
            "allocation_count": len(allocations),
        },
    }


def _serialize_allocation(session: Session, allocation: TransactionAllocation) -> dict[str, Any]:
    category = session.get(Category, allocation.category_id)
    pool = session.get(FundPool, allocation.fund_pool_id) if allocation.fund_pool_id else None
    goal = session.get(FinancialGoal, allocation.financial_goal_id) if allocation.financial_goal_id else None
    return {
        "id": allocation.id,
        "canonical_transaction_id": allocation.canonical_transaction_id,
        "allocation_group_id": allocation.allocation_group_id,
        "line_number": allocation.line_number,
        "amount": _money(_money_decimal(allocation.amount)),
        "category_id": allocation.category_id,
        "category_display_name": category.display_name if category else None,
        "subcategory": allocation.subcategory,
        "fund_pool_id": allocation.fund_pool_id,
        "fund_pool_name": pool.name if pool else None,
        "financial_goal_id": allocation.financial_goal_id,
        "financial_goal_name": goal.name if goal else None,
        "memo": allocation.memo,
        "source": allocation.source,
        "status": allocation.status,
        "decision_event_id": allocation.decision_event_id,
        "created_at": allocation.created_at,
        "updated_at": allocation.updated_at,
    }


def _record_decision(
    session: Session,
    *,
    transaction: CanonicalTransaction,
    decision_type: str,
    previous_value: Any,
    approved_value: Any,
    actor: str,
    actor_context: Optional[ActorContext],
    notes: Optional[str],
) -> DecisionEvent:
    event = DecisionEvent(
        target_type="canonical_transaction",
        target_id=transaction.id,
        decision_type=decision_type,
        field_name="transaction_allocations",
        previous_value=_decision_value(previous_value),
        proposed_value=_decision_value(approved_value),
        approved_value=_decision_value(approved_value),
        actor=actor,
        actor_context_json=actor_context_to_json(derive_actor_context(actor, actor_context)),
        notes=notes.strip() if notes else None,
        suggestion_source="owner",
    )
    session.add(event)
    session.flush()
    return event


def _line_decision_payload(*, line_number: int, line: dict[str, Any]) -> dict[str, Any]:
    return {
        "line_number": line_number,
        "amount": _money(line["amount"]),
        "category_id": line["category_id"],
        "subcategory": line["subcategory"],
        "fund_pool_id": line["fund_pool_id"],
        "financial_goal_id": line["financial_goal_id"],
        "memo": line["memo"],
        "source": line["source"],
    }


def _serialize_event(event: DecisionEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "decision_type": event.decision_type,
        "field_name": event.field_name,
        "actor": event.actor,
        "created_at": event.created_at,
    }


def _decision_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _money_decimal(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _allocation_amount_from_receipt_line(transaction: CanonicalTransaction, line_total: Decimal) -> Decimal:
    magnitude = abs(_money_decimal(line_total))
    transaction_amount = _money_decimal(transaction.amount)
    if transaction_amount < 0:
        return -magnitude
    if transaction_amount > 0:
        return magnitude
    raise SplitsError("allocation_amount_invalid", "Transaction amount must be non-zero.")


def _money(value: Decimal) -> str:
    return str(_money_decimal(value))


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def detail_status_code() -> int:
    return 422
