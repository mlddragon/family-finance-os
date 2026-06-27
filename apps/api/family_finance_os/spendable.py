from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from family_finance_os.models import (
    FinancialGoal,
    ImportedRow,
    ManualObligation,
    Setting,
    SourceAccount,
    SpendableBalanceSnapshot,
)
from family_finance_os.settings_service import CONFIRMED_SOURCE_PROFILE_STATUSES
from family_finance_os.source_profiles import get_source_profile, list_source_profiles


MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
MONEY_QUANT = Decimal("0.01")
DEFAULT_LIQUID_SOURCE_KEYS = ["alliant_checking", "alliant_savings"]


class SpendableError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def validate_month(month: Optional[str]) -> str:
    if month is None:
        return date.today().isoformat()[:7]
    if not MONTH_PATTERN.fullmatch(month):
        raise SpendableError("invalid_month", "month must use YYYY-MM format.")
    return month


def compute_spendable(
    session: Session,
    *,
    month: Optional[str] = None,
    include_provisional: Optional[bool] = None,
    persist_snapshot: bool = False,
    snapshot_type: str = "draft_close",
    monthly_close_id: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
) -> dict[str, Any]:
    target_month = validate_month(month)
    settings = _settings_lookup(session)
    include_provisional_value = (
        bool(include_provisional)
        if include_provisional is not None
        else bool(settings.get(("spendable", "spendable.include_provisional_default"), False))
    )

    liquid_source_keys = settings.get(
        ("spendable", "spendable.liquid_source_keys"),
        DEFAULT_LIQUID_SOURCE_KEYS,
    )
    card_source_keys = settings.get(
        ("spendable", "spendable.card_obligation_source_keys"),
        [
            profile.source_key
            for profile in list_source_profiles()
            if profile.account_type == "credit_card"
        ],
    )

    liquid = _liquid_summary(session, source_keys=list(liquid_source_keys), settings=settings)
    reserved_goal_balance = _reserved_goal_balance(session)
    manual_obligations_total = _manual_obligations_total(session, target_month)
    provisional_exposure = _provisional_exposure(session, target_month)
    card_summary = _card_obligation_summary(session, source_keys=list(card_source_keys), settings=settings)

    headline = liquid["verified_liquid_cash"] - reserved_goal_balance - manual_obligations_total
    if include_provisional_value:
        headline -= provisional_exposure

    warnings = [
        *liquid["warnings"],
        *card_summary["warnings"],
        *_headline_warnings(
            verified_liquid_cash=liquid["verified_liquid_cash"],
            reserved_goal_balance=reserved_goal_balance,
            headline=headline,
        ),
    ]
    confidence = _confidence(warnings, provisional_exposure=provisional_exposure)

    payload = {
        "month": target_month,
        "headline_spendable": _money(headline),
        "verified_liquid_cash": _money(liquid["verified_liquid_cash"]),
        "reserved_goal_balance": _money(reserved_goal_balance),
        "manual_obligations_total": _money(manual_obligations_total),
        "provisional_exposure": _money(provisional_exposure),
        "include_provisional": include_provisional_value,
        "card_obligation_total": _money(card_summary["card_obligation_total"]),
        "card_obligation_items": card_summary["card_obligation_items"],
        "confidence": confidence,
        "warnings": warnings,
        "source_details": liquid["source_details"] + card_summary["source_details"],
        "snapshot_id": None,
    }

    if persist_snapshot:
        snapshot = SpendableBalanceSnapshot(
            month=target_month,
            snapshot_type=snapshot_type,
            headline_spendable=headline,
            verified_liquid_cash=liquid["verified_liquid_cash"],
            reserved_goal_balance=reserved_goal_balance,
            manual_obligations_total=manual_obligations_total,
            provisional_exposure=provisional_exposure,
            include_provisional=include_provisional_value,
            card_obligation=card_summary["card_obligation_total"],
            confidence=confidence,
            input_summary_json=json.dumps(
                {
                    "warnings": warnings,
                    "source_details": payload["source_details"],
                    "card_obligation_items": card_summary["card_obligation_items"],
                },
                sort_keys=True,
            ),
            monthly_close_id=monthly_close_id,
            created_by_user_id=created_by_user_id,
        )
        session.add(snapshot)
        session.commit()
        payload["snapshot_id"] = snapshot.id

    return payload


