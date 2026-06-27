from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_to_json, derive_actor_context
from family_finance_os.funds import funds_summary
from family_finance_os.ledger_normalization import list_transactions
from family_finance_os.models import Job, utc_now_iso
from family_finance_os.net_worth import net_worth_summary
from family_finance_os.reporting import (
    ReportingError,
    _cashflow_summary,
    _category_spending_summary,
    _dump,
    _loads_optional,
    _review_backlog_summary,
    _reviewed_transaction_rows,
    close_readiness,
    default_month,
    ensure_safe_artifact_directory,
    serialize_artifact,
    serialize_job,
    _write_csv_artifact,
    _write_json_artifact,
    _write_text_artifact,
)

PROMPT_LIBRARY_DIR = Path(__file__).resolve().parent / "prompt_library"
PROMPT_KEYS = {
    "monthly_spending_review": "monthly_spending_review.md",
    "cashflow_savings_rate": "cashflow_savings_rate.md",
    "goal_progress_check_in": "goal_progress_check_in.md",
}


class AnalystExportRequest(BaseModel):
    actor: str = Field(min_length=1)
    actor_context: Optional[ActorContext] = None
    month: Optional[str] = None
    include_raw_transactions: bool = False
    include_estimates: bool = False
    prompt_key: str = "monthly_spending_review"


def list_analyst_pack_prompts() -> dict[str, Any]:
    prompts = []
    for key, filename in PROMPT_KEYS.items():
        path = PROMPT_LIBRARY_DIR / filename
        prompts.append({"prompt_key": key, "title": key.replace("_", " ").title(), "available": path.exists()})
    return {"prompts": prompts}


def analyst_pack_options(session: Session, *, month: Optional[str] = None) -> dict[str, Any]:
    target_month = month or default_month(session)
    readiness = close_readiness(session, month=target_month)
    return {
        "month": target_month,
        "sections": [
            {"key": "cashflow_summary", "label": "Cashflow summary", "included_by_default": True},
            {"key": "category_spending", "label": "Category spending totals", "included_by_default": True},
            {"key": "fund_pools", "label": "Fund pool commitments and Pool remaining", "included_by_default": True},
            {"key": "reserved_goals", "label": "Reserved goal balance", "included_by_default": True},
            {"key": "net_worth_actual", "label": "Net worth (actual only)", "included_by_default": True},
            {
                "key": "net_worth_estimates",
                "label": "Net worth (include estimates)",
                "included_by_default": False,
                "requires_include_estimates": True,
            },
            {"key": "review_backlog", "label": "Review backlog", "included_by_default": True},
            {"key": "recurring_candidates", "label": "Recurring transaction candidates", "included_by_default": True},
            {"key": "validation_notes", "label": "Validation and source freshness notes", "included_by_default": True},
            {
                "key": "raw_transactions",
                "label": "Reviewed transaction rows",
                "included_by_default": False,
                "requires_include_raw_transactions": True,
            },
        ],
        "validation_summary": readiness,
        "privacy_boundary": "local_file_only_no_in_app_ai",
    }


