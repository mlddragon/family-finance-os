from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from family_finance_os.actors import ActorContext, actor_context_from_json, actor_context_to_json, derive_actor_context
from family_finance_os.decision_events import serialize_decision_event
from family_finance_os.ledger_normalization import list_transactions
from family_finance_os.models import (
    Artifact,
    CanonicalTransaction,
    Category,
    DecisionEvent,
    ImportBatch,
    ImportedRow,
    Job,
    MonthlyClose,
    ReportRun,
    Setting,
    SourceAccount,
    TransactionAllocation,
    ValidationFinding,
    utc_now_iso,
)
from family_finance_os.elevated_mode import ActiveElevatedSession, ElevatedContext
from family_finance_os.funds import funds_close_readiness, funds_summary
from family_finance_os.net_worth import net_worth_summary
from family_finance_os.settings_service import CONFIRMED_SOURCE_PROFILE_STATUSES, list_settings
from family_finance_os.source_profiles import list_source_profiles


class ReportingError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400, detail: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


class ReportRunRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    month: Optional[str] = None


class MonthlyCloseRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    month: Optional[str] = None
    notes: Optional[str] = None
    override_purpose: Optional[str] = None


class AdvisorExportRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    month: Optional[str] = None


def run_reports(
    session: Session,
    data_root: Path,
    request: ReportRunRequest,
    *,
    synthetic_artifact_marker: Optional[str] = None,
) -> dict[str, Any]:
    month = request.month or default_month(session)
    validation_summary = close_readiness(session, month=month)
    validation_status = _validation_status(validation_summary)
    input_snapshot = _input_snapshot(session, month=month, validation_summary=validation_summary)

    job = Job(
        job_type="report_run",
        status="running",
        actor=request.actor,
        actor_context_json=actor_context_to_json(derive_actor_context(request.actor, request.actor_context)),
        input_json=_dump(input_snapshot),
    )
    report_run = ReportRun(
        report_type="v1_core_reports",
        status="running",
        job=job,
        validation_status=validation_status,
        actor_context_json=actor_context_to_json(derive_actor_context(request.actor, request.actor_context)),
        input_snapshot_json=_dump(input_snapshot),
    )
    session.add_all([job, report_run])
    session.flush()

    report_dir = ensure_safe_artifact_directory(data_root, data_root / "reports" / report_run.id)
    reports = _core_report_payloads(session, month=month, validation_summary=validation_summary)
    artifacts = [
        _write_json_artifact(
            session,
            report_dir / f"{artifact_type}.json",
            data_root=data_root,
            artifact_type=artifact_type,
            payload=payload,
            job=job,
            source_inputs=input_snapshot,
            title=title,
            description=description,
            sensitivity="household_financial_summary",
            synthetic_artifact_marker=synthetic_artifact_marker,
        )
        for artifact_type, title, description, payload in reports
    ]
    artifacts.append(
        _write_csv_artifact(
            session,
            report_dir / "reviewed_transactions_export.csv",
            data_root=data_root,
            artifact_type="reviewed_transactions_export",
            rows=_reviewed_transaction_rows(session),
            job=job,
            source_inputs=input_snapshot,
        title="Reviewed Transaction Export",
        description="Reviewed/current transaction export for v1 reports.",
        sensitivity="household_financial_export",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    )

    output_summary = {
        "month": month,
        "artifact_count": len(artifacts),
        "artifact_types": [artifact.artifact_type for artifact in artifacts],
        "validation_summary": validation_summary,
        "provisional": validation_status != "passed",
    }
    report_run.status = "completed"
    report_run.output_summary_json = _dump(output_summary)
    job.status = "completed"
    job.finished_at = utc_now_iso()
    job.output_json = _dump(output_summary)
    session.commit()
    return {
        "job": serialize_job(job),
        "report_run": serialize_report_run(report_run),
        "validation_summary": validation_summary,
        "artifacts": [serialize_artifact(artifact) for artifact in artifacts],
    }


def create_monthly_close(
    session: Session,
    data_root: Path,
    request: MonthlyCloseRequest,
    *,
    status: str,
    synthetic_artifact_marker: Optional[str] = None,
    elevated_session: Optional[ActiveElevatedSession] = None,
) -> dict[str, Any]:
    month = request.month or default_month(session)
    validation_summary = close_readiness(session, month=month)
    existing_close = session.scalar(
        select(MonthlyClose).where(MonthlyClose.month == month, MonthlyClose.status == status)
    )
    if existing_close is not None:
        raise ReportingError(
            "monthly_close_already_exists",
            "A monthly close already exists for this month and status.",
            status_code=409,
            detail={"monthly_close": serialize_monthly_close(existing_close)},
        )

    legacy_blockers = validation_summary["legacy_blockers"]
    funds_blockers = validation_summary["funds_and_spendable"]["blockers"]
    governor_override_applied = False

    if status == "final":
        if legacy_blockers:
            raise ReportingError(
                "final_close_blocked",
                "Final close is blocked by validation, freshness, or required source coverage.",
                status_code=409,
                detail={"validation_summary": validation_summary},
            )
        if funds_blockers:
            _validate_monthly_close_governor_override(
                request=request,
                funds_blockers=funds_blockers,
                elevated_session=elevated_session,
            )
            governor_override_applied = True

    job = Job(
        job_type=f"monthly_close_{status}",
        status="running",
        actor=request.actor,
        actor_context_json=actor_context_to_json(derive_actor_context(request.actor, request.actor_context)),
        input_json=_dump({"month": month, "status": status, "validation_summary": validation_summary}),
    )
    monthly_close = MonthlyClose(
        month=month,
        status=status,
        actor=request.actor,
        actor_context_json=actor_context_to_json(derive_actor_context(request.actor, request.actor_context)),
        validation_summary=_dump(validation_summary),
        source_import_batch_ids_json=_dump(validation_summary["accepted_import_batch_ids"]),
        report_run_ids_json=_dump(_completed_report_run_ids(session)),
        artifact_folder_path="pending",
        provisional=(
            status != "final"
            or bool(legacy_blockers)
            or bool(funds_blockers)
            or governor_override_applied
        ),
        notes=request.notes,
    )
    session.add_all([job, monthly_close])
    session.flush()

    if governor_override_applied:
        _record_monthly_close_governor_override(
            session,
            request=request,
            month=month,
            monthly_close_id=monthly_close.id,
            funds_blockers=funds_blockers,
            elevated_session=elevated_session,
        )

    bundle_dir = ensure_safe_artifact_directory(
        data_root,
        data_root / "monthly_close" / month / f"{status}-{monthly_close.id}",
    )
    monthly_close.artifact_folder_path = str(bundle_dir)
    source_inputs = {
        "month": month,
        "monthly_close_id": monthly_close.id,
        "status": status,
        "validation_summary": validation_summary,
        "report_run_ids": _completed_report_run_ids(session),
        "governor_override_applied": governor_override_applied,
    }

    app_name = _setting_value(session, "branding", "branding.app_display_name", "Family Finance OS")
    memo_title = _render_title_template(
        _setting_value(
            session,
            "reports",
            "reports.monthly_close.title_template",
            "{app_name} Monthly Close - {month}",
        ),
        app_name=app_name,
        month=month,
    )
    memo_artifact = _write_text_artifact(
        session,
        bundle_dir / "monthly_close_memo.md",
        data_root=data_root,
        artifact_type="monthly_close_memo",
        text=_monthly_close_memo(title=memo_title, status=status, validation_summary=validation_summary),
        job=job,
        source_inputs=source_inputs,
        title=memo_title,
        description="Human-readable v1 monthly close memo.",
        sensitivity="household_financial_summary",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    settings_artifact = _write_json_artifact(
        session,
        bundle_dir / "settings_snapshot.json",
        data_root=data_root,
        artifact_type="settings_snapshot",
        payload={"month": month, "settings": list_settings(session)},
        job=job,
        source_inputs=source_inputs,
        title="Settings Snapshot",
        description="Settings state captured for monthly close reproducibility.",
        sensitivity="household_financial_configuration",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    decision_artifact = _write_json_artifact(
        session,
        bundle_dir / "decision_events.json",
        data_root=data_root,
        artifact_type="decision_event_export",
        payload={"month": month, "decision_events": _decision_event_rows(session)},
        job=job,
        source_inputs=source_inputs,
        title="Decision Event Export",
        description="Append-only decision events included in the close bundle.",
        sensitivity="household_financial_export",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    funds_snapshot = funds_summary(session, month=month)
    fund_pool_artifact = _write_json_artifact(
        session,
        bundle_dir / "fund_pool_summary.json",
        data_root=data_root,
        artifact_type="fund_pool_summary",
        payload={
            "month": month,
            "pools": funds_snapshot["pools"],
            "commitment_health": funds_snapshot["commitment_health"],
            "goals": funds_snapshot["goals"],
        },
        job=job,
        source_inputs=source_inputs,
        title="Fund Pool Summary",
        description="Fund pool commitments and Pool remaining captured for monthly close.",
        sensitivity="household_financial_summary",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    spendable_artifact = _write_json_artifact(
        session,
        bundle_dir / "spendable_snapshot.json",
        data_root=data_root,
        artifact_type="spendable_snapshot",
        payload={"month": month, "spendable": funds_snapshot["spendable"]},
        job=job,
        source_inputs=source_inputs,
        title="Spendable Snapshot",
        description="Spendable balance snapshot captured for monthly close.",
        sensitivity="household_financial_summary",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    monthly_close.settings_snapshot_artifact_id = settings_artifact.id
    monthly_close.decision_export_artifact_id = decision_artifact.id
    bundle_artifacts = [memo_artifact, settings_artifact, decision_artifact, fund_pool_artifact, spendable_artifact]
    manifest_payload = {
        "monthly_close_id": monthly_close.id,
        "month": month,
        "status": status,
        "provisional": monthly_close.provisional,
        "governor_override_applied": governor_override_applied,
        "generated_at": utc_now_iso(),
        "validation_summary": validation_summary,
        "source_import_batch_ids": validation_summary["accepted_import_batch_ids"],
        "report_run_ids": _completed_report_run_ids(session),
        "artifacts": [serialize_artifact(artifact) for artifact in bundle_artifacts],
    }
    if synthetic_artifact_marker:
        manifest_payload["synthetic_artifact_marker"] = synthetic_artifact_marker
    manifest_artifact = _write_json_artifact(
        session,
        bundle_dir / "manifest.json",
        data_root=data_root,
        artifact_type="monthly_close_manifest",
        payload=manifest_payload,
        job=job,
        source_inputs=source_inputs,
        title="Monthly Close Manifest",
        description="Machine-readable manifest for the monthly close bundle.",
        sensitivity="household_financial_summary",
        compact=True,
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    artifacts = [*bundle_artifacts, manifest_artifact]

    output_summary = {
        "month": month,
        "status": status,
        "monthly_close_id": monthly_close.id,
        "artifact_count": len(artifacts),
        "validation_summary": validation_summary,
        "governor_override_applied": governor_override_applied,
    }
    job.status = "completed"
    job.finished_at = utc_now_iso()
    job.output_json = _dump(output_summary)
    session.commit()
    return {
        "job": serialize_job(job),
        "monthly_close": serialize_monthly_close(monthly_close),
        "validation_summary": validation_summary,
        "governor_override_applied": governor_override_applied,
        "artifacts": [serialize_artifact(artifact) for artifact in artifacts],
    }


def create_advisor_export(
    session: Session,
    data_root: Path,
    request: AdvisorExportRequest,
    *,
    synthetic_artifact_marker: Optional[str] = None,
) -> dict[str, Any]:
    month = request.month or default_month(session)
    validation_summary = close_readiness(session, month=month)
    input_snapshot = _input_snapshot(session, month=month, validation_summary=validation_summary)
    job = Job(
        job_type="advisor_export",
        status="running",
        actor=request.actor,
        actor_context_json=actor_context_to_json(derive_actor_context(request.actor, request.actor_context)),
        input_json=_dump(input_snapshot),
    )
    session.add(job)
    session.flush()
    export_dir = ensure_safe_artifact_directory(data_root, data_root / "exports" / "advisor" / job.id)

    summary_artifact = _write_json_artifact(
        session,
        export_dir / "advisor_summary.json",
        data_root=data_root,
        artifact_type="advisor_summary",
        payload={
            "month": month,
            "validation_summary": validation_summary,
            "cashflow": _cashflow_summary(session),
            "category_spending": _category_spending_summary(session),
            "review_backlog": _review_backlog_summary(session),
        },
        job=job,
        source_inputs=input_snapshot,
        title="Advisor Summary",
        description="Explicit owner-requested advisor summary export with validation state.",
        sensitivity="household_financial_summary",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    transactions_artifact = _write_csv_artifact(
        session,
        export_dir / "advisor_transactions.csv",
        data_root=data_root,
        artifact_type="advisor_transactions_export",
        rows=_reviewed_transaction_rows(session),
        job=job,
        source_inputs=input_snapshot,
        title="Advisor Transaction Export",
        description="Explicit owner-requested transaction export for advisor review.",
        sensitivity="household_financial_export",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    artifacts = [summary_artifact, transactions_artifact]
    output_summary = {
        "month": month,
        "artifact_count": len(artifacts),
        "validation_summary": validation_summary,
    }
    job.status = "completed"
    job.finished_at = utc_now_iso()
    job.output_json = _dump(output_summary)
    session.commit()
    return {
        "job": serialize_job(job),
        "validation_summary": validation_summary,
        "artifacts": [serialize_artifact(artifact) for artifact in artifacts],
    }


def list_artifacts(session: Session) -> list[dict[str, Any]]:
    artifacts = session.scalars(select(Artifact).order_by(Artifact.created_at, Artifact.id)).all()
    return [serialize_artifact(artifact) for artifact in artifacts]


def ensure_safe_artifact_directory(data_root: Path, directory: Path) -> Path:
    resolved_data_root = data_root.resolve()
    try:
        relative_parts = directory.relative_to(data_root).parts
    except ValueError as exc:
        raise ReportingError(
            "artifact_storage_path_unsafe",
            "Artifact storage path must be inside DATA_ROOT.",
            status_code=409,
        ) from exc

    current = data_root
    for part in relative_parts[:-1]:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise ReportingError(
                "artifact_storage_path_unsafe",
                "Artifact storage path must be a safe directory inside DATA_ROOT.",
                status_code=409,
            )
        current.mkdir(exist_ok=True)
        if not current.resolve().is_relative_to(resolved_data_root):
            raise ReportingError(
                "artifact_storage_path_unsafe",
                "Artifact storage path must stay inside DATA_ROOT.",
                status_code=409,
            )

    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ReportingError(
            "artifact_storage_path_unsafe",
            "Artifact storage path must be a safe directory inside DATA_ROOT.",
            status_code=409,
        )
    directory.mkdir(exist_ok=True)
    if directory.is_symlink() or not directory.resolve().is_relative_to(resolved_data_root):
        raise ReportingError(
            "artifact_storage_path_unsafe",
            "Artifact storage path must stay inside DATA_ROOT.",
            status_code=409,
        )
    return directory


def artifact_download_path(session: Session, data_root: Path, artifact_id: str) -> Path:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise ReportingError("artifact_not_found", "Artifact not found.", status_code=404)
    registered_path = Path(artifact.path)
    path = registered_path.resolve()
    data_root_resolved = data_root.resolve()
    if not path.is_relative_to(data_root_resolved):
        raise ReportingError("artifact_path_outside_data_root", "Artifact path is outside DATA_ROOT.", status_code=409)
    if not registered_path.exists():
        raise ReportingError("artifact_file_missing", "Artifact file is missing.", status_code=404)
    if registered_path.is_symlink() or not registered_path.is_file():
        raise ReportingError(
            "artifact_file_not_regular",
            "Artifact path must be a regular file at the registered location.",
            status_code=409,
        )
    content = registered_path.read_bytes()
    if len(content) != artifact.byte_size or hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise ReportingError(
            "artifact_integrity_mismatch",
            "Artifact file no longer matches its registered integrity metadata.",
            status_code=409,
        )
    return registered_path


def close_readiness(session: Session, *, month: Optional[str] = None) -> dict[str, Any]:
    target_month = month or default_month(session)
    findings = session.scalars(select(ValidationFinding)).all()
    open_blocking = [finding for finding in findings if finding.status == "open" and finding.severity == "blocking"]
    open_warning = [finding for finding in findings if finding.status == "open" and finding.severity == "warning"]
    accepted_batches = _accepted_import_batches(session)
    coverage = _source_coverage(session, accepted_batches)
    transaction_count = len(list_transactions(session))
    legacy_blockers = []
    if open_blocking:
        legacy_blockers.append("open_blocking_validation")
    if coverage["missing_required_sources"]:
        legacy_blockers.append("missing_required_sources")
    if coverage["stale_required_sources"]:
        legacy_blockers.append("stale_required_sources")
    if coverage["unconfirmed_source_profiles"]:
        legacy_blockers.append("unconfirmed_source_profiles")

    funds_and_spendable = funds_close_readiness(session, month=target_month)
    combined_blockers = [*legacy_blockers, *funds_and_spendable["blockers"]]

    return {
        "month": target_month,
        "transaction_count": transaction_count,
        "open_blocking_count": len(open_blocking),
        "open_warning_count": len(open_warning),
        "missing_required_count": len(coverage["missing_required_sources"]),
        "stale_required_count": len(coverage["stale_required_sources"]),
        "missing_required_sources": coverage["missing_required_sources"],
        "stale_required_sources": coverage["stale_required_sources"],
        "unconfirmed_source_profiles": coverage["unconfirmed_source_profiles"],
        "accepted_source_keys": coverage["accepted_source_keys"],
        "required_source_keys": coverage["required_source_keys"],
        "accepted_import_batch_ids": [batch.id for batch in accepted_batches],
        "legacy_blockers": legacy_blockers,
        "funds_and_spendable": funds_and_spendable,
        "blockers": combined_blockers,
        "ready_for_draft": transaction_count > 0,
        "ready_for_final": transaction_count > 0 and not legacy_blockers and not funds_and_spendable["blockers"],
    }


def default_month(session: Session) -> str:
    transactions = list_transactions(session)
    if transactions:
        return str(max(transaction["posted_date"] for transaction in transactions))[:7]
    return date.today().isoformat()[:7]


def serialize_job(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "actor": job.actor,
        "actor_context": actor_context_from_json(job.actor_context_json),
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "output": _loads_optional(job.output_json),
    }


def serialize_report_run(report_run: ReportRun) -> dict[str, Any]:
    return {
        "id": report_run.id,
        "report_type": report_run.report_type,
        "status": report_run.status,
        "job_id": report_run.job_id,
        "validation_status": report_run.validation_status,
        "actor_context": actor_context_from_json(report_run.actor_context_json),
        "input_snapshot": _loads_optional(report_run.input_snapshot_json),
        "output_summary": _loads_optional(report_run.output_summary_json),
    }


def serialize_artifact(artifact: Artifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "artifact_type": artifact.artifact_type,
        "path": artifact.path,
        "sha256": artifact.sha256,
        "byte_size": artifact.byte_size,
        "title": artifact.title,
        "description": artifact.description,
        "producing_job_id": artifact.producing_job_id,
        "source_inputs": _loads_optional(artifact.source_inputs_json),
        "retention_category": artifact.retention_category,
        "sensitivity": artifact.sensitivity,
        "download_url": f"/api/artifacts/{artifact.id}/download",
        "created_at": artifact.created_at,
    }


def serialize_monthly_close(monthly_close: MonthlyClose) -> dict[str, Any]:
    return {
        "id": monthly_close.id,
        "month": monthly_close.month,
        "status": monthly_close.status,
        "actor": monthly_close.actor,
        "actor_context": actor_context_from_json(monthly_close.actor_context_json),
        "validation_summary": _loads_optional(monthly_close.validation_summary),
        "source_import_batch_ids": _loads_optional(monthly_close.source_import_batch_ids_json),
        "report_run_ids": _loads_optional(monthly_close.report_run_ids_json),
        "settings_snapshot_artifact_id": monthly_close.settings_snapshot_artifact_id,
        "decision_export_artifact_id": monthly_close.decision_export_artifact_id,
        "artifact_folder_path": monthly_close.artifact_folder_path,
        "provisional": monthly_close.provisional,
        "notes": monthly_close.notes,
    }


def _core_report_payloads(
    session: Session,
    *,
    month: str,
    validation_summary: dict[str, Any],
) -> list[tuple[str, str, str, dict[str, Any]]]:
    return [
        (
            "import_validation_summary",
            "Import And Validation Summary",
            "Import batches, source coverage, and validation state.",
            {
                "month": month,
                "validation_summary": validation_summary,
                "import_batches": [_serialize_import_batch(batch) for batch in _accepted_import_batches(session)],
                "open_findings": [_serialize_finding(finding) for finding in _open_findings(session)],
            },
        ),
        (
            "cashflow_summary",
            "Cashflow Summary",
            "Inflow, outflow, and net cashflow from imported ledger facts.",
            _cashflow_summary(session),
        ),
        (
            "category_spending_summary",
            "Category Spending Summary",
            "Outflow grouped by current reviewed category.",
            _category_spending_summary(session),
        ),
        (
            "review_backlog_summary",
            "Review Backlog Summary",
            "Review and validation queue counts.",
            _review_backlog_summary(session),
        ),
        (
            "net_worth_summary",
            "Net Worth Summary",
            "Actual-only and with-estimates manual net worth summary.",
            net_worth_summary(session, include_estimates=True),
        ),
        (
            "top_merchants_sources",
            "Top Merchants And Sources",
            "Merchant and source activity summary.",
            _top_merchants_sources(session),
        ),
    ]


def _cashflow_summary(session: Session) -> dict[str, Any]:
    rows = _imported_rows(session)
    inflow = sum(abs(Decimal(str(row.amount))) for row in rows if row.direction == "inflow")
    outflow = sum(abs(Decimal(str(row.amount))) for row in rows if row.direction == "outflow")
    return {
        "inflow": _money(inflow),
        "outflow": _money(outflow),
        "net": _money(inflow - outflow),
        "transaction_count": len(rows),
    }


def _category_spending_summary(session: Session) -> dict[str, Any]:
    transaction_by_id = {transaction["id"]: transaction for transaction in list_transactions(session)}
    allocations_by_transaction = _balanced_allocations_by_transaction(session)
    category_names = _category_names_by_id(session)
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    split_transactions_counted: set[str] = set()
    for row in _imported_rows(session):
        if row.direction != "outflow" or row.canonical_transaction_id is None:
            continue
        allocations = allocations_by_transaction.get(row.canonical_transaction_id)
        if allocations is not None:
            if row.canonical_transaction_id in split_transactions_counted:
                continue
            split_transactions_counted.add(row.canonical_transaction_id)
            for allocation in allocations:
                category = category_names.get(allocation.category_id, "Uncategorized")
                totals[category] += abs(Decimal(str(allocation.amount)))
            continue
        category = transaction_by_id.get(row.canonical_transaction_id, {}).get("category_current") or "Uncategorized"
        totals[category] += abs(Decimal(str(row.amount)))
    return {
        "categories": [
            {"category": category, "outflow": _money(amount)}
            for category, amount in sorted(totals.items(), key=lambda item: item[0])
        ]
    }


def _review_backlog_summary(session: Session) -> dict[str, Any]:
    transactions = list_transactions(session)
    review_counts = Counter(transaction["review_status"] for transaction in transactions)
    validation_counts = Counter(transaction["validation_status"] for transaction in transactions)
    return {
        "total_transactions": len(transactions),
        "review_counts": dict(review_counts),
        "validation_counts": dict(validation_counts),
    }


def _top_merchants_sources(session: Session) -> dict[str, Any]:
    merchant_totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    source_counts: Counter[str] = Counter()
    for row in _imported_rows(session):
        merchant = row.normalized_merchant or row.raw_description
        merchant_totals[merchant] += abs(Decimal(str(row.amount)))
        source_key = row.source_account.source.source_key if row.source_account and row.source_account.source else "unknown"
        source_counts[source_key] += 1
    return {
        "top_merchants": [
            {"merchant": merchant, "activity": _money(total)}
            for merchant, total in sorted(merchant_totals.items(), key=lambda item: item[1], reverse=True)[:10]
        ],
        "source_counts": dict(source_counts),
    }


def _reviewed_transaction_rows(session: Session) -> list[dict[str, Any]]:
    allocations_by_transaction = _balanced_allocations_by_transaction(session)
    category_names = _category_names_by_id(session)
    rows: list[dict[str, Any]] = []
    for transaction in list_transactions(session):
        base_row = {
            "id": transaction["id"],
            "posted_date": transaction["posted_date"],
            "raw_description": transaction["raw_description"],
            "normalized_merchant": transaction["normalized_merchant"],
            "review_status": transaction["review_status"],
            "validation_status": transaction["validation_status"],
        }
        allocations = allocations_by_transaction.get(transaction["id"])
        if allocations is None:
            rows.append(
                {
                    **base_row,
                    "amount": transaction["amount"],
                    "category_current": transaction["category_current"],
                    "subcategory_current": transaction.get("subcategory_current"),
                    "allocation_id": None,
                    "allocation_group_id": None,
                    "allocation_line_number": None,
                    "allocation_source": None,
                    "allocation_memo": None,
                }
            )
            continue
        for allocation in allocations:
            rows.append(
                {
                    **base_row,
                    "amount": _money(Decimal(str(allocation.amount))),
                    "category_current": category_names.get(allocation.category_id, "Uncategorized"),
                    "subcategory_current": allocation.subcategory,
                    "allocation_id": allocation.id,
                    "allocation_group_id": allocation.allocation_group_id,
                    "allocation_line_number": allocation.line_number,
                    "allocation_source": allocation.source,
                    "allocation_memo": allocation.memo,
                }
            )
    return rows


def _balanced_allocations_by_transaction(session: Session) -> dict[str, list[TransactionAllocation]]:
    transactions = {
        transaction.id: Decimal(str(transaction.amount)).quantize(Decimal("0.01"))
        for transaction in session.scalars(select(CanonicalTransaction)).all()
    }
    allocations = session.scalars(
        select(TransactionAllocation)
        .where(TransactionAllocation.status == "active")
        .order_by(TransactionAllocation.canonical_transaction_id, TransactionAllocation.line_number)
    ).all()
    grouped: dict[str, list[TransactionAllocation]] = defaultdict(list)
    for allocation in allocations:
        grouped[allocation.canonical_transaction_id].append(allocation)
    return {
        transaction_id: lines
        for transaction_id, lines in grouped.items()
        if transaction_id in transactions
        and sum((Decimal(str(line.amount)) for line in lines), Decimal("0.00")).quantize(Decimal("0.01"))
        == transactions[transaction_id]
    }


def _category_names_by_id(session: Session) -> dict[str, str]:
    categories = session.scalars(select(Category)).all()
    return {category.id: category.display_name for category in categories}


def _decision_event_rows(session: Session) -> list[dict[str, Any]]:
    events = session.scalars(select(DecisionEvent).order_by(DecisionEvent.created_at, DecisionEvent.id)).all()
    return [serialize_decision_event(event) for event in events]


def _monthly_close_memo(*, title: str, status: str, validation_summary: dict[str, Any]) -> str:
    funds = validation_summary.get("funds_and_spendable", {})
    return "\n".join(
        [
            f"# {title}",
            "",
            f"Status: {status}",
            f"Provisional: {not validation_summary['ready_for_final']}",
            f"Transactions: {validation_summary['transaction_count']}",
            f"Missing required sources: {validation_summary['missing_required_count']}",
            f"Stale required sources: {validation_summary['stale_required_count']}",
            f"Unconfirmed source profiles: {len(validation_summary['unconfirmed_source_profiles'])}",
            f"Open blocking findings: {validation_summary['open_blocking_count']}",
            f"Funds/Spendable blockers: {', '.join(funds.get('blockers', [])) or 'none'}",
            f"Negative Pool remaining: {', '.join(funds.get('negative_pool_remaining', [])) or 'none'}",
            f"Headline Spendable balance: {funds.get('headline_spendable', 'unknown')}",
        ]
    )


def _validate_monthly_close_governor_override(
    *,
    request: MonthlyCloseRequest,
    funds_blockers: list[str],
    elevated_session: Optional[ActiveElevatedSession],
) -> None:
    if not funds_blockers:
        return
    if elevated_session is None or elevated_session.context != ElevatedContext.FINANCIAL_GOVERNANCE:
        raise ReportingError(
            "monthly_close_governor_required",
            "Final close needs Financial Governor elevated mode for Funds/Spendable blockers.",
            status_code=409,
        )
    if elevated_session.purpose_code != "monthly_close_governance_review":
        raise ReportingError(
            "monthly_close_override_required",
            "Final close needs Financial Governor override because Funds/Spendable checks have blockers.",
            status_code=409,
        )
    if not (request.override_purpose or "").strip():
        raise ReportingError(
            "monthly_close_override_note_required",
            "Enter why final close should proceed with these Funds/Spendable blockers.",
            status_code=422,
        )


def _record_monthly_close_governor_override(
    session: Session,
    *,
    request: MonthlyCloseRequest,
    month: str,
    monthly_close_id: str,
    funds_blockers: list[str],
    elevated_session: Optional[ActiveElevatedSession],
) -> None:
    actor_context = derive_actor_context(request.actor, request.actor_context)
    session.add(
        DecisionEvent(
            target_type="monthly_close",
            target_id=monthly_close_id,
            decision_type="monthly_close_governor_override",
            field_name="funds_and_spendable_blockers",
            previous_value=_dump({"month": month, "blockers": funds_blockers}),
            approved_value=_dump(
                {
                    "override_purpose": (request.override_purpose or "").strip(),
                    "blockers": funds_blockers,
                    "elevated_session_id": elevated_session.session_id if elevated_session else None,
                    "elevated_purpose_code": elevated_session.purpose_code if elevated_session else None,
                }
            ),
            actor=request.actor,
            actor_context_json=actor_context_to_json(actor_context),
            notes=(request.override_purpose or "").strip(),
        )
    )
    session.flush()


def cashflow_for_month(session: Session, month: str) -> dict[str, Any]:
    rows = [row for row in _imported_rows(session) if (row.posted_date or "")[:7] == month]
    inflow = sum(abs(Decimal(str(row.amount))) for row in rows if row.direction == "inflow")
    outflow = sum(abs(Decimal(str(row.amount))) for row in rows if row.direction == "outflow")
    return {
        "month": month,
        "inflow": _money(inflow),
        "outflow": _money(outflow),
        "net": _money(inflow - outflow),
        "transaction_count": len(rows),
    }


def cashflow_trend(session: Session, *, months: int = 6, anchor_month: Optional[str] = None) -> dict[str, Any]:
    anchor = anchor_month or default_month(session)
    year, month_num = map(int, anchor.split("-"))
    points: list[dict[str, Any]] = []
    current_year, current_month = year, month_num
    for _ in range(max(months, 1)):
        month_key = f"{current_year:04d}-{current_month:02d}"
        readiness = close_readiness(session, month=month_key)
        provisional_reasons: list[str] = []
        if readiness["legacy_blockers"]:
            provisional_reasons.extend(readiness["legacy_blockers"])
        if readiness["open_warning_count"]:
            provisional_reasons.append("open_validation_warnings")
        if readiness["funds_and_spendable"]["blockers"]:
            provisional_reasons.extend(readiness["funds_and_spendable"]["blockers"])
        cashflow = cashflow_for_month(session, month_key)
        points.append(
            {
                **cashflow,
                "provisional": bool(provisional_reasons) or cashflow["transaction_count"] == 0,
                "provisional_reasons": provisional_reasons,
            }
        )
        current_month -= 1
        if current_month == 0:
            current_month = 12
            current_year -= 1
    points.reverse()
    return {"months": months, "anchor_month": anchor, "points": points}


def category_spend_for_month(session: Session, month: str) -> dict[str, Any]:
    transaction_by_id = {transaction["id"]: transaction for transaction in list_transactions(session)}
    allocations_by_transaction = _balanced_allocations_by_transaction(session)
    category_names = _category_names_by_id(session)
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    split_transactions_counted: set[str] = set()
    for row in _imported_rows(session):
        if (row.posted_date or "")[:7] != month:
            continue
        if row.direction != "outflow" or row.canonical_transaction_id is None:
            continue
        allocations = allocations_by_transaction.get(row.canonical_transaction_id)
        if allocations is not None:
            if row.canonical_transaction_id in split_transactions_counted:
                continue
            split_transactions_counted.add(row.canonical_transaction_id)
            for allocation in allocations:
                category = category_names.get(allocation.category_id, "Uncategorized")
                totals[category] += abs(Decimal(str(allocation.amount)))
            continue
        category = transaction_by_id.get(row.canonical_transaction_id, {}).get("category_current") or "Uncategorized"
        totals[category] += abs(Decimal(str(row.amount)))
    readiness = close_readiness(session, month=month)
    return {
        "month": month,
        "categories": [
            {"category": category, "outflow": _money(amount)}
            for category, amount in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        ],
        "provisional": bool(readiness["legacy_blockers"] or readiness["open_warning_count"]),
        "provisional_reasons": readiness["legacy_blockers"],
    }


def _source_coverage(session: Session, accepted_batches: list[ImportBatch]) -> dict[str, Any]:
    settings = _settings_lookup(session)
    latest_by_source: dict[str, ImportBatch] = {}
    for batch in sorted(accepted_batches, key=lambda item: item.transaction_date_max or ""):
        if batch.source:
            latest_by_source[batch.source.source_key] = batch

    required_source_keys: list[str] = []
    missing_required_sources: list[str] = []
    stale_required_sources: list[str] = []
    unconfirmed_source_profiles: list[str] = []
    for profile in list_source_profiles():
        required = bool(settings.get(("sources", f"sources.{profile.source_key}.required"), profile.required))
        freshness_days = int(
            settings.get(("freshness", f"sources.{profile.source_key}.freshness_threshold_days"), profile.freshness_threshold_days)
        )
        confirmation_status = settings.get(
            ("sources", f"sources.{profile.source_key}.profile_confirmation_status"),
            profile.confirmation_status,
        )
        if not required:
            continue
        required_source_keys.append(profile.source_key)
        if confirmation_status not in CONFIRMED_SOURCE_PROFILE_STATUSES:
            unconfirmed_source_profiles.append(profile.source_key)
        latest = latest_by_source.get(profile.source_key)
        if latest is None:
            missing_required_sources.append(profile.source_key)
            continue
        if latest.transaction_date_max:
            latest_date = datetime.strptime(latest.transaction_date_max, "%Y-%m-%d").date()
            if (date.today() - latest_date).days > freshness_days:
                stale_required_sources.append(profile.source_key)

    return {
        "required_source_keys": sorted(required_source_keys),
        "accepted_source_keys": sorted(latest_by_source.keys()),
        "missing_required_sources": sorted(missing_required_sources),
        "stale_required_sources": sorted(stale_required_sources),
        "unconfirmed_source_profiles": sorted(unconfirmed_source_profiles),
    }


def _settings_lookup(session: Session) -> dict[tuple[str, str], Any]:
    settings = session.scalars(select(Setting)).all()
    return {(setting.domain, setting.setting_key): json.loads(setting.value_json) for setting in settings}


def _setting_value(session: Session, domain: str, setting_key: str, default: Any) -> Any:
    return _settings_lookup(session).get((domain, setting_key), default)


def _render_title_template(template: str, *, app_name: str, month: str) -> str:
    return template.replace("{app_name}", app_name).replace("{month}", month)


def _input_snapshot(session: Session, *, month: str, validation_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "month": month,
        "import_batch_ids": validation_summary["accepted_import_batch_ids"],
        "validation_summary": validation_summary,
        "setting_count": len(list_settings(session)),
    }


def _accepted_import_batches(session: Session) -> list[ImportBatch]:
    return session.scalars(
        select(ImportBatch)
        .where(ImportBatch.status == "accepted")
        .options(selectinload(ImportBatch.source), selectinload(ImportBatch.source_files))
        .order_by(ImportBatch.created_at, ImportBatch.id)
    ).all()


def _imported_rows(session: Session) -> list[ImportedRow]:
    return session.scalars(
        select(ImportedRow)
        .options(
            selectinload(ImportedRow.source_account),
            selectinload(ImportedRow.source_account).selectinload(SourceAccount.source),
        )
        .order_by(ImportedRow.posted_date, ImportedRow.id)
    ).all()


def _open_findings(session: Session) -> list[ValidationFinding]:
    return session.scalars(select(ValidationFinding).where(ValidationFinding.status == "open")).all()


def _completed_report_run_ids(session: Session) -> list[str]:
    return session.scalars(select(ReportRun.id).where(ReportRun.status == "completed")).all()


def _validation_status(validation_summary: dict[str, Any]) -> str:
    if validation_summary["open_blocking_count"]:
        return "blocked"
    if (
        validation_summary["open_warning_count"]
        or validation_summary["missing_required_count"]
        or validation_summary["stale_required_count"]
        or validation_summary["unconfirmed_source_profiles"]
    ):
        return "passed_with_warnings"
    return "passed"


def _write_json_artifact(
    session: Session,
    path: Path,
    *,
    data_root: Path,
    artifact_type: str,
    payload: dict[str, Any],
    job: Job,
    source_inputs: dict[str, Any],
    title: str,
    description: str,
    sensitivity: str,
    compact: bool = False,
    synthetic_artifact_marker: Optional[str] = None,
) -> Artifact:
    if synthetic_artifact_marker:
        payload = {"synthetic_artifact_marker": synthetic_artifact_marker, **payload}
    if compact:
        content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    else:
        content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    return _write_artifact(
        session,
        path,
        data_root=data_root,
        artifact_type=artifact_type,
        content=content,
        job=job,
        source_inputs=source_inputs,
        title=title,
        description=description,
        sensitivity=sensitivity,
    )


def _write_text_artifact(
    session: Session,
    path: Path,
    *,
    data_root: Path,
    artifact_type: str,
    text: str,
    job: Job,
    source_inputs: dict[str, Any],
    title: str,
    description: str,
    sensitivity: str,
    synthetic_artifact_marker: Optional[str] = None,
) -> Artifact:
    if synthetic_artifact_marker:
        text = f"{synthetic_artifact_marker}\n\n{text}"
    return _write_artifact(
        session,
        path,
        data_root=data_root,
        artifact_type=artifact_type,
        content=text.encode("utf-8"),
        job=job,
        source_inputs=source_inputs,
        title=title,
        description=description,
        sensitivity=sensitivity,
    )


def _write_csv_artifact(
    session: Session,
    path: Path,
    *,
    data_root: Path,
    artifact_type: str,
    rows: list[dict[str, Any]],
    job: Job,
    source_inputs: dict[str, Any],
    title: str,
    description: str,
    sensitivity: str,
    synthetic_artifact_marker: Optional[str] = None,
) -> Artifact:
    buffer = io.StringIO()
    if synthetic_artifact_marker:
        rows = [
            {
                "synthetic_artifact_marker": synthetic_artifact_marker,
                **row,
            }
            for row in rows
        ]
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return _write_artifact(
        session,
        path,
        data_root=data_root,
        artifact_type=artifact_type,
        content=buffer.getvalue().encode("utf-8"),
        job=job,
        source_inputs=source_inputs,
        title=title,
        description=description,
        sensitivity=sensitivity,
    )


def _write_artifact(
    session: Session,
    path: Path,
    *,
    data_root: Path,
    artifact_type: str,
    content: bytes,
    job: Job,
    source_inputs: dict[str, Any],
    title: str,
    description: str,
    sensitivity: str,
) -> Artifact:
    ensure_safe_artifact_directory(data_root, path.parent)
    path.write_bytes(content)
    artifact = Artifact(
        artifact_type=artifact_type,
        path=str(path),
        sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        title=title,
        description=description,
        producing_job=job,
        source_inputs_json=_dump(source_inputs),
        retention_category="v1_operational_artifact",
        sensitivity=sensitivity,
    )
    session.add(artifact)
    session.flush()
    return artifact


def _serialize_import_batch(batch: ImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "source_key": batch.source.source_key if batch.source else None,
        "status": batch.status,
        "validation_status": batch.validation_status,
        "row_count": batch.row_count,
        "transaction_date_min": batch.transaction_date_min,
        "transaction_date_max": batch.transaction_date_max,
    }


def _serialize_finding(finding: ValidationFinding) -> dict[str, Any]:
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


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _loads_optional(value_json: Optional[str]) -> Any:
    return json.loads(value_json) if value_json else None
