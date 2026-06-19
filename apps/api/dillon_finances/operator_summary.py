from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from dillon_finances.ledger_normalization import list_transactions
from dillon_finances.models import ImportBatch, SourceFile, ValidationFinding
from dillon_finances.source_profiles import list_source_profiles


def operator_summary_payload(
    session: Session,
    *,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    transactions = list_transactions(session)
    findings = session.scalars(select(ValidationFinding)).all()
    import_batches = session.scalars(
        select(ImportBatch)
        .options(selectinload(ImportBatch.source), selectinload(ImportBatch.source_files))
        .order_by(ImportBatch.created_at.desc())
    ).all()
    source_files = session.scalars(select(SourceFile)).all()

    latest_import = _latest_import_payload(import_batches)
    source_summary = _source_summary(import_batches)
    validation_summary = _validation_summary(findings)
    review_summary = _review_summary(transactions)
    monthly_close = _monthly_close_summary(
        transaction_count=review_summary["total_transactions"],
        open_blocking=validation_summary["open_blocking"],
        missing_required_count=source_summary["missing_required_count"],
    )

    return {
        "runtime": runtime,
        "latest_import": latest_import,
        "sources": source_summary,
        "validation": validation_summary,
        "review": review_summary,
        "monthly_close": monthly_close,
        "artifacts": {
            "generated_count": 0,
            "status": "pending_reports_milestone",
        },
        "inbox": {
            "tracked_file_count": len(source_files),
        },
        "next_action": _next_action(
            latest_import=latest_import,
            validation=validation_summary,
            review=review_summary,
            sources=source_summary,
        ),
    }


def _latest_import_payload(import_batches: list[ImportBatch]) -> dict[str, Any]:
    if not import_batches:
        return {
            "id": None,
            "status": "none",
            "validation_status": "none",
            "source_key": None,
            "row_count": 0,
            "transaction_date_min": None,
            "transaction_date_max": None,
            "created_at": None,
        }
    batch = import_batches[0]
    return {
        "id": batch.id,
        "status": batch.status,
        "validation_status": batch.validation_status,
        "source_key": batch.source.source_key if batch.source else None,
        "row_count": batch.row_count or 0,
        "transaction_date_min": batch.transaction_date_min,
        "transaction_date_max": batch.transaction_date_max,
        "created_at": batch.created_at,
    }


def _source_summary(import_batches: list[ImportBatch]) -> dict[str, Any]:
    profiles = list(list_source_profiles())
    accepted_batches = [batch for batch in import_batches if batch.status == "accepted" and batch.source]
    imported_source_keys = sorted({batch.source.source_key for batch in accepted_batches})
    imported_key_set = set(imported_source_keys)
    required_keys = {profile.source_key for profile in profiles if profile.required}
    missing_required_keys = sorted(required_keys - imported_key_set)

    latest_by_source: dict[str, ImportBatch] = {}
    for batch in import_batches:
        if not batch.source:
            continue
        source_key = batch.source.source_key
        if source_key not in latest_by_source:
            latest_by_source[source_key] = batch

    return {
        "required_count": len(required_keys),
        "imported_source_keys": imported_source_keys,
        "missing_required_count": len(missing_required_keys),
        "missing_required_source_keys": missing_required_keys,
        "profiles": [
            {
                **profile.to_dict(),
                "imported": profile.source_key in imported_key_set,
                "latest_import_status": latest_by_source.get(profile.source_key).status
                if profile.source_key in latest_by_source
                else "none",
                "latest_transaction_date": latest_by_source.get(profile.source_key).transaction_date_max
                if profile.source_key in latest_by_source
                else None,
            }
            for profile in profiles
        ],
    }


def _validation_summary(findings: list[ValidationFinding]) -> dict[str, Any]:
    open_findings = [finding for finding in findings if finding.status == "open"]
    by_severity = {"blocking": 0, "warning": 0, "info": 0}
    for finding in open_findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
    return {
        "total_open": len(open_findings),
        "open_blocking": by_severity.get("blocking", 0),
        "open_warning": by_severity.get("warning", 0),
        "open_info": by_severity.get("info", 0),
        "by_severity": by_severity,
    }


def _review_summary(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    unreviewed = sum(1 for transaction in transactions if transaction["review_status"] == "unreviewed")
    reviewed = sum(1 for transaction in transactions if transaction["review_status"] == "reviewed")
    blocked = sum(1 for transaction in transactions if transaction["validation_status"] == "blocked")
    return {
        "total_transactions": len(transactions),
        "unreviewed": unreviewed,
        "reviewed": reviewed,
        "blocked": blocked,
    }


def _monthly_close_summary(
    *,
    transaction_count: int,
    open_blocking: int,
    missing_required_count: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    if open_blocking:
        blockers.append(f"{open_blocking} blocking validation finding")
    if missing_required_count:
        blockers.append(f"{missing_required_count} required source missing")

    return {
        "status": "not_started",
        "ready_for_draft": transaction_count > 0 and open_blocking == 0,
        "ready_for_final": transaction_count > 0 and open_blocking == 0 and missing_required_count == 0,
        "blockers": blockers,
    }


def _next_action(
    *,
    latest_import: dict[str, Any],
    validation: dict[str, Any],
    review: dict[str, Any],
    sources: dict[str, Any],
) -> dict[str, str]:
    if latest_import["status"] == "none":
        return {
            "code": "import_required_source_files",
            "label": "Import required source files",
        }
    if validation["open_blocking"]:
        return {
            "code": "resolve_validation_blockers",
            "label": "Resolve blocking validation findings",
        }
    if review["blocked"]:
        return {
            "code": "resolve_ledger_identity_blockers",
            "label": "Resolve ledger identity blockers",
        }
    if review["unreviewed"]:
        return {
            "code": "review_ledger_decisions",
            "label": "Review ledger decisions",
        }
    if sources["missing_required_count"]:
        return {
            "code": "import_remaining_required_sources",
            "label": "Import remaining required sources",
        }
    return {
        "code": "run_reports_monthly_close",
        "label": "Run reports and monthly close",
    }
