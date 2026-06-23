from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")


def parse_ledger_date(value: str) -> date:
    cleaned = value.strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported ledger date: {value!r}")


def parse_money(value: str) -> Decimal:
    cleaned = value.strip()
    if not cleaned:
        raise InvalidOperation("empty money value")

    is_parenthetical_negative = cleaned.startswith("(") and cleaned.endswith(")")
    if is_parenthetical_negative:
        cleaned = cleaned[1:-1].strip()

    cleaned = cleaned.replace("$", "").replace(",", "")
    amount = Decimal(cleaned)
    return -amount if is_parenthetical_negative else amount


def decimal_string(value: Decimal) -> str:
    return f"{value:.2f}"
