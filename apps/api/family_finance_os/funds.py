from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_to_json, derive_actor_context
from family_finance_os.models import (
    BudgetTarget,
    CanonicalTransaction,
    DecisionEvent,
    FinancialGoal,
    FundPool,
    MonthlyPoolCommitment,
    TransactionAllocation,
)
from family_finance_os.spendable import compute_spendable


MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
MONEY_QUANT = Decimal("0.01")
GOAL_TYPES = {"emergency", "sinking_fund", "purchase", "other"}


class FundsError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ActorMutationRequest(BaseModel):
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None
    note: Optional[str] = None


class FundPoolCreateRequest(ActorMutationRequest):
    name: str = Field(min_length=1, max_length=160)
    pool_key: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    rollover_policy: str = "none"


class FundPoolPatchRequest(ActorMutationRequest):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    pool_key: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None
    rollover_policy: Optional[str] = None


class FundCommitmentCreateRequest(ActorMutationRequest):
    fund_pool_id: str = Field(min_length=1)
    month: str = Field(min_length=7, max_length=7)
    committed_amount: Decimal
    funding_source: str = Field(default="monthly_income", min_length=1, max_length=80)
    status: str = "active"


class FundCommitmentPatchRequest(ActorMutationRequest):
    fund_pool_id: Optional[str] = Field(default=None, min_length=1)
    month: Optional[str] = Field(default=None, min_length=7, max_length=7)
    committed_amount: Optional[Decimal] = None
    funding_source: Optional[str] = Field(default=None, min_length=1, max_length=80)
    status: Optional[str] = None


class FinancialGoalCreateRequest(ActorMutationRequest):
    name: str = Field(min_length=1, max_length=160)
    goal_key: Optional[str] = Field(default=None, max_length=120)
    goal_type: str = Field(min_length=1, max_length=40)
    target_amount: Decimal
    target_date: Optional[str] = None
    linked_fund_pool_id: Optional[str] = None
    reserved_balance: Decimal = Decimal("0.00")
    status: str = "active"
    notes: Optional[str] = None


class FinancialGoalPatchRequest(ActorMutationRequest):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    goal_key: Optional[str] = Field(default=None, max_length=120)
    goal_type: Optional[str] = Field(default=None, min_length=1, max_length=40)
    target_amount: Optional[Decimal] = None
    target_date: Optional[str] = None
    linked_fund_pool_id: Optional[str] = None
    reserved_balance: Optional[Decimal] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class BudgetTargetCreateRequest(ActorMutationRequest):
    target_scope: str = Field(min_length=1, max_length=40)
    target_key: Optional[str] = Field(default=None, max_length=120)
    month: Optional[str] = Field(default=None, min_length=7, max_length=7)
    category_id: Optional[str] = None
    fund_pool_id: Optional[str] = None
    financial_goal_id: Optional[str] = None
    target_amount: Decimal
    warning_threshold_amount: Optional[Decimal] = None
    hard_cap_amount: Optional[Decimal] = None
    review_threshold_amount: Optional[Decimal] = None
    status: str = "active"
    notes: Optional[str] = None


class BudgetTargetPatchRequest(ActorMutationRequest):
    target_scope: Optional[str] = Field(default=None, min_length=1, max_length=40)
    month: Optional[str] = Field(default=None, min_length=7, max_length=7)
    category_id: Optional[str] = None
    fund_pool_id: Optional[str] = None
    financial_goal_id: Optional[str] = None
    target_amount: Optional[Decimal] = None
    warning_threshold_amount: Optional[Decimal] = None
    hard_cap_amount: Optional[Decimal] = None
    review_threshold_amount: Optional[Decimal] = None
    status: Optional[str] = None
    notes: Optional[str] = None


def validate_month(month: Optional[str]) -> str:
    if month is None:
        return date.today().isoformat()[:7]
    if not MONTH_PATTERN.fullmatch(month):
        raise FundsError("invalid_month", "month must use YYYY-MM format.")
    return month