def _settings_lookup(session: Session) -> dict[tuple[str, str], Any]:
    return {
        (setting.domain, setting.setting_key): json.loads(setting.value_json)
        for setting in session.scalars(select(Setting)).all()
    }


def _latest_accepted_rows_by_source(session: Session) -> dict[str, ImportedRow]:
    rows = session.scalars(
        select(ImportedRow)
        .join(ImportedRow.import_batch)
        .join(ImportedRow.source_account)
        .options(
            selectinload(ImportedRow.import_batch),
            selectinload(ImportedRow.source_account).selectinload(SourceAccount.source),
        )
        .where(ImportedRow.import_batch.has(status="accepted"))
        .order_by(ImportedRow.posted_date.desc(), ImportedRow.created_at.desc(), ImportedRow.id.desc())
    ).all()
    latest: dict[str, ImportedRow] = {}
    for row in rows:
        source = row.source_account.source
        if source.source_key not in latest:
            latest[source.source_key] = row
    return latest


def _liquid_summary(
    session: Session,
    *,
    source_keys: list[str],
    settings: dict[tuple[str, str], Any],
) -> dict[str, Any]:
    latest_rows = _latest_accepted_rows_by_source(session)
    total = Decimal("0.00")
    warnings: list[dict[str, str]] = []
    source_details: list[dict[str, Any]] = []

    for source_key in source_keys:
        if not _source_enabled(source_key, settings):
            continue
        row = latest_rows.get(source_key)
        display_name = _display_name(source_key, settings)
        if row is None:
            continue
        if row.balance is None:
            warnings.append(
                _warning(
                    "missing_liquid_balance",
                    f"{display_name} has accepted rows without a balance.",
                )
            )
            continue
        if not _source_confirmed(source_key, settings):
            warnings.append(
                _warning(
                    "unconfirmed_liquid_source",
                    f"{display_name} source profile is not owner-confirmed.",
                )
            )
            continue
        balance = Decimal(row.balance)
        total += balance
        source_details.append(
            _source_detail(
                source_key=source_key,
                display_name=display_name,
                role="liquid_cash",
                row=row,
                balance=balance,
                settings=settings,
            )
        )

    if total == Decimal("0.00"):
        warnings.append(
            _warning(
                "no_verified_liquid_cash",
                "No accepted confirmed liquid balances are available.",
                severity="blocking",
            )
        )

    return {
        "verified_liquid_cash": total,
        "warnings": warnings,
        "source_details": source_details,
    }


def _reserved_goal_balance(session: Session) -> Decimal:
    goals = session.scalars(select(FinancialGoal).where(FinancialGoal.status == "active")).all()
    return sum((Decimal(goal.reserved_balance) for goal in goals), Decimal("0.00"))


def _manual_obligations_total(session: Session, month: str) -> Decimal:
    obligations = session.scalars(
        select(ManualObligation).where(
            ManualObligation.status == "active",
            ManualObligation.linked_canonical_transaction_id.is_(None),
            ManualObligation.month == month,
        )
    ).all()
    return sum((Decimal(obligation.amount) for obligation in obligations), Decimal("0.00"))


def _provisional_exposure(session: Session, month: str) -> Decimal:
    rows = session.scalars(
        select(ImportedRow)
        .join(ImportedRow.import_batch)
        .where(
            ImportedRow.import_batch.has(status="accepted"),
            ImportedRow.posted_date.like(f"{month}-%"),
            ImportedRow.direction == "debit",
        )
    ).all()
    return sum((abs(Decimal(row.amount)) for row in rows), Decimal("0.00"))


