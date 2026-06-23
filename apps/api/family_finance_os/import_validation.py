from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from decimal import InvalidOperation
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_from_json, actor_context_to_json, derive_actor_context
from family_finance_os.models import (
    ImportBatch,
    ImportBatchEvent,
    Setting,
    Source,
    SourceAccount,
    SourceFile,
    ValidationFinding,
    ValidationFindingEvent,
    utc_now_iso,
)
from family_finance_os.ledger_normalization import normalize_import_batch
from family_finance_os.ledger_parsing import parse_ledger_date, parse_money
from family_finance_os.source_profiles import SourceProfile, get_source_profile, list_source_profiles


VALIDATION_CODES = {
    "file_missing",
    "file_unreadable",
    "file_empty",
    "file_integrity_mismatch",
    "file_not_regular",
    "unsafe_filename",
    "unsupported_file_type",
    "schema_mismatch",
    "ambiguous_source",
    "source_account_unconfirmed",
    "storage_path_unsafe",
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
    "active_blocking_validation_finding",
    "validation_finding_not_found",
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
        "storage_status": source_file.storage_status,
        "destroyed_at": source_file.destroyed_at,
        "destroyed_by": source_file.destroyed_by,
        "destroyed_reason": source_file.destroyed_reason,
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


def serialize_finding_event(event: ValidationFindingEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "validation_finding_id": event.validation_finding_id,
        "event_type": event.event_type,
        "actor": event.actor,
        "actor_context": actor_context_from_json(event.actor_context_json),
        "notes": event.notes,
        "created_at": event.created_at,
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


def _create_open_finding_once(
    session: Session,
    *,
    severity: str,
    code: str,
    message: str,
    target_type: str,
    target_id: Optional[str],
) -> ValidationFinding:
    existing = session.scalar(
        select(ValidationFinding).where(
            ValidationFinding.code == code,
            ValidationFinding.target_type == target_type,
            ValidationFinding.target_id == target_id,
            ValidationFinding.status == "open",
        )
    )
    if existing is not None:
        return existing
    return _create_finding(
        session,
        severity=severity,
        code=code,
        message=message,
        target_type=target_type,
        target_id=target_id,
    )


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


def _profile_filename_tokens(profile: SourceProfile) -> set[str]:
    return {
        profile.source_key,
        profile.source_key.replace("_", "-"),
        profile.display_name.lower().replace(" ", "_"),
        profile.display_name.lower().replace(" ", "-"),
    }


def _headers_match_profile(headers: list[str], profile: SourceProfile) -> bool:
    expected_headers = list(profile.expected_headers)
    allowed_headers = set(profile.expected_headers) | set(profile.optional_headers)
    if any(header not in allowed_headers for header in headers):
        return False
    required_headers_in_file = [header for header in headers if header in profile.expected_headers]
    return required_headers_in_file == expected_headers


def _detect_profile(headers: list[str], *, filename: str = "", source_key_hint: Optional[str] = None) -> Optional[SourceProfile]:
    if source_key_hint:
        try:
            hinted_profile = get_source_profile(source_key_hint)
        except KeyError as exc:
            raise ImportValidationError(
                "source_account_unconfirmed",
                "Selected source profile is not approved for v1 import.",
            ) from exc
        return hinted_profile if _headers_match_profile(headers, hinted_profile) else None

    matches = [profile for profile in list_source_profiles() if _headers_match_profile(headers, profile)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        filename_key = filename.lower()
        hinted_matches = [
            profile
            for profile in matches
            if any(token in filename_key for token in _profile_filename_tokens(profile))
        ]
        if len(hinted_matches) == 1:
            return hinted_matches[0]
        raise ImportValidationError("ambiguous_source", "Headers match multiple source profiles")
    return None


def _scan_file(
    session: Session,
    path: Path,
    *,
    source_key_hint: Optional[str] = None,
    original_filename: Optional[str] = None,
) -> ImportBatch:
    file_hash = sha256_file(path)
    if source_key_hint:
        try:
            profile = get_source_profile(source_key_hint)
        except KeyError as exc:
            raise ImportValidationError(
                "source_account_unconfirmed",
                "Selected source profile is not approved for v1 import.",
                status_code=400,
            ) from exc
        source = _source_for_profile(session, profile)
        source_account = _account_for_profile(session, source, profile)
        parser_version = profile.parser_version
    else:
        source = _unknown_source(session)
        source_account = None
        parser_version = None

    batch = ImportBatch(
        source=source,
        source_account=source_account,
        status="detected",
        validation_status="pending",
        parser_version=parser_version,
    )
    session.add(batch)
    session.flush()
    source_file = SourceFile(
        source=source,
        source_account=source_account,
        import_batch=batch,
        original_filename=original_filename or path.name,
        stored_path=str(path),
        file_sha256=file_hash,
        byte_size=path.stat().st_size,
        validation_status="pending",
        parser_version=parser_version,
    )
    session.add(source_file)
    session.commit()
    session.refresh(batch)
    return batch


def scan_inbox(session: Session, data_root: Path) -> list[ImportBatch]:
    inbox = data_root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    _sync_inbox_file_regular_findings(session, inbox)
    batches: list[ImportBatch] = []
    for path in sorted(inbox.iterdir()):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            _create_open_finding_once(
                session,
                severity=BLOCKING,
                code="file_not_regular",
                message=_non_regular_source_message(path.name),
                target_type="inbox_file",
                target_id=path.name,
            )
            continue
        if path.is_file():
            existing = session.scalar(select(SourceFile).where(SourceFile.stored_path == str(path)))
            if existing is None:
                batches.append(_scan_file(session, path))
            else:
                batches.append(existing.import_batch)
    session.commit()
    return batches


def _safe_upload_filename(filename: str) -> str:
    if not filename or filename in {".", ".."} or "\x00" in filename:
        raise ImportValidationError("unsafe_filename", "Uploaded filename must be a plain file name.")
    if PurePath(filename).name != filename or PureWindowsPath(filename).name != filename:
        raise ImportValidationError("unsafe_filename", "Uploaded filename must not include path components.")
    return filename


def _stored_path_has_source_file_record(session: Session, path: Path) -> bool:
    return session.scalar(select(SourceFile).where(SourceFile.stored_path == str(path))) is not None


def _unique_upload_path(session: Session, data_root: Path, safe_filename: str) -> Path:
    inbox = data_root / "inbox"
    candidate = inbox / safe_filename
    if candidate.is_symlink() or (candidate.exists() and not candidate.is_file()):
        raise ImportValidationError(
            "file_not_regular",
            _non_regular_source_message(safe_filename),
            status_code=409,
        )
    if not candidate.exists() and not _stored_path_has_source_file_record(session, candidate):
        return candidate

    stem = candidate.stem or "uploaded-file"
    suffix = candidate.suffix
    for _ in range(100):
        replacement = inbox / f"{stem}-{uuid4().hex[:8]}{suffix}"
        if not replacement.exists() and not _stored_path_has_source_file_record(session, replacement):
            return replacement
    raise ImportValidationError("unsafe_filename", "Could not allocate a safe upload storage path.", status_code=409)


def save_upload(
    session: Session,
    data_root: Path,
    filename: str,
    content: bytes,
    *,
    source_key_hint: Optional[str] = None,
) -> ImportBatch:
    safe_filename = _safe_upload_filename(filename)
    extension = Path(safe_filename).suffix.lower()
    if extension in REJECTED_EXTENSIONS or extension not in SUPPORTED_EXTENSIONS:
        raise ImportValidationError("unsupported_file_type", f"{extension or 'file'} is not supported")
    inbox_path = _unique_upload_path(session, data_root, safe_filename)
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    if inbox_path.is_symlink() or (inbox_path.exists() and not inbox_path.is_file()):
        raise ImportValidationError(
            "file_not_regular",
            _non_regular_source_message(safe_filename),
            status_code=409,
        )
    inbox_path.write_bytes(content)
    return _scan_file(session, inbox_path, source_key_hint=source_key_hint, original_filename=safe_filename)


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
            posted_dates.append(parse_ledger_date(raw_date))
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
            amount = parse_money(raw_amount)
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
            if profile.amount_sign_policy.startswith("charges_") and amount == 0:
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


def _is_regular_source_file(path: Path) -> bool:
    return not path.is_symlink() and path.is_file()


def _source_file_integrity_matches(path: Path, source_file: SourceFile) -> bool:
    return path.stat().st_size == source_file.byte_size and sha256_file(path) == source_file.file_sha256


def _source_file_integrity_message(filename: str) -> str:
    return f"{filename} no longer matches the file hash and size recorded at detection."


def _storage_path_unsafe_message(path: Path) -> str:
    return f"Storage path {path.name} is not a safe directory inside DATA_ROOT."


def _ensure_safe_storage_directory(data_root: Path, directory: Path) -> Path:
    resolved_data_root = data_root.resolve()
    try:
        relative_parts = directory.relative_to(data_root).parts
    except ValueError as exc:
        raise ImportValidationError(
            "storage_path_unsafe",
            _storage_path_unsafe_message(directory),
            status_code=409,
        ) from exc

    current = data_root
    for part in relative_parts[:-1]:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise ImportValidationError(
                "storage_path_unsafe",
                _storage_path_unsafe_message(current),
                status_code=409,
            )
        current.mkdir(exist_ok=True)
        if not current.resolve().is_relative_to(resolved_data_root):
            raise ImportValidationError(
                "storage_path_unsafe",
                _storage_path_unsafe_message(current),
                status_code=409,
            )

    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ImportValidationError(
            "storage_path_unsafe",
            _storage_path_unsafe_message(directory),
            status_code=409,
        )
    directory.mkdir(exist_ok=True)
    if directory.is_symlink() or not directory.resolve().is_relative_to(resolved_data_root):
        raise ImportValidationError(
            "storage_path_unsafe",
            _storage_path_unsafe_message(directory),
            status_code=409,
        )
    return directory


def _ensure_managed_storage_path(data_root: Path, path: Path) -> Path:
    resolved_data_root = data_root.resolve()
    try:
        if path.exists():
            resolved_path = path.resolve()
            if not resolved_path.is_relative_to(resolved_data_root):
                raise ImportValidationError(
                    "storage_path_unsafe",
                    _storage_path_unsafe_message(path),
                    status_code=409,
                )
            return resolved_path
        resolved_parent = path.parent.resolve()
        if not resolved_parent.is_relative_to(resolved_data_root):
            raise ImportValidationError(
                "storage_path_unsafe",
                _storage_path_unsafe_message(path),
                status_code=409,
            )
        return path
    except OSError as exc:
        raise ImportValidationError(
            "storage_path_unsafe",
            _storage_path_unsafe_message(path),
            status_code=409,
        ) from exc


def _non_regular_source_message(filename: str) -> str:
    return f"{filename} must be a regular source export file, not a symlink or special filesystem item."


def _sync_inbox_file_regular_findings(session: Session, inbox: Path) -> None:
    findings = session.scalars(
        select(ValidationFinding).where(
            ValidationFinding.code == "file_not_regular",
            ValidationFinding.target_type == "inbox_file",
            ValidationFinding.status == "open",
        )
    ).all()
    for finding in findings:
        if finding.target_id is None:
            continue
        path = inbox / finding.target_id
        if not path.exists() and not path.is_symlink():
            finding.status = "resolved"
            continue
        if _is_regular_source_file(path):
            finding.status = "resolved"


def validate_import_batch(session: Session, batch_id: str) -> dict[str, Any]:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise ImportValidationError("file_missing", "Import batch not found", status_code=404)
    if batch.status == "voided" or batch.validation_status == "voided":
        raise ImportValidationError(
            "voided_import_validation_blocked",
            "Voided import batches cannot be revalidated.",
            status_code=409,
        )
    _clear_batch_findings(session, batch.id)

    findings: list[ValidationFinding] = []
    for source_file in batch.source_files:
        path = Path(source_file.stored_path)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            findings.append(
                _create_finding(
                    session,
                    severity=BLOCKING,
                    code="file_not_regular",
                    message=_non_regular_source_message(source_file.original_filename),
                    target_type="import_batch",
                    target_id=batch.id,
                )
            )
            continue
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
        if not _source_file_integrity_matches(path, source_file):
            findings.append(
                _create_finding(
                    session,
                    severity=BLOCKING,
                    code="file_integrity_mismatch",
                    message=_source_file_integrity_message(source_file.original_filename),
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
            source_key_hint = None
            if batch.source and batch.source.source_key != "unknown":
                source_key_hint = batch.source.source_key
            profile = _detect_profile(
                parsed.headers,
                filename=source_file.original_filename,
                source_key_hint=source_key_hint,
            )
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
    refresh_source_coverage_findings(session)
    session.commit()
    findings = session.scalars(select(ValidationFinding).order_by(ValidationFinding.created_at)).all()
    return [serialize_finding(finding) for finding in findings]


def _finding_targets_closed_import_batch(session: Session, finding: ValidationFinding) -> bool:
    if finding.target_type != "import_batch" or finding.target_id is None:
        return False
    batch = session.get(ImportBatch, finding.target_id)
    if batch is None:
        return False
    return batch.status in {"accepted", "voided"} or batch.validation_status in {
        "accepted",
        "accepted_with_warnings",
        "voided",
    }


def resolve_validation_finding(
    session: Session,
    finding_id: str,
    *,
    actor: str,
    note: str,
    actor_context: Optional[ActorContext] = None,
) -> dict[str, Any]:
    finding = session.get(ValidationFinding, finding_id)
    if finding is None:
        raise ImportValidationError("validation_finding_not_found", "Validation finding not found.", status_code=404)
    if finding.status != "open":
        return {"finding": serialize_finding(finding), "event": None}
    if finding.severity == BLOCKING and not _finding_targets_closed_import_batch(session, finding):
        raise ImportValidationError(
            "active_blocking_validation_finding",
            "Active blocking findings must be fixed or voided before they can be cleared.",
            status_code=409,
        )

    event = ValidationFindingEvent(
        validation_finding=finding,
        event_type="resolved",
        actor=actor,
        actor_context_json=actor_context_to_json(derive_actor_context(actor, actor_context)),
        notes=note,
        metadata_json=json.dumps(
            {
                "previous_status": finding.status,
                "new_status": "resolved",
                "severity": finding.severity,
                "code": finding.code,
            },
            sort_keys=True,
        ),
    )
    session.add(event)
    session.flush()
    finding.status = "resolved"
    finding.resolution_event_id = event.id
    refresh_source_coverage_findings(session)
    session.commit()
    session.refresh(finding)
    session.refresh(event)
    return {"finding": serialize_finding(finding), "event": serialize_finding_event(event)}


def refresh_source_coverage_findings(session: Session) -> None:
    required_keys = _required_source_keys(session)
    accepted_keys = _accepted_source_keys(session)
    missing_keys = required_keys - accepted_keys
    existing = session.scalars(
        select(ValidationFinding)
        .where(ValidationFinding.code == "required_source_missing")
        .order_by(ValidationFinding.created_at)
    ).all()
    existing_by_source: dict[str, list[ValidationFinding]] = {}
    open_by_source: dict[str, list[ValidationFinding]] = {}
    for finding in existing:
        if finding.target_id:
            existing_by_source.setdefault(finding.target_id, []).append(finding)
        if finding.status == "open" and finding.target_id:
            open_by_source.setdefault(finding.target_id, []).append(finding)

    for source_key, findings in open_by_source.items():
        if source_key not in missing_keys:
            for finding in findings:
                finding.status = "resolved"
            continue
        for duplicate in findings[1:]:
            duplicate.status = "resolved"

    for source_key in sorted(missing_keys):
        if source_key in open_by_source:
            continue
        if any(finding.status == "resolved" for finding in existing_by_source.get(source_key, [])):
            continue
        _create_finding(
            session,
            severity=WARNING,
            code="required_source_missing",
            message=f"Required source {source_key} has not been accepted for the current close cycle.",
            target_type="source",
            target_id=source_key,
        )


def _required_source_keys(session: Session) -> set[str]:
    required: set[str] = set()
    for profile in list_source_profiles():
        required_setting = session.scalar(
            select(Setting).where(
                Setting.domain == "sources",
                Setting.setting_key == f"sources.{profile.source_key}.required",
            )
        )
        required_value = json.loads(required_setting.value_json) if required_setting else profile.required
        if required_value:
            required.add(profile.source_key)
    return required


def _accepted_source_keys(session: Session) -> set[str]:
    accepted_batches = session.scalars(select(ImportBatch).where(ImportBatch.status == "accepted")).all()
    return {batch.source.source_key for batch in accepted_batches if batch.source is not None}


def _open_findings(session: Session, batch_id: str) -> list[ValidationFinding]:
    return session.scalars(
        select(ValidationFinding).where(
            ValidationFinding.target_type == "import_batch",
            ValidationFinding.target_id == batch_id,
            ValidationFinding.status == "open",
        )
    ).all()


def _record_import_batch_event(
    session: Session,
    batch: ImportBatch,
    *,
    event_type: str,
    actor: str,
    notes: str,
    metadata: dict[str, Any],
    actor_context: Optional[ActorContext] = None,
) -> ImportBatchEvent:
    event = ImportBatchEvent(
        import_batch=batch,
        event_type=event_type,
        actor=actor,
        actor_context_json=actor_context_to_json(derive_actor_context(actor, actor_context)),
        notes=notes,
        metadata_json=json.dumps(metadata, sort_keys=True),
    )
    session.add(event)
    return event


def _stored_path_claimed_by_other_batch(session: Session, source_file: SourceFile, path: Path) -> bool:
    return (
        session.scalar(
            select(SourceFile)
            .join(ImportBatch)
            .where(
                SourceFile.id != source_file.id,
                SourceFile.stored_path == str(path),
                ImportBatch.status != "voided",
            )
        )
        is not None
    )


def _quarantine_batch(data_root: Path, batch: ImportBatch, findings: list[ValidationFinding]) -> None:
    quarantine_dir = _ensure_safe_storage_directory(data_root, data_root / "quarantine" / batch.id)
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


def void_import_batch(
    session: Session,
    data_root: Path,
    batch_id: str,
    *,
    actor: str,
    reason: str,
    destroy_files: bool = False,
    actor_context: Optional[ActorContext] = None,
) -> dict[str, Any]:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise ImportValidationError("file_missing", "Import batch not found", status_code=404)
    if batch.status == "accepted" or batch.imported_rows:
        raise ImportValidationError(
            "accepted_import_void_blocked",
            "Accepted import batches cannot be voided in v1.",
            status_code=409,
        )
    if batch.status == "voided" or batch.validation_status == "voided":
        active_findings = _open_findings(session, batch.id)
        for finding in active_findings:
            finding.status = "resolved"
        batch.status = "voided"
        batch.validation_status = "voided"
        for source_file in batch.source_files:
            source_file.validation_status = "voided"
        refresh_source_coverage_findings(session)
        session.commit()
        session.refresh(batch)
        return {"import_batch": serialize_import_batch(batch)}

    active_findings = _open_findings(session, batch.id)
    for finding in active_findings:
        finding.status = "resolved"

    destroyed_file_count = 0
    preserved_file_count = 0
    void_dir = _ensure_safe_storage_directory(data_root, data_root / "processed" / "voided" / batch.id)
    timestamp = utc_now_iso()
    for source_file in batch.source_files:
        source_path = Path(source_file.stored_path)
        _ensure_managed_storage_path(data_root, source_path)
        path_claimed_by_other_batch = _stored_path_claimed_by_other_batch(session, source_file, source_path)
        if destroy_files:
            if source_path.is_symlink() or (source_path.exists() and not source_path.is_file()):
                raise ImportValidationError(
                    "file_not_regular",
                    _non_regular_source_message(source_file.original_filename),
                    status_code=409,
                )
            if source_path.exists() and not path_claimed_by_other_batch:
                source_path.unlink()
                destroyed_file_count += 1
            source_file.storage_status = "destroyed"
            source_file.destroyed_at = timestamp
            source_file.destroyed_by = actor
            source_file.destroyed_reason = reason
        else:
            if source_path.is_symlink() or (source_path.exists() and not source_path.is_file()):
                raise ImportValidationError(
                    "file_not_regular",
                    _non_regular_source_message(source_file.original_filename),
                    status_code=409,
                )
            destination = void_dir / source_file.original_filename
            if source_path.exists() and not path_claimed_by_other_batch and source_path.resolve() != destination.resolve():
                if destination.exists():
                    destination = void_dir / f"{source_file.id}-{source_file.original_filename}"
                shutil.move(str(source_path), str(destination))
                source_file.stored_path = str(destination)
            source_file.storage_status = "preserved"
            preserved_file_count += 1
        source_file.validation_status = "voided"

    batch.status = "voided"
    batch.validation_status = "voided"
    _record_import_batch_event(
        session,
        batch,
        event_type="voided",
        actor=actor,
        notes=reason,
        actor_context=actor_context,
        metadata={
            "destroy_files": destroy_files,
            "preserved_file_count": preserved_file_count,
            "destroyed_file_count": destroyed_file_count,
            "resolved_finding_count": len(active_findings),
        },
    )
    if destroy_files:
        _record_import_batch_event(
            session,
            batch,
            event_type="files_destroyed",
            actor=actor,
            notes=reason,
            actor_context=actor_context,
            metadata={"destroyed_file_count": destroyed_file_count},
        )
    refresh_source_coverage_findings(session)
    session.commit()
    session.refresh(batch)
    return {"import_batch": serialize_import_batch(batch)}


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
    if batch.status == "voided" or batch.validation_status == "voided":
        raise ImportValidationError(
            "voided_import_acceptance_blocked",
            "Voided import batches cannot be accepted.",
            status_code=409,
        )

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
    if batch.validation_status == "blocked" or blocking_findings:
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

    for source_file in batch.source_files:
        source_path = Path(source_file.stored_path)
        if source_path.is_symlink() or (source_path.exists() and not source_path.is_file()):
            _create_finding(
                session,
                severity=BLOCKING,
                code="file_not_regular",
                message=_non_regular_source_message(source_file.original_filename),
                target_type="import_batch",
                target_id=batch.id,
            )
            session.commit()
            raise ImportValidationError(
                "file_not_regular",
                _non_regular_source_message(source_file.original_filename),
                status_code=409,
            )
        if not source_path.exists():
            _create_finding(
                session,
                severity=BLOCKING,
                code="file_missing",
                message=f"{source_file.original_filename} is missing.",
                target_type="import_batch",
                target_id=batch.id,
            )
            session.commit()
            raise ImportValidationError("file_missing", f"{source_file.original_filename} is missing.", status_code=404)
        if not _source_file_integrity_matches(source_path, source_file):
            _create_finding(
                session,
                severity=BLOCKING,
                code="file_integrity_mismatch",
                message=_source_file_integrity_message(source_file.original_filename),
                target_type="import_batch",
                target_id=batch.id,
            )
            session.commit()
            raise ImportValidationError(
                "file_integrity_mismatch",
                _source_file_integrity_message(source_file.original_filename),
                status_code=409,
            )

    year = batch.transaction_date_max[:4] if batch.transaction_date_max else "unknown-year"
    source_key = batch.source.source_key if batch.source else "unknown"
    raw_dir = _ensure_safe_storage_directory(data_root, data_root / "raw" / source_key / year / batch.id)
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
    refresh_source_coverage_findings(session)
    session.commit()
    session.refresh(batch)
    return serialize_import_batch(batch)