def funds_summary(session: Session, *, month: Optional[str] = None) -> dict[str, Any]:
    target_month = validate_month(month)
    spendable = compute_spendable(session, month=target_month)
    pools = _pool_summaries(session, target_month)
    goals = list_financial_goals(session)
    budget_targets = list_budget_targets(session, month=target_month)
    fund_commitments = sum((_decimal(pool["commitment"]) for pool in pools), Decimal("0.00"))
    pool_remaining_total = sum((_decimal(pool["pool_remaining"]) for pool in pools), Decimal("0.00"))
    funded_this_month = _funded_this_month(session, target_month, fallback=fund_commitments)
    uncommitted = funded_this_month - fund_commitments
    return {
        "month": target_month,
        "spendable": {
            "headline": spendable["headline_spendable"],
            "verified_liquid_cash": spendable["verified_liquid_cash"],
            "reserved_goal_balance": spendable["reserved_goal_balance"],
            "manual_upcoming_obligations": spendable["manual_obligations_total"],
            "provisional_exposure": spendable["provisional_exposure"],
            "card_obligation_total": spendable["card_obligation_total"],
            "card_obligation_items": spendable["card_obligation_items"],
            "includes_provisional": spendable["include_provisional"],
            "confidence": spendable["confidence"],
            "warnings": spendable["warnings"],
        },
        "commitment_health": {
            "funded_this_month": _money(funded_this_month),
            "fund_commitments": _money(fund_commitments),
            "pool_remaining_total": _money(pool_remaining_total),
            "uncommitted": _money(uncommitted),
            "overcommitted": uncommitted < Decimal("0.00"),
        },
        "pools": pools,
        "goals": goals,
        "budget_targets": budget_targets,
    }


def list_fund_pools(session: Session, *, month: Optional[str] = None) -> list[dict[str, Any]]:
    if month is not None:
        return _pool_summaries(session, validate_month(month))
    pools = session.scalars(select(FundPool).order_by(FundPool.sort_order, FundPool.name)).all()
    return [serialize_fund_pool(pool) for pool in pools]


