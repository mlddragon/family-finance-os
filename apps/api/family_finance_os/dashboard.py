from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from family_finance_os.funds import FundsError, funds_summary, validate_month
from family_finance_os.net_worth import net_worth_summary
from family_finance_os.reporting import (
    _review_backlog_summary,
    cashflow_trend,
    category_spend_for_month,
    close_readiness,
    default_month,
)


class DashboardError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def validate_dashboard_month(session: Session, month: Optional[str]) -> str:
    if month is None:
        return default_month(session)
    try:
        return validate_month(month)
    except FundsError as exc:
        raise DashboardError(exc.code, exc.message, status_code=422) from exc


def dashboard_summary(session: Session, *, month: Optional[str] = None) -> dict[str, Any]:
    target_month = validate_dashboard_month(session, month)
    readiness = close_readiness(session, month=target_month)
    funds = funds_summary(session, month=target_month)
    review = _review_backlog_summary(session)
    reviewed = review["review_counts"].get("reviewed", 0)
    total = review["total_transactions"] or 0
    reviewed_percent = "0.00" if total == 0 else f"{(reviewed / total) * 100:.2f}"
    freshness = "stale" if readiness["legacy_blockers"] else "current"
    confidence = funds["spendable"].get("confidence") or "unknown"
    return {
        "month": target_month,
        "freshness": freshness,
        "confidence": confidence,
        "reviewed_percent": reviewed_percent,
        "review_backlog": review,
        "readiness": readiness,
        "spendable": funds["spendable"],
        "commitment_health": funds["commitment_health"],
    }


def dashboard_cashflow(session: Session, *, months: int = 6, anchor_month: Optional[str] = None) -> dict[str, Any]:
    anchor = validate_dashboard_month(session, anchor_month)
    if months < 1 or months > 24:
        raise DashboardError("invalid_dashboard_months", "Months must be between 1 and 24.", status_code=422)
    return cashflow_trend(session, months=months, anchor_month=anchor)


def dashboard_category_spend(session: Session, *, month: Optional[str] = None) -> dict[str, Any]:
    target_month = validate_dashboard_month(session, month)
    return category_spend_for_month(session, target_month)


def dashboard_pool_progress(session: Session, *, month: Optional[str] = None) -> dict[str, Any]:
    target_month = validate_dashboard_month(session, month)
    funds = funds_summary(session, month=target_month)
    pools = []
    for pool in funds["pools"]:
        commitment = Decimal(pool["commitment"])
        spent = Decimal(pool["spent"])
        target_amount = commitment if commitment > Decimal("0.00") else spent
        progress_percent = "0.00"
        if target_amount > Decimal("0.00"):
            progress_percent = f"{min((spent / target_amount) * 100, Decimal('999.99')):.2f}"
        pools.append(
            {
                "pool_key": pool["pool_key"],
                "name": pool["name"],
                "commitment": pool["commitment"],
                "spent": pool["spent"],
                "pool_remaining": pool["pool_remaining"],
                "progress_percent": progress_percent,
                "over_target": Decimal(pool["pool_remaining"]) < Decimal("0.00"),
                "status": pool["status"],
            }
        )
    goals = [
        {
            "goal_key": goal["goal_key"],
            "name": goal["name"],
            "target_amount": goal["target_amount"],
            "reserved_balance": goal["reserved_balance"],
            "remaining_to_target": goal["remaining_to_target"],
        }
        for goal in funds["goals"]
    ]
    return {"month": target_month, "pools": pools, "goals": goals}


def dashboard_net_worth(
    session: Session,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_estimates: bool = False,
) -> dict[str, Any]:
    _ = date_from, date_to
    summary = net_worth_summary(session, include_estimates=include_estimates)
    return {
        "as_of": date.today().isoformat(),
        "include_estimates": include_estimates,
        "view_label": "includes_estimates" if include_estimates else "actual_only",
        "summary": summary,
        "warning": None
        if include_estimates
        else "Estimated asset values are excluded from Spendable balance and default net worth.",
    }


class DashboardQuery(BaseModel):
    month: Optional[str] = None
    months: int = Field(default=6, ge=1, le=24)
    from_date: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None
    include_estimates: bool = False
