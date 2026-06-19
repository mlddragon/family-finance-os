from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from dillon_finances.models import (
    ImportBatch,
    Source,
    SourceAccount,
    SourceFile,
    ValidationFinding,
)
from dillon_finances.ledger_normalization import normalize_import_batch
from dillon_finances.source_profiles import SourceProfile, list_source_profiles


VALIDATION_CODES = {
    "file_missing",
    "file_unreadable",
    "file_empty",
    "unsupported_file_type",
    "schema_mismatch",
    "ambiguous_source",
    "source_account_unconfirmed",
    "date_parse_failed",
    "amount_parse_failed",
    "amount_precision_invalid",
    "amount_sign_unexpected",
    "row_count_mismatch",
    "duplicate_imported_row",
    "duplicate_canonical_candidate",
    "overlapping_export",
    "source_stale",
    "required_source_missing",
    "batch_validation_incomplete",
}

BLOCKING = "blocking"
WARNING = "warning"
INFO = "info"

SUPPORTED_EXTENSIONS = {".csv"}
REJECTED_EXTENSIONS = {".xls", ".xlsx", ".pdf", ".env", ".key", ".pem", ".p12", ".pfx"}


class ImportValidationError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ParsedCsv:
    headers: list[str]
    rows: list[dict[str, str]]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unknown_source(session: Session) -> Source:
    source = session.scalar(select(Source).where(Source.source_key == "unknown"))
    if source is None:
        source = Source(source_key="unknown", display_name="Unknown Source", source_type="unknown")
        session.add(source)
        session.flush()
    return source


def _source_for_profile(session: Session, profile: SourceProfile) -> Source:
    source = session.scalar(select(Source).where(Source.source_key == profile.source_key))
    if source is None:
        source = Source(
            source_key=profile.source_key,
            display_name=profile.display_name,
            source_type=profile.account_type,
        )
        session.add(source)
        session.flush()
    return source


def _account_for_profile(session: Session, source: Source, profile: SourceProfile) -> SourceAccount:
    account_key = f"{profile.source_key}_default"
    account = session.scalar(
        select(SourceAccount).where(
            SourceAccount.source_id == source.id,
            SourceAccount.account_key == account_key,
        )
    )
    if account is None:
        account = SourceAccount(
            source=source,
            account_key=account_key,
            display_name=profile.display_name,
            account_type=profile.account_type,
        )
        session.add(account)
        session.flush()
    return account


def serialize_import_batch(batch: ImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "status": batch.status,
        "validation_status": batch.validation_status,
        "row_count": batch.row_count,
        "source_key": batch.source.source_key if batch.source else None,
        "source_files": [_serialize_source_file(source_file) for source_file in batch.source_files],
    }


def _serialize_source_file(source_file: SourceFile) -> dict[str, Any]:
    return {
        "id": source_file.id,
        "original_filename": source_file.original_filename,
        "stored_path": source_file.stored_path,
        "file_sha256": source_file.file_sha256,
        "byte_size": source_file.byte_size,
        "validation_status": source_file.validation_status,
        "row_count": source_file.row_count,
        "parser_version": source_file.parser_version,
    }


def serialize_finding(finding: ValidationFinding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "severity": finding.severity,
        "code": finding.code,
        "message": finding.message,
        "target_type": finding.target_type,
        "target_id": finding.target_id,
        "status": finding.status,
        "created_at": finding.created_at,
    }


def _create_finding(
    session: Session,
    *,
    severity: str,
    code: str,
    message: str,
    target_type: str,
    target_id: Optional[str],
) -> ValidationFinding:
    finding = ValidationFinding(
        severity=severity,
        code=code,
        message=message,
        target_type=target_type,
        target_id=target_id,
        status="open",
    )
    session.add(finding)
    return finding


def _clear_batch_findings(session: Session, batch_id: str) -> None:
    findings = session.scalars(
        select(ValidationFinding).where(
            ValidationFinding.target_type == "import_batch",
            ValidationFinding.target_id == batch_id,
            ValidationFinding.status == "open",
        )
    ).all()
    for finding in findings:
        finding.status = "resolved"