def create_fund_pool(session: Session, request: FundPoolCreateRequest) -> dict[str, Any]:
    name = _required_name(request.name, "fund_pool_name_required", "Fund pool name is required.")
    _ensure_unique_active_pool_name(session, name)
    pool_key = _unique_key(
        session,
        FundPool,
        "pool_key",
        request.pool_key or name,
        "fund_pool_key_exists",
        "A fund pool with this key already exists.",
    )
    sort_order = request.sort_order
    if sort_order is None:
        sort_order = _next_pool_sort_order(session)
    pool = FundPool(
        pool_key=pool_key,
        name=name,
        description=_clean_optional(request.description),
        status="active",
        sort_order=sort_order,
        rollover_policy=request.rollover_policy,
    )
    session.add(pool)
    session.flush()
    _record_decision(
        session,
        target_type="fund_pool",
        target_id=pool.id,
        decision_type="fund_pool_create",
        field_name="record",
        previous_value=None,
        approved_value=serialize_fund_pool(pool),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(pool)
    return serialize_fund_pool(pool)


def update_fund_pool(session: Session, pool_id: str, request: FundPoolPatchRequest) -> dict[str, Any]:
    pool = _get_or_404(session, FundPool, pool_id, "fund_pool_not_found", "Fund pool was not found.")
    before = serialize_fund_pool(pool)
    if request.name is not None:
        name = _required_name(request.name, "fund_pool_name_required", "Fund pool name is required.")
        _ensure_unique_active_pool_name(session, name, existing_id=pool.id)
        pool.name = name
    if request.pool_key is not None and request.pool_key != pool.pool_key:
        pool.pool_key = _unique_key(
            session,
            FundPool,
            "pool_key",
            request.pool_key,
            "fund_pool_key_exists",
            "A fund pool with this key already exists.",
        )
    if request.description is not None:
        pool.description = _clean_optional(request.description)
    if request.status is not None:
        pool.status = request.status
    if request.sort_order is not None:
        pool.sort_order = request.sort_order
    if request.rollover_policy is not None:
        pool.rollover_policy = request.rollover_policy
    session.flush()
    _record_decision(
        session,
        target_type="fund_pool",
        target_id=pool.id,
        decision_type="fund_pool_update",
        field_name="record",
        previous_value=before,
        approved_value=serialize_fund_pool(pool),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(pool)
    return serialize_fund_pool(pool)


def list_fund_commitments(session: Session, *, month: Optional[str] = None) -> list[dict[str, Any]]:
    statement = select(MonthlyPoolCommitment).order_by(MonthlyPoolCommitment.month, MonthlyPoolCommitment.created_at)
    if month is not None:
        statement = statement.where(MonthlyPoolCommitment.month == validate_month(month))
    return [serialize_commitment(commitment, session=session) for commitment in session.scalars(statement).all()]


def create_fund_commitment(session: Session, request: FundCommitmentCreateRequest) -> dict[str, Any]:
    target_month = validate_month(request.month)
    _get_or_404(session, FundPool, request.fund_pool_id, "fund_pool_not_found", "Fund pool was not found.")
    commitment = MonthlyPoolCommitment(
        fund_pool_id=request.fund_pool_id,
        month=target_month,
        committed_amount=_non_negative_money(request.committed_amount, "invalid_commitment_amount"),
        funding_source=request.funding_source.strip(),
        status=request.status,
        notes=_clean_optional(request.note),
    )
    session.add(commitment)
    session.flush()
    event = _record_decision(
        session,
        target_type="fund_commitment",
        target_id=commitment.id,
        decision_type="fund_commitment_create",
        field_name="record",
        previous_value=None,
        approved_value=serialize_commitment(commitment, session=session),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    commitment.decision_event_id = event.id
    session.commit()
    session.refresh(commitment)
    return serialize_commitment(commitment, session=session)


def update_fund_commitment(session: Session, commitment_id: str, request: FundCommitmentPatchRequest) -> dict[str, Any]:
    commitment = _get_or_404(
        session,
        MonthlyPoolCommitment,
        commitment_id,
        "fund_commitment_not_found",
        "Fund commitment was not found.",
    )
    before = serialize_commitment(commitment, session=session)
    if request.fund_pool_id is not None:
        _get_or_404(session, FundPool, request.fund_pool_id, "fund_pool_not_found", "Fund pool was not found.")
        commitment.fund_pool_id = request.fund_pool_id
    if request.month is not None:
        commitment.month = validate_month(request.month)
    if request.committed_amount is not None:
        commitment.committed_amount = _non_negative_money(request.committed_amount, "invalid_commitment_amount")
    if request.funding_source is not None:
        commitment.funding_source = request.funding_source.strip()
    if request.status is not None:
        commitment.status = request.status
    if request.note is not None:
        commitment.notes = _clean_optional(request.note)
    session.flush()
    event = _record_decision(
        session,
        target_type="fund_commitment",
        target_id=commitment.id,
        decision_type="fund_commitment_update",
        field_name="record",
        previous_value=before,
        approved_value=serialize_commitment(commitment, session=session),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    commitment.decision_event_id = event.id
    session.commit()
    session.refresh(commitment)
    return serialize_commitment(commitment, session=session)


def delete_fund_commitment(session: Session, commitment_id: str, request: ActorMutationRequest) -> dict[str, Any]:
    commitment = _get_or_404(
        session,
        MonthlyPoolCommitment,
        commitment_id,
        "fund_commitment_not_found",
        "Fund commitment was not found.",
    )
    before = serialize_commitment(commitment, session=session)
    commitment.status = "deleted"
    session.flush()
    _record_decision(
        session,
        target_type="fund_commitment",
        target_id=commitment.id,
        decision_type="fund_commitment_delete",
        field_name="status",
        previous_value=before,
        approved_value=serialize_commitment(commitment, session=session),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(commitment)
    return serialize_commitment(commitment, session=session)


def list_financial_goals(session: Session) -> list[dict[str, Any]]:
    goals = session.scalars(select(FinancialGoal).order_by(FinancialGoal.name, FinancialGoal.goal_key)).all()
    return [serialize_goal(goal) for goal in goals]


def create_financial_goal(session: Session, request: FinancialGoalCreateRequest) -> dict[str, Any]:
    name = _required_name(request.name, "goal_name_required", "Financial goal name is required.")
    _validate_goal_type(request.goal_type)
    if request.linked_fund_pool_id:
        _get_or_404(session, FundPool, request.linked_fund_pool_id, "fund_pool_not_found", "Fund pool was not found.")
    goal = FinancialGoal(
        goal_key=_unique_key(
            session,
            FinancialGoal,
            "goal_key",
            request.goal_key or name,
            "financial_goal_key_exists",
            "A financial goal with this key already exists.",
        ),
        name=name,
        goal_type=request.goal_type,
        target_amount=_non_negative_money(request.target_amount, "invalid_goal_target_amount"),
        target_date=request.target_date,
        linked_fund_pool_id=request.linked_fund_pool_id,
        reserved_balance=_non_negative_money(request.reserved_balance, "invalid_reserved_balance"),
        status=request.status,
        notes=_clean_optional(request.notes),
    )
    session.add(goal)
    session.flush()
    _record_decision(
        session,
        target_type="financial_goal",
        target_id=goal.id,
        decision_type="financial_goal_create",
        field_name="record",
        previous_value=None,
        approved_value=serialize_goal(goal),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(goal)
    return serialize_goal(goal)


def update_financial_goal(session: Session, goal_id: str, request: FinancialGoalPatchRequest) -> dict[str, Any]:
    goal = _get_or_404(session, FinancialGoal, goal_id, "financial_goal_not_found", "Financial goal was not found.")
    before = serialize_goal(goal)
    if request.name is not None:
        goal.name = _required_name(request.name, "goal_name_required", "Financial goal name is required.")
    if request.goal_key is not None and request.goal_key != goal.goal_key:
        goal.goal_key = _unique_key(
            session,
            FinancialGoal,
            "goal_key",
            request.goal_key,
            "financial_goal_key_exists",
            "A financial goal with this key already exists.",
        )
    if request.goal_type is not None:
        _validate_goal_type(request.goal_type)
        goal.goal_type = request.goal_type
    if request.target_amount is not None:
        goal.target_amount = _non_negative_money(request.target_amount, "invalid_goal_target_amount")
    if request.target_date is not None:
        goal.target_date = request.target_date
    if request.linked_fund_pool_id is not None:
        _get_or_404(session, FundPool, request.linked_fund_pool_id, "fund_pool_not_found", "Fund pool was not found.")
        goal.linked_fund_pool_id = request.linked_fund_pool_id
    if request.reserved_balance is not None:
        goal.reserved_balance = _non_negative_money(request.reserved_balance, "invalid_reserved_balance")
    if request.status is not None:
        goal.status = request.status
    if request.notes is not None:
        goal.notes = _clean_optional(request.notes)
    session.flush()
    _record_decision(
        session,
        target_type="financial_goal",
        target_id=goal.id,
        decision_type="financial_goal_update",
        field_name="record",
        previous_value=before,
        approved_value=serialize_goal(goal),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(goal)
    return serialize_goal(goal)


def list_budget_targets(session: Session, *, month: Optional[str] = None) -> list[dict[str, Any]]:
    statement = select(BudgetTarget).order_by(BudgetTarget.month, BudgetTarget.target_scope, BudgetTarget.target_key)
    if month is not None:
        statement = statement.where(BudgetTarget.month == validate_month(month))
    return [serialize_budget_target(target) for target in session.scalars(statement).all()]


def create_budget_target(session: Session, request: BudgetTargetCreateRequest) -> dict[str, Any]:
    month = validate_month(request.month) if request.month is not None else None
    target = BudgetTarget(
        target_key=_unique_key(
            session,
            BudgetTarget,
            "target_key",
            request.target_key or _target_key_seed(request.target_scope, month),
            "budget_target_key_exists",
            "A budget target with this key already exists.",
        ),
        month=month,
        target_scope=request.target_scope,
        category_id=request.category_id,
        fund_pool_id=request.fund_pool_id,
        financial_goal_id=request.financial_goal_id,
        target_amount=_non_negative_money(request.target_amount, "invalid_target_amount"),
        warning_threshold_amount=request.warning_threshold_amount,
        hard_cap_amount=request.hard_cap_amount,
        review_threshold_amount=request.review_threshold_amount,
        status=request.status,
        notes=_clean_optional(request.notes),
    )
    session.add(target)
    session.flush()
    event = _record_decision(
        session,
        target_type="budget_target",
        target_id=target.id,
        decision_type="budget_target_create",
        field_name="record",
        previous_value=None,
        approved_value=serialize_budget_target(target),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    target.decision_event_id = event.id
    session.commit()
    session.refresh(target)
    return serialize_budget_target(target)


def update_budget_target(session: Session, target_id: str, request: BudgetTargetPatchRequest) -> dict[str, Any]:
    target = _get_or_404(session, BudgetTarget, target_id, "budget_target_not_found", "Budget target was not found.")
    before = serialize_budget_target(target)
    if request.target_scope is not None:
        target.target_scope = request.target_scope
    if request.month is not None:
        target.month = validate_month(request.month)
    if request.category_id is not None:
        target.category_id = request.category_id
    if request.fund_pool_id is not None:
        target.fund_pool_id = request.fund_pool_id
    if request.financial_goal_id is not None:
        target.financial_goal_id = request.financial_goal_id
    if request.target_amount is not None:
        target.target_amount = _non_negative_money(request.target_amount, "invalid_target_amount")
    if request.warning_threshold_amount is not None:
        target.warning_threshold_amount = request.warning_threshold_amount
    if request.hard_cap_amount is not None:
        target.hard_cap_amount = request.hard_cap_amount
    if request.review_threshold_amount is not None:
        target.review_threshold_amount = request.review_threshold_amount
    if request.status is not None:
        target.status = request.status
    if request.notes is not None:
        target.notes = _clean_optional(request.notes)
    session.flush()
    event = _record_decision(
        session,
        target_type="budget_target",
        target_id=target.id,
        decision_type="budget_target_update",
        field_name="record",
        previous_value=before,
        approved_value=serialize_budget_target(target),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    target.decision_event_id = event.id
    session.commit()
    session.refresh(target)
    return serialize_budget_target(target)


def serialize_fund_pool(pool: FundPool) -> dict[str, Any]:
    return {
        "id": pool.id,
        "pool_key": pool.pool_key,
        "name": pool.name,
        "description": pool.description,
        "status": pool.status,
        "sort_order": pool.sort_order,
        "rollover_policy": pool.rollover_policy,
        "created_at": pool.created_at,
        "updated_at": pool.updated_at,
    }


def serialize_commitment(commitment: MonthlyPoolCommitment, *, session: Session) -> dict[str, Any]:
    pool = session.get(FundPool, commitment.fund_pool_id)
    return {
        "id": commitment.id,
        "fund_pool_id": commitment.fund_pool_id,
        "fund_pool_name": pool.name if pool else None,
        "month": commitment.month,
        "committed_amount": _money(Decimal(commitment.committed_amount)),
        "funding_source": commitment.funding_source,
        "status": commitment.status,
        "decision_event_id": commitment.decision_event_id,
        "notes": commitment.notes,
        "created_at": commitment.created_at,
        "updated_at": commitment.updated_at,
    }


def serialize_goal(goal: FinancialGoal) -> dict[str, Any]:
    target_amount = Decimal(goal.target_amount)
    reserved_balance = Decimal(goal.reserved_balance)
    return {
        "id": goal.id,
        "goal_key": goal.goal_key,
        "name": goal.name,
        "goal_type": goal.goal_type,
        "target_amount": _money(target_amount),
        "target_date": goal.target_date,
        "linked_fund_pool_id": goal.linked_fund_pool_id,
        "reserved_balance": _money(reserved_balance),
        "remaining_to_target": _money(target_amount - reserved_balance),
        "status": goal.status,
        "notes": goal.notes,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
    }


def serialize_budget_target(target: BudgetTarget) -> dict[str, Any]:
    return {
        "id": target.id,
        "target_key": target.target_key,
        "month": target.month,
        "target_scope": target.target_scope,
        "category_id": target.category_id,
        "fund_pool_id": target.fund_pool_id,
        "financial_goal_id": target.financial_goal_id,
        "target_amount": _money(Decimal(target.target_amount)),
        "warning_threshold_amount": _optional_money(target.warning_threshold_amount),
        "hard_cap_amount": _optional_money(target.hard_cap_amount),
        "review_threshold_amount": _optional_money(target.review_threshold_amount),
        "status": target.status,
        "notes": target.notes,
        "decision_event_id": target.decision_event_id,
        "created_at": target.created_at,
        "updated_at": target.updated_at,
    }


def _pool_summaries(session: Session, month: str) -> list[dict[str, Any]]:
    pools = session.scalars(
        select(FundPool)
        .where(FundPool.status == "active")
        .order_by(FundPool.sort_order, FundPool.name)
    ).all()
    commitments = _commitments_by_pool(session, month)
    spent = _spent_by_pool(session, month)
    summaries = []
    for pool in pools:
        commitment = commitments.get(pool.id, Decimal("0.00"))
        spent_amount = spent.get(pool.id, Decimal("0.00"))
        remaining = commitment - spent_amount
        summaries.append(
            {
                **serialize_fund_pool(pool),
                "commitment": _money(commitment),
                "spent": _money(spent_amount),
                "pool_remaining": _money(remaining),
                "status": _pool_status(spent_amount=spent_amount, remaining=remaining),
            }
        )
    return summaries


def _commitments_by_pool(session: Session, month: str) -> dict[str, Decimal]:
    commitments = session.scalars(
        select(MonthlyPoolCommitment).where(
            MonthlyPoolCommitment.month == month,
            MonthlyPoolCommitment.status == "active",
        )
    ).all()
    totals: dict[str, Decimal] = {}
    for commitment in commitments:
        totals[commitment.fund_pool_id] = totals.get(commitment.fund_pool_id, Decimal("0.00")) + Decimal(
            commitment.committed_amount
        )
    return totals


def _spent_by_pool(session: Session, month: str) -> dict[str, Decimal]:
    allocations = session.scalars(
        select(TransactionAllocation)
        .join(CanonicalTransaction, TransactionAllocation.canonical_transaction_id == CanonicalTransaction.id)
        .where(
            TransactionAllocation.status == "active",
            TransactionAllocation.fund_pool_id.is_not(None),
            CanonicalTransaction.posted_date.like(f"{month}-%"),
        )
    ).all()
    totals: dict[str, Decimal] = {}
    for allocation in allocations:
        if allocation.fund_pool_id is None:
            continue
        totals[allocation.fund_pool_id] = totals.get(allocation.fund_pool_id, Decimal("0.00")) + abs(
            Decimal(allocation.amount)
        )
    return totals


def _funded_this_month(session: Session, month: str, *, fallback: Decimal) -> Decimal:
    targets = session.scalars(
        select(BudgetTarget).where(
            BudgetTarget.month == month,
            BudgetTarget.target_scope == "monthly_funding",
            BudgetTarget.status == "active",
        )
    ).all()
    if not targets:
        return fallback
    return sum((Decimal(target.target_amount) for target in targets), Decimal("0.00"))


def _pool_status(*, spent_amount: Decimal, remaining: Decimal) -> str:
    if remaining < Decimal("0.00"):
        return f"Over by ${_money(abs(remaining))}"
    if spent_amount == Decimal("0.00"):
        return "Not started"
    return "On track"


def _record_decision(
    session: Session,
    *,
    target_type: str,
    target_id: str,
    decision_type: str,
    field_name: str,
    previous_value: Any,
    approved_value: Any,
    actor: str,
    actor_context: Optional[ActorContext],
    notes: Optional[str],
) -> DecisionEvent:
    event = DecisionEvent(
        target_type=target_type,
        target_id=target_id,
        decision_type=decision_type,
        field_name=field_name,
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


def _decision_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _required_name(value: str, code: str, message: str) -> str:
    name = value.strip()
    if not name:
        raise FundsError(code, message)
    return name


def _validate_goal_type(goal_type: str) -> None:
    if goal_type not in GOAL_TYPES:
        raise FundsError("invalid_goal_type", f"goal_type must be one of: {', '.join(sorted(GOAL_TYPES))}.")


def _ensure_unique_active_pool_name(session: Session, name: str, *, existing_id: Optional[str] = None) -> None:
    normalized = " ".join(name.casefold().split())
    pools = session.scalars(select(FundPool).where(FundPool.status == "active")).all()
    for pool in pools:
        if existing_id and pool.id == existing_id:
            continue
        if " ".join(pool.name.casefold().split()) == normalized:
            raise FundsError("fund_pool_name_exists", "An active fund pool with this name already exists.", 409)


def _next_pool_sort_order(session: Session) -> int:
    pools = session.scalars(select(FundPool)).all()
    return max((pool.sort_order for pool in pools), default=0) + 10


def _unique_key(
    session: Session,
    model: type[Any],
    column_name: str,
    seed: str,
    error_code: str,
    error_message: str,
) -> str:
    key = _slug(seed)
    if not key:
        raise FundsError("invalid_stable_key", "Stable key could not be derived.")
    column = getattr(model, column_name)
    if session.scalar(select(model).where(column == key)) is not None:
        raise FundsError(error_code, error_message, 409)
    return key


def _target_key_seed(scope: str, month: Optional[str]) -> str:
    return f"{scope}_{month or 'all_months'}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold())
    return slug.strip("_")


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _get_or_404(
    session: Session,
    model: type[Any],
    record_id: str,
    code: str,
    message: str,
) -> Any:
    record = session.get(model, record_id)
    if record is None:
        raise FundsError(code, message, 404)
    return record


def _non_negative_money(value: Decimal, code: str) -> Decimal:
    amount = Decimal(value)
    if amount < Decimal("0.00"):
        raise FundsError(code, "Amount must be greater than or equal to zero.")
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _optional_money(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return _money(Decimal(value))


def _decimal(value: str) -> Decimal:
    return Decimal(value)


def _money(value: Decimal) -> str:
    return str(Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def funds_close_readiness(session: Session, *, month: Optional[str] = None) -> dict[str, Any]:
    summary = funds_summary(session, month=month)
    spendable = summary["spendable"]
    pools = summary["pools"]
    negative_pool_remaining = [
        pool["pool_key"] for pool in pools if _decimal(pool["pool_remaining"]) < Decimal("0.00")
    ]
    verified_liquid = _decimal(spendable["verified_liquid_cash"])
    reserved = _decimal(spendable["reserved_goal_balance"])
    reserved_goals_exceed_liquid = reserved > verified_liquid
    negative_headline_spendable = _decimal(spendable["headline"]) < Decimal("0.00")
    commitments_by_pool = {pool["id"]: _decimal(pool["commitment"]) for pool in pools}
    missing_fund_commitments: list[str] = []
    for target in summary["budget_targets"]:
        if target.get("status") != "active" or not target.get("fund_pool_id"):
            continue
        pool_id = target["fund_pool_id"]
        if commitments_by_pool.get(pool_id, Decimal("0.00")) <= Decimal("0.00"):
            pool = next((item for item in pools if item["id"] == pool_id), None)
            if pool is not None:
                missing_fund_commitments.append(pool["pool_key"])
    missing_fund_commitments = sorted(set(missing_fund_commitments))
    blockers: list[str] = []
    if negative_pool_remaining:
        blockers.append("negative_pool_remaining")
    if reserved_goals_exceed_liquid:
        blockers.append("reserved_goals_exceed_liquid")
    if negative_headline_spendable:
        blockers.append("negative_headline_spendable")
    if missing_fund_commitments:
        blockers.append("missing_fund_commitments")
    return {
        "negative_pool_remaining": negative_pool_remaining,
        "reserved_goals_exceed_liquid": reserved_goals_exceed_liquid,
        "negative_headline_spendable": negative_headline_spendable,
        "missing_fund_commitments": missing_fund_commitments,
        "headline_spendable": spendable["headline"],
        "verified_liquid_cash": spendable["verified_liquid_cash"],
        "reserved_goal_balance": spendable["reserved_goal_balance"],
        "pool_summaries": [
            {
                "pool_key": pool["pool_key"],
                "name": pool["name"],
                "commitment": pool["commitment"],
                "spent": pool["spent"],
                "pool_remaining": pool["pool_remaining"],
            }
            for pool in pools
        ],
        "warnings": [],
        "blockers": blockers,
    }