def _card_obligation_summary(
    session: Session,
    *,
    source_keys: list[str],
    settings: dict[tuple[str, str], Any],
) -> dict[str, Any]:
    latest_rows = _latest_accepted_rows_by_source(session)
    total = Decimal("0.00")
    items: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    source_details: list[dict[str, Any]] = []

    for source_key in source_keys:
        if not _source_enabled(source_key, settings):
            continue
        row = latest_rows.get(source_key)
        if row is None:
            continue
        display_name = _display_name(source_key, settings)
        if row.balance is None:
            warnings.append(_warning("missing_card_balance", f"{display_name} is missing a card balance."))
            items.append(
                {
                    "card": display_name,
                    "owed": None,
                    "note": "Latest accepted row has no balance",
                    "source_key": source_key,
                    "status": "missing_balance",
                }
            )
            continue
        owed = abs(Decimal(row.balance))
        total += owed
        status = _source_confidence(row, settings)
        items.append(
            {
                "card": display_name,
                "owed": _money(owed),
                "note": "Pool remaining already reflects this",
                "source_key": source_key,
                "status": status,
                "latest_transaction_date": row.posted_date,
                "confidence": status,
            }
        )
        source_details.append(
            _source_detail(
                source_key=source_key,
                display_name=display_name,
                role="card_obligation",
                row=row,
                balance=owed,
                settings=settings,
            )
        )

    return {
        "card_obligation_total": total,
        "card_obligation_items": items,
        "warnings": warnings,
        "source_details": source_details,
    }


def _headline_warnings(
    *,
    verified_liquid_cash: Decimal,
    reserved_goal_balance: Decimal,
    headline: Decimal,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if reserved_goal_balance > verified_liquid_cash:
        warnings.append(
            _warning(
                "reserved_goals_exceed_liquid",
                "Reserved goal balance exceeds verified liquid cash.",
            )
        )
    if headline < Decimal("0.00"):
        warnings.append(_warning("negative_spendable", "Spendable balance is negative."))
    return warnings


def _source_enabled(source_key: str, settings: dict[tuple[str, str], Any]) -> bool:
    profile = get_source_profile(source_key)
    return bool(
        settings.get(("sources", f"sources.{source_key}.enabled"), profile.required)
        or settings.get(("sources", f"sources.{source_key}.required"), profile.required)
        or source_key in DEFAULT_LIQUID_SOURCE_KEYS
        or profile.account_type == "credit_card"
    )


def _source_confirmed(source_key: str, settings: dict[tuple[str, str], Any]) -> bool:
    profile = get_source_profile(source_key)
    status = settings.get(
        ("sources", f"sources.{source_key}.profile_confirmation_status"),
        profile.confirmation_status,
    )
    return status in CONFIRMED_SOURCE_PROFILE_STATUSES


def _display_name(source_key: str, settings: dict[tuple[str, str], Any]) -> str:
    profile = get_source_profile(source_key)
    return str(settings.get(("sources", f"sources.{source_key}.display_name"), profile.display_name))


def _source_detail(
    *,
    source_key: str,
    display_name: str,
    role: str,
    row: ImportedRow,
    balance: Decimal,
    settings: dict[tuple[str, str], Any],
) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "display_name": display_name,
        "role": role,
        "latest_transaction_date": row.posted_date,
        "balance": _money(balance),
        "confidence": _source_confidence(row, settings),
    }


def _source_confidence(row: ImportedRow, settings: dict[tuple[str, str], Any]) -> str:
    source_key = row.source_account.source.source_key
    threshold = int(
        settings.get(
            ("freshness", f"sources.{source_key}.freshness_threshold_days"),
            get_source_profile(source_key).freshness_threshold_days,
        )
    )
    latest_date = date.fromisoformat(row.posted_date)
    return "stale" if (date.today() - latest_date).days > threshold else "current"


def _confidence(warnings: list[dict[str, str]], *, provisional_exposure: Decimal) -> str:
    if any(warning["severity"] == "blocking" for warning in warnings):
        return "blocked"
    if any(warning["code"].startswith("stale") for warning in warnings):
        return "stale"
    if provisional_exposure > Decimal("0.00"):
        return "provisional"
    return "current"


def _warning(code: str, message: str, *, severity: str = "warning") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _money(value: Decimal) -> str:
    return str(Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
