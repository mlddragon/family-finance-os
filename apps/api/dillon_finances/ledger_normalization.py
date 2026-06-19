from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from dillon_finances.models import (
    CanonicalTransaction,
    ImportBatch,
    ImportedRow,
    SourceFile,
    ValidationFinding,
)


@dataclass(frozen=True)
class NormalizedLedgerRow:
    source_row_number: int
    posted_date: str
    effective_date: Optional[str]
    raw_description: str
    normalized_merchant: Optional[str]
    amount: str
    direction: str
    balance: Optional[str]
    initial_category: Optional[str]
    initial_subcategory: Optional[str]
    source_transaction_id: Optional[str]
    parser_version: str


def _stable_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decimal_string(value: str) -> str:
    return f"{Decimal(value):.2f}"


def _description_fingerprint(description: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", description.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def _direction(amount: Decimal, account_type: str) -> str:
    if amount == 0:
        return "neutral"
    if account_type == "credit_card":
        return "outflow" if amount > 0 else "inflow"
    return "inflow" if amount > 0 else "outflow"


def imported_row_hash(row: NormalizedLedgerRow) -> str:
    return _stable_sha256(asdict(row))


def imported_row_identity(
    source_account_id: str,
    source_file_hash: str,
    source_row_number: int,
    row_hash: str,
) -> str:
    digest = _stable_sha256(
        {
            "source_account_id": source_account_id,
            "source_file_hash": source_file_hash,
            "source_row_number": source_row_number,
            "row_hash": row_hash,
        }
    )
    return f"imported_row:{digest}"


def canonical_transaction_identity(
    row: NormalizedLedgerRow,
    source_account_id: str,
) -> str:
    digest = _stable_sha256(
        {
            "source_account_id": source_account_id,
            "posted_date": row.posted_date,
            "amount": row.amount,
            "source_transaction_id": row.source_transaction_id,
            "description_fingerprint": _description_fingerprint(row.raw_description),
        }
    )
    return f"canonical_transaction:{digest}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file_handle:
        return list(csv.DictReader(file_handle))


def _first_present(row: dict[str, str], *headers: str) -> Optional[str]:
    for header in headers:
        value = row.get(header)
        if value not in (None, ""):
            return value
    return None


def parse_source_file(source_file: SourceFile) -> list[NormalizedLedgerRow]:
    if source_file.source_account is None:
        return []

    account_type = source_file.source_account.account_type
    parser_version = source_file.parser_version or "unknown"
    normalized_rows: list[NormalizedLedgerRow] = []
    for row_number, row in enumerate(_read_csv(Path(source_file.stored_path)), start=2):
        transaction_date = _first_present(row, "Transaction Date", "Date")
        post_date = _first_present(row, "Post Date", "Date", "Transaction Date")
        raw_amount = _first_present(row, "Amount") or "0"
        amount = Decimal(raw_amount)
        raw_description = _first_present(row, "Description", "Memo", "Merchant") or ""
        balance = _first_present(row, "Balance")
        normalized_rows.append(
            NormalizedLedgerRow(
                source_row_number=row_number,
                posted_date=post_date or transaction_date or "",
                effective_date=transaction_date,
                raw_description=raw_description,
                normalized_merchant=_description_fingerprint(raw_description) or None,
                amount=_decimal_string(raw_amount),
                direction=_direction(amount, account_type),
                balance=_decimal_string(balance) if balance is not None else None,
                initial_category=_first_present(row, "Category"),
                initial_subcategory=_first_present(row, "Subcategory"),
                source_transaction_id=_first_present(
                    row,
                    "Transaction ID",
                    "Transaction Id",
                    "TransactionID",
                    "ID",
                ),
                parser_version=parser_version,
            )
        )
    return normalized_rows


def _canonical_for_row(
    session: Session,
    *,
    row: NormalizedLedgerRow,
    source_account_id: str,
) -> CanonicalTransaction:
    canonical_identity = canonical_transaction_identity(row, source_account_id)
    canonical = session.scalar(
        select(CanonicalTransaction).where(
            CanonicalTransaction.canonical_identity == canonical_identity
        )
    )
    if canonical is not None:
        return canonical

    canonical = CanonicalTransaction(
        canonical_identity=canonical_identity,
        source_account_id=source_account_id,
        posted_date=row.posted_date,
        amount=Decimal(row.amount),
        description_fingerprint=_description_fingerprint(row.raw_description),
        status="active",
    )
    session.add(canonical)
    session.flush()
    return canonical


def _open_duplicate_canonical_finding(
    session: Session,
    canonical: CanonicalTransaction,
) -> Optional[ValidationFinding]:
    return session.scalar(
        select(ValidationFinding).where(
            ValidationFinding.target_type == "canonical_transaction",
            ValidationFinding.target_id == canonical.id,
            ValidationFinding.code == "duplicate_canonical_candidate",
            ValidationFinding.status == "open",
        )
    )


def _mark_ambiguous_canonical(
    session: Session,
    *,
    canonical: CanonicalTransaction,
    import_batch_id: str,
) -> None:
    canonical.status = "ambiguous"
    if _open_duplicate_canonical_finding(session, canonical) is not None:
        return
    session.add(
        ValidationFinding(
            severity="blocking",
            code="duplicate_canonical_candidate",
            message=(
                "Multiple imported rows map to the same canonical transaction identity. "
                "Review is blocked until the identity can be disambiguated."
            ),
            target_type="canonical_transaction",
            target_id=canonical.id,
            status="open",
            resolution_event_id=import_batch_id,
        )
    )


def _canonical_imported_row_count(session: Session, canonical_id: str) -> int:
    return session.scalar(
        select(func.count(ImportedRow.id)).where(ImportedRow.canonical_transaction_id == canonical_id)
    ) or 0


def normalize_import_batch(session: Session, batch: ImportBatch) -> list[ImportedRow]:
    if batch.source_account is None:
        return []

    created_rows: list[ImportedRow] = []
    touched_canonical_ids: set[str] = set()
    for source_file in batch.source_files:
        if source_file.source_account is None:
            continue
        for normalized_row in parse_source_file(source_file):
            row_hash = imported_row_hash(normalized_row)
            row_identity = imported_row_identity(
                source_file.source_account.id,
                source_file.file_sha256,
                normalized_row.source_row_number,
                row_hash,
            )
            existing_imported_row = session.scalar(
                select(ImportedRow).where(ImportedRow.imported_row_identity == row_identity)
            )
            if existing_imported_row is not None:
                if existing_imported_row.canonical_transaction_id:
                    touched_canonical_ids.add(existing_imported_row.canonical_transaction_id)
                continue

            canonical = _canonical_for_row(
                session,
                row=normalized_row,
                source_account_id=source_file.source_account.id,
            )
            imported_row = ImportedRow(
                import_batch=batch,
                source_file=source_file,
                source_account=source_file.source_account,
                canonical_transaction=canonical,
                source_row_number=normalized_row.source_row_number,
                imported_row_hash=row_hash,
                imported_row_identity=row_identity,
                posted_date=normalized_row.posted_date,
                effective_date=normalized_row.effective_date,
                raw_description=normalized_row.raw_description,
                normalized_merchant=normalized_row.normalized_merchant,
                amount=Decimal(normalized_row.amount),
                direction=normalized_row.direction,
                balance=Decimal(normalized_row.balance) if normalized_row.balance else None,
                initial_category=normalized_row.initial_category,
                initial_subcategory=normalized_row.initial_subcategory,
                initial_review_flags_json=None,
                parser_version=normalized_row.parser_version,
            )
            session.add(imported_row)
            session.flush()
            created_rows.append(imported_row)
            touched_canonical_ids.add(canonical.id)

    for canonical_id in touched_canonical_ids:
        canonical = session.get(CanonicalTransaction, canonical_id)
        if canonical is None:
            continue
        if _canonical_imported_row_count(session, canonical.id) > 1:
            _mark_ambiguous_canonical(session, canonical=canonical, import_batch_id=batch.id)
            batch.validation_status = "blocked"

    return created_rows


def _imported_fact_payload(imported_row: ImportedRow) -> dict[str, Any]:
    source_file = imported_row.source_file
    return {
        "id": imported_row.id,
        "import_batch_id": imported_row.import_batch_id,
        "source_file_id": imported_row.source_file_id,
        "source_filename": source_file.original_filename if source_file else None,
        "source_row_number": imported_row.source_row_number,
        "posted_date": imported_row.posted_date,
        "effective_date": imported_row.effective_date,
        "raw_description": imported_row.raw_description,
        "normalized_merchant": imported_row.normalized_merchant,
        "amount": _decimal_string(str(imported_row.amount)),
        "direction": imported_row.direction,
        "initial_category": imported_row.initial_category,
        "initial_subcategory": imported_row.initial_subcategory,
        "parser_version": imported_row.parser_version,
    }


def _transaction_validation_status(canonical: CanonicalTransaction) -> str:
    if canonical.status == "ambiguous":
        return "blocked"
    return "ready_for_review"


def serialize_transaction(canonical: CanonicalTransaction, *, include_facts: bool = False) -> dict[str, Any]:
    imported_rows = sorted(
        canonical.imported_rows,
        key=lambda imported_row: (imported_row.posted_date, imported_row.source_row_number),
    )
    primary_fact = imported_rows[0] if imported_rows else None
    payload: dict[str, Any] = {
        "id": canonical.id,
        "canonical_identity": canonical.canonical_identity,
        "posted_date": canonical.posted_date,
        "amount": _decimal_string(str(canonical.amount)),
        "description_fingerprint": canonical.description_fingerprint,
        "status": canonical.status,
        "validation_status": _transaction_validation_status(canonical),
        "review_status": "unreviewed",
        "imported_fact_count": len(imported_rows),
        "source_account_id": canonical.source_account_id,
        "raw_description": primary_fact.raw_description if primary_fact else None,
        "normalized_merchant": primary_fact.normalized_merchant if primary_fact else None,
        "initial_category": primary_fact.initial_category if primary_fact else None,
    }
    if include_facts:
        payload["imported_facts"] = [_imported_fact_payload(row) for row in imported_rows]
    return payload


def list_transactions(session: Session) -> list[dict[str, Any]]:
    canonicals = session.scalars(
        select(CanonicalTransaction)
        .options(selectinload(CanonicalTransaction.imported_rows).selectinload(ImportedRow.source_file))
        .order_by(CanonicalTransaction.posted_date.desc(), CanonicalTransaction.created_at.desc())
    ).all()
    return [serialize_transaction(canonical) for canonical in canonicals]


def get_transaction(session: Session, transaction_id: str) -> Optional[dict[str, Any]]:
    canonical = session.scalar(
        select(CanonicalTransaction)
        .where(CanonicalTransaction.id == transaction_id)
        .options(selectinload(CanonicalTransaction.imported_rows).selectinload(ImportedRow.source_file))
    )
    if canonical is None:
        return None
    return serialize_transaction(canonical, include_facts=True)
