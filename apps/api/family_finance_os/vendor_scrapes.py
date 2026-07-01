from __future__ import annotations

import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import derive_actor_context
from family_finance_os.jobs import record_job
from family_finance_os.models import Job, Setting, utc_now_iso
from family_finance_os.receipts import persist_vendor_scraper_receipts
from family_finance_os.reporting import (
    ensure_safe_artifact_directory,
    serialize_artifact,
    serialize_job,
    _write_json_artifact,
)
from family_finance_os.vendor_scrape_contracts import (
    ActorVendorScrapeRequest,
    VendorScrapeAdapterOutput,
    VendorScrapeCancelRequest,
    VendorScrapeError,
    VendorScrapeRunRequest,
)
from family_finance_os.vendor_adapters import ADAPTER_DISPLAY_NAMES, get_adapter

MONEY_QUANT = Decimal("0.01")
VENDOR_KEYS = ("amazon", "costco", "walmart")
SCRAPE_MODES = {"synthetic", "manual_browser_assist"}
PIPELINE_STAGES = ("prepare", "collect", "normalize", "validate", "persist", "audit")
FORBIDDEN_REQUEST_KEY_FRAGMENTS = (
    "credential",
    "cookie",
    "token",
    "password",
    "session",
    "browser_profile",
    "api_key",
)
FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "credentials",
        "credential",
        "session",
        "cookie",
        "cookies",
        "token",
        "tokens",
        "password",
        "auth",
        "browser_profile",
        "session_id",
        "access_token",
        "refresh_token",
        "api_key",
    }
)

VENDOR_ADAPTER_REGISTRY: dict[str, dict[str, str]] = {
    vendor_key: {"vendor_key": vendor_key, "display_name": display_name}
    for vendor_key, display_name in ADAPTER_DISPLAY_NAMES.items()
}


def reject_forbidden_request_fields(data: dict[str, Any]) -> None:
    for key in data:
        lowered = key.lower()
        if lowered in FORBIDDEN_REQUEST_KEYS or any(
            fragment in lowered for fragment in FORBIDDEN_REQUEST_KEY_FRAGMENTS
        ):
            raise VendorScrapeError(
                "vendor_scrape_credentials_forbidden",
                "Vendor scrape requests must not include credential or session fields.",
            )