def _parse_csv(path: Path) -> ParsedCsv:
    try:
        text = path.read_text()
    except OSError as exc:
        raise ImportValidationError("file_unreadable", f"Could not read file {path.name}") from exc

    if not text.strip():
        raise ImportValidationError("file_empty", f"File {path.name} is empty")

    reader = csv.DictReader(text.splitlines())
    headers = list(reader.fieldnames or [])
    if not headers:
        raise ImportValidationError("file_empty", f"File {path.name} has no headers")
    return ParsedCsv(headers=headers, rows=list(reader))


def _detect_profile(headers: list[str]) -> Optional[SourceProfile]:
    matches = [profile for profile in list_source_profiles() if list(profile.expected_headers) == headers]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ImportValidationError("ambiguous_source", "Headers match multiple source profiles")
    return None


def _scan_file(session: Session, path: Path) -> ImportBatch:
    file_hash = sha256_file(path)
    unknown = _unknown_source(session)
    batch = ImportBatch(source=unknown, status="detected", validation_status="pending")
    session.add(batch)
    session.flush()
    source_file = SourceFile(
        source=unknown,
        import_batch=batch,
        original_filename=path.name,
        stored_path=str(path),
        file_sha256=file_hash,
        byte_size=path.stat().st_size,
        validation_status="pending",
        parser_version=None,
    )
    session.add(source_file)
    session.commit()
    session.refresh(batch)
    return batch


def scan_inbox(session: Session, data_root: Path) -> list[ImportBatch]:
    inbox = data_root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    batches: list[ImportBatch] = []
    for path in sorted(inbox.iterdir()):
        if path.is_file():
            existing = session.scalar(select(SourceFile).where(SourceFile.stored_path == str(path)))
            if existing is None:
                batches.append(_scan_file(session, path))
            else:
                batches.append(existing.import_batch)
    return batches


def save_upload(session: Session, data_root: Path, filename: str, content: bytes) -> ImportBatch:
    extension = Path(filename).suffix.lower()
    if extension in REJECTED_EXTENSIONS or extension not in SUPPORTED_EXTENSIONS:
        raise ImportValidationError("unsupported_file_type", f"{extension or 'file'} is not supported")
    inbox_path = data_root / "inbox" / Path(filename).name
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_bytes(content)
    return _scan_file(session, inbox_path)