def build_analyst_pack(
    session: Session,
    data_root: Path,
    request: AnalystExportRequest,
    *,
    synthetic_artifact_marker: Optional[str] = None,
) -> dict[str, Any]:
    if request.prompt_key not in PROMPT_KEYS:
        raise ReportingError(
            "analyst_pack_prompt_not_found",
            f"Prompt key {request.prompt_key!r} was not found.",
            status_code=404,
        )
    prompt_path = PROMPT_LIBRARY_DIR / PROMPT_KEYS[request.prompt_key]
    if not prompt_path.exists():
        raise ReportingError(
            "analyst_pack_prompt_not_found",
            f"Prompt template for {request.prompt_key!r} is missing.",
            status_code=404,
        )

    month = request.month or default_month(session)
    validation_summary = close_readiness(session, month=month)
    funds = funds_summary(session, month=month)
    net_worth_actual = net_worth_summary(session, include_estimates=False)
    net_worth_with_estimates = net_worth_summary(session, include_estimates=True) if request.include_estimates else None
    recurring = _recurring_heuristic_summary(session)
    summary_payload = {
        "schema_version": "v1.1",
        "month": month,
        "generated_at": utc_now_iso(),
        "confidence": funds["spendable"].get("confidence"),
        "provisional": not validation_summary["ready_for_final"],
        "cashflow": _cashflow_summary(session),
        "category_spending": _category_spending_summary(session),
        "fund_pools": funds["pools"],
        "commitment_health": funds["commitment_health"],
        "reserved_goal_balance": funds["spendable"]["reserved_goal_balance"],
        "net_worth_actual": net_worth_actual,
        "net_worth_with_estimates": net_worth_with_estimates,
        "review_backlog": _review_backlog_summary(session),
        "recurring_candidates": recurring,
        "validation_summary": validation_summary,
    }
    input_snapshot = {
        "month": month,
        "include_raw_transactions": request.include_raw_transactions,
        "include_estimates": request.include_estimates,
        "prompt_key": request.prompt_key,
        "validation_summary": validation_summary,
    }
    job = Job(
        job_type="analyst_pack_export",
        status="running",
        actor=request.actor,
        actor_context_json=actor_context_to_json(derive_actor_context(request.actor, request.actor_context)),
        input_json=_dump(input_snapshot),
    )
    session.add(job)
    session.flush()
    export_dir = ensure_safe_artifact_directory(data_root, data_root / "exports" / "analyst_pack" / job.id)
    prompt_dir = export_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = prompt_path.read_text(encoding="utf-8")
    prompt_artifact = _write_text_artifact(
        session,
        prompt_dir / f"{request.prompt_key}.md",
        data_root=data_root,
        artifact_type="analyst_pack_prompt",
        text=prompt_text,
        job=job,
        source_inputs=input_snapshot,
        title=f"Analyst Prompt: {request.prompt_key}",
        description="Local prompt template copied into the analyst pack.",
        sensitivity="household_financial_configuration",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    summary_artifact = _write_json_artifact(
        session,
        export_dir / "summary.json",
        data_root=data_root,
        artifact_type="analyst_pack_summary",
        payload=summary_payload,
        job=job,
        source_inputs=input_snapshot,
        title="Analyst Pack Summary",
        description="Structured household summary for external analyst review.",
        sensitivity="household_financial_summary",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    summary_md = _summary_markdown(summary_payload)
    summary_md_artifact = _write_text_artifact(
        session,
        export_dir / "summary.md",
        data_root=data_root,
        artifact_type="analyst_pack_summary_markdown",
        text=summary_md,
        job=job,
        source_inputs=input_snapshot,
        title="Analyst Pack Summary (Markdown)",
        description="Human-readable analyst pack summary.",
        sensitivity="household_financial_summary",
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    artifacts = [prompt_artifact, summary_artifact, summary_md_artifact]
    if request.include_raw_transactions:
        artifacts.append(
            _write_csv_artifact(
                session,
                export_dir / "reviewed_transactions.csv",
                data_root=data_root,
                artifact_type="analyst_pack_transactions_export",
                rows=_reviewed_transaction_rows(session),
                job=job,
                source_inputs=input_snapshot,
                title="Analyst Pack Transaction Export",
                description="Optional reviewed transaction rows for external analyst review.",
                sensitivity="household_financial_export",
                synthetic_artifact_marker=synthetic_artifact_marker,
            )
        )
    manifest_payload = {
        "schema_version": "v1.1",
        "pack_type": "analyst_pack",
        "month": month,
        "generated_at": utc_now_iso(),
        "includes_raw_transactions": request.include_raw_transactions,
        "includes_estimates": request.include_estimates,
        "prompt_key": request.prompt_key,
        "artifacts": [serialize_artifact(artifact) for artifact in artifacts],
        "validation_summary": validation_summary,
        "privacy_boundary": "local_file_only_no_in_app_ai",
    }
    if synthetic_artifact_marker:
        manifest_payload["synthetic_artifact_marker"] = synthetic_artifact_marker
    manifest_artifact = _write_json_artifact(
        session,
        export_dir / "manifest.json",
        data_root=data_root,
        artifact_type="analyst_pack_manifest",
        payload=manifest_payload,
        job=job,
        source_inputs=input_snapshot,
        title="Analyst Pack Manifest",
        description="Machine-readable manifest for the analyst export pack.",
        sensitivity="household_financial_summary",
        compact=True,
        synthetic_artifact_marker=synthetic_artifact_marker,
    )
    artifacts.append(manifest_artifact)
    job.status = "completed"
    job.finished_at = utc_now_iso()
    job.output_json = _dump({"month": month, "artifact_count": len(artifacts), "manifest": manifest_payload})
    session.commit()
    return {
        "job": serialize_job(job),
        "validation_summary": validation_summary,
        "manifest": manifest_payload,
        "artifacts": [serialize_artifact(artifact) for artifact in artifacts],
    }


def _summary_markdown(summary_payload: dict[str, Any]) -> str:
    cashflow = summary_payload["cashflow"]
    return "\n".join(
        [
            "# Analyst Pack Summary",
            "",
            f"Month: {summary_payload['month']}",
            f"Generated at: {summary_payload['generated_at']}",
            f"Provisional: {summary_payload['provisional']}",
            "",
            "## Cashflow",
            f"- Inflow: {cashflow['inflow']}",
            f"- Outflow: {cashflow['outflow']}",
            f"- Net: {cashflow['net']}",
            "",
            "## Privacy boundary",
            "Local file generation only. No in-app AI or external service calls.",
        ]
    )


def _recurring_heuristic_summary(session: Session) -> dict[str, Any]:
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for transaction in list_transactions(session):
        if transaction["review_status"] != "reviewed":
            continue
        merchant = (transaction.get("normalized_merchant") or transaction.get("raw_description") or "unknown").casefold()
        amount = abs(Decimal(str(transaction["amount"])))
        month = str(transaction["posted_date"])[:7]
        groups[merchant].append({"month": month, "amount": amount, "transaction_id": transaction["id"]})

    candidates = []
    for merchant, occurrences in groups.items():
        if len(occurrences) < 3:
            continue
        months = sorted({item["month"] for item in occurrences})
        amounts = [item["amount"] for item in occurrences]
        amount_band = max(amounts) - min(amounts)
        candidates.append(
            {
                "merchant": merchant,
                "occurrence_count": len(occurrences),
                "months": months,
                "amount_band": str(amount_band.quantize(Decimal("0.01"))),
                "confidence": "candidate",
                "reason": "At least three reviewed occurrences with stable merchant identity.",
            }
        )
    return {"candidates": sorted(candidates, key=lambda item: item["merchant"])}