def list_vendor_adapters(session: Session) -> dict[str, Any]:
    adapters = []
    for vendor_key, metadata in VENDOR_ADAPTER_REGISTRY.items():
        last_job = session.scalar(
            select(Job)
            .where(Job.job_type == "vendor_scrape")
            .where(Job.input_json.contains(f'"vendor_key": "{vendor_key}"'))
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        last_run = None
        if last_job is not None:
            last_run = {
                "job_id": last_job.id,
                "status": last_job.status,
                "started_at": last_job.started_at,
                "finished_at": last_job.finished_at,
            }
        adapters.append(
            {
                **metadata,
                "enabled": is_vendor_scraper_enabled(session, vendor_key),
                "last_run": last_run,
            }
        )
    return {"adapters": adapters}


def run_vendor_scrape(
    session: Session,
    data_root: Path,
    request: VendorScrapeRunRequest,
    *,
    synthetic_artifact_marker: Optional[str] = None,
) -> dict[str, Any]:
    _validate_run_request(request)
    vendor_key = request.vendor_key.strip().lower()
    adapter = VENDOR_ADAPTER_REGISTRY.get(vendor_key)
    if adapter is None:
        raise VendorScrapeError(
            "vendor_adapter_not_found",
            f"Vendor adapter '{vendor_key}' was not found.",
            status_code=404,
        )
    if not is_vendor_scraper_enabled(session, vendor_key):
        raise VendorScrapeError(
            "vendor_scrape_disabled",
            f"Vendor adapter '{vendor_key}' is disabled.",
            status_code=409,
        )

    input_payload = {
        "vendor_key": vendor_key,
        "mode": request.mode,
        "date_from": request.date_from,
        "date_to": request.date_to,
        "output_directory": request.output_directory,
        "actor_context": derive_actor_context(request.actor, request.actor_context).model_dump(),
    }
    job = record_job(
        session,
        job_type="vendor_scrape",
        status="running",
        actor=request.actor,
        actor_context=request.actor_context,
        input_json=json.dumps(input_payload, sort_keys=True),
        output_json=json.dumps({"events": []}, sort_keys=True),
    )
    session.flush()

    events: list[dict[str, Any]] = []
    artifact_dir = _resolve_output_directory(data_root, job.id, request.output_directory)
    normalized: Optional[VendorScrapeAdapterOutput] = None
    created_receipts: list[dict[str, Any]] = []
    artifact_id: Optional[str] = None

    try:
        _run_stage(events, "prepare", lambda: _stage_prepare(data_root, artifact_dir))
        raw_payload = _run_stage(
            events,
            "collect",
            lambda: _stage_collect(vendor_key, request.mode, data_root=data_root, run_id=job.id),
        )
        normalized = _run_stage(
            events,
            "normalize",
            lambda: _stage_normalize(vendor_key, raw_payload, run_id=job.id),
        )
        _run_stage(events, "validate", lambda: validate_vendor_scrape_output(normalized))
        created_receipts = _run_stage(
            events,
            "persist",
            lambda: persist_vendor_scraper_receipts(
                session,
                vendor_key=vendor_key,
                receipts=_receipts_for_persist(normalized),
                actor=request.actor,
                actor_context=request.actor_context,
            ),
        )
        artifact = _run_stage(
            events,
            "audit",
            lambda: _stage_audit(
                session,
                data_root=data_root,
                artifact_dir=artifact_dir,
                job=job,
                normalized=normalized,
                input_payload=input_payload,
                synthetic_artifact_marker=synthetic_artifact_marker,
            ),
        )
        artifact_id = artifact["id"]
        job.status = "completed"
        job.finished_at = utc_now_iso()
        job.output_json = json.dumps(
            {
                "events": events,
                "vendor_key": vendor_key,
                "mode": request.mode,
                "quality": normalized.quality.model_dump(),
                "receipt_count": len(created_receipts),
                "created_receipt_ids": [receipt["id"] for receipt in created_receipts],
                "artifact_id": artifact_id,
            },
            sort_keys=True,
        )
        session.commit()
        session.refresh(job)
        return {
            "job": serialize_job(job),
            "receipts": created_receipts,
            "artifact_id": artifact_id,
        }
    except VendorScrapeError as exc:
        _mark_job_failed(session, job, events, exc)
        raise


def get_vendor_scrape_job(session: Session, job_id: str) -> dict[str, Any]:
    job = _get_vendor_scrape_job(session, job_id)
    return {"job": serialize_job(job)}


def get_vendor_scrape_events(session: Session, job_id: str) -> dict[str, Any]:
    job = _get_vendor_scrape_job(session, job_id)
    output = _loads_optional(job.output_json) or {}
    return {"job_id": job.id, "events": output.get("events", [])}


def cancel_vendor_scrape(session: Session, job_id: str, request: VendorScrapeCancelRequest) -> dict[str, Any]:
    job = _get_vendor_scrape_job(session, job_id)
    if job.status != "running":
        raise VendorScrapeError(
            "vendor_scrape_not_running",
            "Only running vendor scrape jobs can be canceled.",
            status_code=409,
        )
    output = _loads_optional(job.output_json) or {}
    events = list(output.get("events", []))
    events.append(_event("cancel", "canceled"))
    job.status = "canceled"
    job.finished_at = utc_now_iso()
    job.output_json = json.dumps({**output, "events": events}, sort_keys=True)
    session.commit()
    session.refresh(job)
    return {"job": serialize_job(job)}


def is_vendor_scraper_enabled(session: Session, vendor_key: str) -> bool:
    setting_key = f"vendor_scraper.{vendor_key}.enabled"
    record = session.scalar(select(Setting).where(Setting.setting_key == setting_key))
    if record is None:
        return False
    value = json.loads(record.value_json)
    return bool(value)


def validate_vendor_scrape_output(payload: VendorScrapeAdapterOutput) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    seen_external_ids: set[str] = set()

    for receipt in payload.receipts:
        if receipt.external_receipt_id in seen_external_ids:
            findings.append(
                {
                    "code": "duplicate_external_receipt_id",
                    "message": f"Duplicate external receipt id '{receipt.external_receipt_id}'.",
                }
            )
        seen_external_ids.add(receipt.external_receipt_id)

        if not receipt.receipt_total:
            findings.append(
                {
                    "code": "missing_receipt_total",
                    "message": f"Receipt '{receipt.external_receipt_id}' is missing receipt_total.",
                }
            )
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", receipt.purchase_date):
            findings.append(
                {
                    "code": "invalid_purchase_date",
                    "message": f"Receipt '{receipt.external_receipt_id}' has an invalid purchase date.",
                }
            )

        receipt_total = _money_decimal(receipt.receipt_total)
        if receipt_total <= Decimal("0.00"):
            findings.append(
                {
                    "code": "invalid_receipt_total",
                    "message": f"Receipt '{receipt.external_receipt_id}' must have a positive total.",
                }
            )
        if receipt.lines:
            line_total = sum((_money_decimal(line.line_total) for line in receipt.lines), Decimal("0.00"))
            if line_total != receipt_total:
                findings.append(
                    {
                        "code": "receipt_total_mismatch",
                        "message": (
                            f"Receipt '{receipt.external_receipt_id}' line totals "
                            f"({_money(line_total)}) do not match receipt total ({_money(receipt_total)})."
                        ),
                    }
                )

    if findings:
        raise VendorScrapeError(
            "vendor_scrape_validation_failed",
            "Vendor scrape output failed validation.",
            detail={"findings": findings},
        )
    return {
        "receipt_count": len(payload.receipts),
        "line_count": sum(len(receipt.lines) for receipt in payload.receipts),
        "warnings": payload.quality.warnings,
    }


def load_synthetic_fixture(vendor_key: str, *, fixture_name: Optional[str] = None) -> dict[str, Any]:
    """Load a synthetic fixture from tests/fixtures/synthetic."""
    fixture_path = _synthetic_fixture_path(vendor_key, fixture_name=fixture_name)
    if not fixture_path.exists():
        raise VendorScrapeError(
            "vendor_scrape_fixture_not_found",
            f"Synthetic fixture for '{vendor_key}' was not found.",
            status_code=404,
        )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def load_collect_fixture(vendor_key: str, *, fixture_name: Optional[str] = None) -> dict[str, Any]:
    from family_finance_os.vendor_adapters.base import load_collect_fixture as _load_collect_fixture

    return _load_collect_fixture(vendor_key, fixture_name=fixture_name)


def _validate_run_request(request: VendorScrapeRunRequest) -> None:
    if request.mode not in SCRAPE_MODES:
        raise VendorScrapeError("vendor_scrape_mode_invalid", "Vendor scrape mode is not supported.")
    for field_name, value in (("date_from", request.date_from), ("date_to", request.date_to)):
        if value is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise VendorScrapeError(
                "vendor_scrape_date_invalid",
                f"{field_name} must use YYYY-MM-DD format.",
            )


def _resolve_output_directory(
    data_root: Path,
    job_id: str,
    output_directory: Optional[str],
) -> Path:
    if output_directory:
        candidate = Path(output_directory)
        if not candidate.is_absolute():
            candidate = data_root / candidate
        resolved = candidate.resolve()
        data_root_resolved = data_root.resolve()
        try:
            resolved.relative_to(data_root_resolved)
        except ValueError as exc:
            raise VendorScrapeError(
                "vendor_scrape_output_path_unsafe",
                "Vendor scrape output path must stay under DATA_ROOT.",
                status_code=409,
            ) from exc
        return ensure_safe_artifact_directory(data_root, resolved)
    return ensure_safe_artifact_directory(data_root, data_root / "vendor_scrapes" / job_id)


def _stage_prepare(data_root: Path, artifact_dir: Path) -> None:
    ensure_safe_artifact_directory(data_root, artifact_dir)


def _stage_collect(vendor_key: str, mode: str, *, data_root: Path, run_id: str) -> dict[str, Any]:
    adapter = get_adapter(vendor_key)
    return adapter.collect(mode, data_root=data_root, run_id=run_id)


def _stage_normalize(vendor_key: str, raw_payload: dict[str, Any], *, run_id: str) -> VendorScrapeAdapterOutput:
    adapter = get_adapter(vendor_key)
    return adapter.normalize(raw_payload, run_id=run_id)


def _stage_audit(
    session: Session,
    *,
    data_root: Path,
    artifact_dir: Path,
    job: Job,
    normalized: VendorScrapeAdapterOutput,
    input_payload: dict[str, Any],
    synthetic_artifact_marker: Optional[str],
) -> dict[str, Any]:
    artifact = _write_json_artifact(
        session,
        artifact_dir / "normalized_output.json",
        data_root=data_root,
        artifact_type="vendor_scrape_normalized_output",
        payload=normalized.model_dump(),
        job=job,
        source_inputs=input_payload,
        title="Vendor Scrape Normalized Output",
        description="Normalized vendor scrape receipt output for audit review.",
        sensitivity="household_financial_summary",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    return serialize_artifact(artifact)


def _receipts_for_persist(normalized: VendorScrapeAdapterOutput) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for receipt in normalized.receipts:
        receipts.append(
            {
                "merchant_name": receipt.merchant_name,
                "purchase_date": receipt.purchase_date,
                "receipt_total": receipt.receipt_total,
                "lines": [
                    {
                        "item_description": line.item_description,
                        "line_total": line.line_total,
                        "quantity": line.quantity,
                        "category_id": line.category_id,
                        "review_status": line.review_status,
                    }
                    for line in receipt.lines
                ],
            }
        )
    return receipts


def _run_stage(events: list[dict[str, Any]], stage: str, fn):
    events.append(_event(stage, "started"))
    try:
        result = fn()
    except Exception:
        events.append(_event(stage, "failed"))
        raise
    events.append(_event(stage, "completed"))
    return result


def _event(stage: str, status: str) -> dict[str, Any]:
    return {"stage": stage, "status": status, "at": utc_now_iso()}


def _mark_job_failed(session: Session, job: Job, events: list[dict[str, Any]], exc: VendorScrapeError) -> None:
    job.status = "failed"
    job.finished_at = utc_now_iso()
    job.error_summary = exc.message
    job.output_json = json.dumps({"events": events, "error_code": exc.code}, sort_keys=True)
    session.commit()


def _get_vendor_scrape_job(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.job_type != "vendor_scrape":
        raise VendorScrapeError("vendor_scrape_not_found", "Vendor scrape job was not found.", status_code=404)
    return job


def _synthetic_fixture_path(vendor_key: str, *, fixture_name: Optional[str] = None) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    if fixture_name:
        filename = fixture_name
    else:
        filename = f"vendor_collect_{vendor_key}.json"
    return repo_root / "tests" / "fixtures" / "synthetic" / filename


def _loads_optional(value: Optional[str]) -> Optional[dict[str, Any]]:
    if value is None:
        return None
    return json.loads(value)


def _money_decimal(value: str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> str:
    return format(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP), "f")