def _validate_rows(
    session: Session,
    *,
    batch: ImportBatch,
    source_file: SourceFile,
    profile: SourceProfile,
    parsed: ParsedCsv,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    posted_dates: list[date] = []
    amount_header = "Amount"
    date_header = "Transaction Date" if "Transaction Date" in parsed.headers else "Date"

    for row_number, row in enumerate(parsed.rows, start=2):
        raw_date = row.get(date_header, "")
        try:
            posted_dates.append(datetime.strptime(raw_date, "%Y-%m-%d").date())
        except ValueError:
            findings.append(
                _create_finding(
                    session,
                    severity=BLOCKING,
                    code="date_parse_failed",
                    message=f"Row {row_number} has an invalid date.",
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )

        raw_amount = row.get(amount_header, "")
        try:
            amount = Decimal(raw_amount)
            if amount.as_tuple().exponent < -2:
                findings.append(
                    _create_finding(
                        session,
                        severity=BLOCKING,
                        code="amount_precision_invalid",
                        message=f"Row {row_number} has more than two amount decimals.",
                        target_type="import_batch",
                        target_id=batch.id,
                    )
                )
            if profile.amount_sign_policy == "charges_positive_payments_negative" and amount == 0:
                findings.append(
                    _create_finding(
                        session,
                        severity=WARNING,
                        code="amount_sign_unexpected",
                        message=f"Row {row_number} has a zero amount.",
                        target_type="import_batch",
                        target_id=batch.id,
                    )
                )
        except InvalidOperation:
            findings.append(
                _create_finding(
                    session,
                    severity=BLOCKING,
                    code="amount_parse_failed",
                    message=f"Row {row_number} has an invalid amount.",
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )

    if not parsed.rows:
        findings.append(
            _create_finding(
                session,
                severity=BLOCKING,
                code="file_empty",
                message="File contains no data rows.",
                target_type="import_batch",
                target_id=batch.id,
            )
        )

    if source_file.row_count is not None and source_file.row_count != len(parsed.rows):
        findings.append(
            _create_finding(
                session,
                severity=BLOCKING,
                code="row_count_mismatch",
                message="Stored row count differs from parsed row count.",
                target_type="import_batch",
                target_id=batch.id,
            )
        )

    source_file.row_count = len(parsed.rows)
    batch.row_count = len(parsed.rows)
    if posted_dates:
        batch.transaction_date_min = min(posted_dates).isoformat()
        batch.transaction_date_max = max(posted_dates).isoformat()

    accepted_same_hash = session.scalars(
        select(SourceFile).where(
            SourceFile.file_sha256 == source_file.file_sha256,
            SourceFile.validation_status == "accepted",
            SourceFile.id != source_file.id,
        )
    ).all()
    if accepted_same_hash:
        findings.append(
            _create_finding(
                session,
                severity=WARNING,
                code="duplicate_imported_row",
                message="This file hash was already accepted. No silent dedupe was applied.",
                target_type="import_batch",
                target_id=batch.id,
            )
        )

    if batch.transaction_date_min and batch.transaction_date_max:
        overlap = session.scalars(
            select(ImportBatch).where(
                ImportBatch.source_id == batch.source_id,
                ImportBatch.status == "accepted",
                ImportBatch.id != batch.id,
                ImportBatch.transaction_date_min <= batch.transaction_date_max,
                ImportBatch.transaction_date_max >= batch.transaction_date_min,
            )
        ).all()
        if overlap:
            findings.append(
                _create_finding(
                    session,
                    severity=WARNING,
                    code="overlapping_export",
                    message="This export overlaps an already accepted import batch.",
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )

        latest_date = datetime.strptime(batch.transaction_date_max, "%Y-%m-%d").date()
        if (date.today() - latest_date).days > profile.freshness_threshold_days:
            findings.append(
                _create_finding(
                    session,
                    severity=WARNING,
                    code="source_stale",
                    message="This source appears stale against its freshness threshold.",
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )

    return findings


def validate_import_batch(session: Session, batch_id: str) -> dict[str, Any]:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise ImportValidationError("file_missing", "Import batch not found", status_code=404)
    _clear_batch_findings(session, batch.id)

    findings: list[ValidationFinding] = []
    for source_file in batch.source_files:
        path = Path(source_file.stored_path)
        if not path.exists():
            findings.append(
                _create_finding(
                    session,
                    severity=BLOCKING,
                    code="file_missing",
                    message=f"{source_file.original_filename} is missing.",
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )
            continue
        extension = path.suffix.lower()
        if extension in REJECTED_EXTENSIONS or extension not in SUPPORTED_EXTENSIONS:
            findings.append(
                _create_finding(
                    session,
                    severity=BLOCKING,
                    code="unsupported_file_type",
                    message=f"{extension or 'file'} is not supported.",
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )
            continue
        try:
            parsed = _parse_csv(path)
            profile = _detect_profile(parsed.headers)
        except ImportValidationError as exc:
            findings.append(
                _create_finding(
                    session,
                    severity=BLOCKING,
                    code=exc.code,
                    message=exc.message,
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )
            continue

        if profile is None:
            findings.append(
                _create_finding(
                    session,
                    severity=BLOCKING,
                    code="schema_mismatch",
                    message="File headers do not match an approved v1 source profile.",
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )
            continue

        source = _source_for_profile(session, profile)
        account = _account_for_profile(session, source, profile)
        batch.source = source
        batch.source_account = account
        batch.parser_version = profile.parser_version
        source_file.source = source
        source_file.source_account = account
        source_file.parser_version = profile.parser_version
        findings.extend(
            _validate_rows(
                session,
                batch=batch,
                source_file=source_file,
                profile=profile,
                parsed=parsed,
            )
        )

    has_blocking = any(finding.severity == BLOCKING for finding in findings)
    batch.validation_status = "blocked" if has_blocking else "passed_with_warnings" if findings else "passed"
    batch.status = "validated"
    for source_file in batch.source_files:
        source_file.validation_status = batch.validation_status
    session.commit()
    session.refresh(batch)
    return {
        **serialize_import_batch(batch),
        "findings": [serialize_finding(finding) for finding in findings],
    }


def list_validation_findings(session: Session) -> list[dict[str, Any]]:
    findings = session.scalars(select(ValidationFinding).order_by(ValidationFinding.created_at)).all()
    return [serialize_finding(finding) for finding in findings]


def _open_findings(session: Session, batch_id: str) -> list[ValidationFinding]:
    return session.scalars(
        select(ValidationFinding).where(
            ValidationFinding.target_type == "import_batch",
            ValidationFinding.target_id == batch_id,
            ValidationFinding.status == "open",
        )
    ).all()


def _quarantine_batch(data_root: Path, batch: ImportBatch, findings: list[ValidationFinding]) -> None:
    quarantine_dir = data_root / "quarantine" / batch.id
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    reason_path = quarantine_dir / "validation.reason.json"
    reason_path.write_text(
        json.dumps(
            {
                "import_batch_id": batch.id,
                "findings": [serialize_finding(finding) for finding in findings],
            },
            indent=2,
            sort_keys=True,
        )
    )
    for source_file in batch.source_files:
        source_path = Path(source_file.stored_path)
        if source_path.exists():
            destination = quarantine_dir / source_file.original_filename
            if source_path.resolve() != destination.resolve():
                shutil.move(str(source_path), str(destination))
            source_file.stored_path = str(destination)
            source_file.validation_status = "blocked"
    batch.status = "blocked"
    batch.validation_status = "blocked"


def accept_import_batch(
    session: Session,
    data_root: Path,
    batch_id: str,
    *,
    acknowledge_warnings: bool = False,
) -> dict[str, Any]:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise ImportValidationError("file_missing", "Import batch not found", status_code=404)

    findings = _open_findings(session, batch.id)
    if batch.validation_status == "pending":
        finding = _create_finding(
            session,
            severity=BLOCKING,
            code="batch_validation_incomplete",
            message="Batch must be validated before acceptance.",
            target_type="import_batch",
            target_id=batch.id,
        )
        session.commit()
        raise ImportValidationError(finding.code, finding.message, status_code=409)

    blocking_findings = [finding for finding in findings if finding.severity == BLOCKING]
    if blocking_findings:
        _quarantine_batch(data_root, batch, blocking_findings)
        session.commit()
        raise ImportValidationError(
            "blocking_validation_findings",
            "Blocking validation findings prevent acceptance.",
            status_code=409,
        )

    warning_findings = [finding for finding in findings if finding.severity == WARNING]
    if warning_findings and not acknowledge_warnings:
        raise ImportValidationError(
            "warning_acknowledgment_required",
            "Warnings require explicit acknowledgment before acceptance.",
            status_code=409,
        )

    year = batch.transaction_date_max[:4] if batch.transaction_date_max else "unknown-year"
    source_key = batch.source.source_key if batch.source else "unknown"
    raw_dir = data_root / "raw" / source_key / year / batch.id
    raw_dir.mkdir(parents=True, exist_ok=True)
    for source_file in batch.source_files:
        source_path = Path(source_file.stored_path)
        destination = raw_dir / source_file.original_filename
        if source_path.exists() and source_path.resolve() != destination.resolve():
            shutil.move(str(source_path), str(destination))
        source_file.stored_path = str(destination)
        source_file.validation_status = "accepted"
    batch.status = "accepted"
    batch.validation_status = "accepted_with_warnings" if warning_findings else "accepted"
    normalize_import_batch(session, batch)
    session.commit()
    session.refresh(batch)
    return serialize_import_batch(batch)
