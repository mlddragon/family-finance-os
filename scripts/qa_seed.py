from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from fastapi.testclient import TestClient

from dillon_finances import __version__
from dillon_finances.main import create_app
from dillon_finances.runtime import SYNTHETIC_ARTIFACT_MARKER, bootstrap_data_root, runtime_environment_from_env
from dillon_finances.source_profiles import list_source_profiles


BASELINE_SCENARIO = "baseline"
STALE_SOURCE_SCENARIO = "stale-source"
BLOCKED_IMPORT_SCENARIO = "blocked-import"
REVIEW_BACKLOG_SCENARIO = "review-backlog"
MONTHLY_CLOSE_READY_SCENARIO = "monthly-close-ready"
SCENARIO_VERSION = __version__

SOURCE_KEYS = (
    "alliant_checking",
    "alliant_savings",
    "alliant_credit_card",
    "chase_prime_visa",
)


class QaSeedError(RuntimeError):
    pass


def _fresh_dates() -> tuple[str, str]:
    transaction_date = date.today() - timedelta(days=1)
    post_date = date.today()
    return transaction_date.isoformat(), post_date.isoformat()


def _stale_dates() -> tuple[str, str]:
    transaction_date = date.today() - timedelta(days=60)
    post_date = transaction_date + timedelta(days=1)
    return transaction_date.isoformat(), post_date.isoformat()


def _source_files(*, stale_sources: set[str] | None = None) -> dict[str, str]:
    stale_sources = stale_sources or set()
    fresh_transaction_date, fresh_post_date = _fresh_dates()
    stale_transaction_date, stale_post_date = _stale_dates()

    def dates_for(source_key: str) -> tuple[str, str]:
        if source_key in stale_sources:
            return stale_transaction_date, stale_post_date
        return fresh_transaction_date, fresh_post_date

    checking_date, _ = dates_for("alliant_checking")
    savings_date, _ = dates_for("alliant_savings")
    alliant_card_date, alliant_card_post_date = dates_for("alliant_credit_card")
    chase_date, chase_post_date = dates_for("chase_prime_visa")
    return {
        "alliant_checking": "\n".join(
            [
                "Date,Description,Amount,Balance",
                f"{checking_date},SYNTHETIC PAYROLL,2450.00,5200.00",
                f"{checking_date},SYNTHETIC UTILITY BILL,-125.32,5074.68",
                "",
            ]
        ),
        "alliant_savings": "\n".join(
            [
                "Date,Description,Amount,Balance",
                f"{savings_date},SYNTHETIC SAVINGS TRANSFER,300.00,12000.00",
                f"{savings_date},SYNTHETIC INTEREST,4.25,12004.25",
                "",
            ]
        ),
        "alliant_credit_card": "\n".join(
            [
                "Date,Description,Amount,Balance,Post Date",
                f"{alliant_card_date},SYNTHETIC HARDWARE STORE,78.42,78.42,{alliant_card_post_date}",
                f"{alliant_card_date},SYNTHETIC CARD PAYMENT,-78.42,0.00,{alliant_card_post_date}",
                "",
            ]
        ),
        "chase_prime_visa": "\n".join(
            [
                "Transaction Date,Post Date,Description,Category,Amount",
                f"{chase_date},{chase_post_date},SYNTHETIC GROCERY MARKET,Food & Drink,-62.41",
                f"{chase_date},{chase_post_date},SYNTHETIC ONLINE ORDER,Shopping,-44.18",
                "",
            ]
        ),
    }


def _blocked_import_file() -> str:
    return "\n".join(
        [
            "Wrong,Header",
            "SYNTHETIC WRONG HEADER,12.34",
            "",
        ]
    )


def _system_actor_context(system_persona_key: str) -> dict[str, Any]:
    return {
        "actor_key": "system",
        "actor_type": "system",
        "display_name": "System",
        "group_keys": [],
        "system_persona_key": system_persona_key,
        "source": "system",
    }


def _owner_actor_context() -> dict[str, Any]:
    return {
        "actor_key": "owner",
        "actor_type": "human",
        "display_name": "Owner",
        "persona_key": "finance_manager",
        "persona_label": "Finance Manager",
        "group_keys": ["administrator", "finance_manager"],
        "source": "local_selector",
    }


def _post_json(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    if response.status_code >= 400:
        raise QaSeedError(f"{path} failed: {response.status_code} {response.text}")
    return response.json()


def _patch_json(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.patch(path, json=payload)
    if response.status_code >= 400:
        raise QaSeedError(f"{path} failed: {response.status_code} {response.text}")
    return response.json()


def _upload_source(
    client: TestClient,
    source_key: str | None,
    content: str,
    *,
    scenario_name: str,
) -> str:
    data: dict[str, str] = {}
    filename_source = source_key or "unknown_source"
    if source_key:
        data["source_key"] = source_key
    response = client.post(
        "/api/uploads",
        data=data,
        files={"file": (f"SYNTHETIC_{filename_source}_{scenario_name}.csv", content, "text/csv")},
    )
    if response.status_code >= 400:
        raise QaSeedError(f"upload {filename_source} failed: {response.status_code} {response.text}")
    return response.json()["import_batch"]["id"]


def _validate_batch(client: TestClient, batch_id: str) -> dict[str, Any]:
    return _post_json(client, f"/api/import-batches/{batch_id}/validate", {})


def _accept_batch(client: TestClient, batch_id: str, *, acknowledge_warnings: bool = True) -> dict[str, Any]:
    return _post_json(
        client,
        f"/api/import-batches/{batch_id}/accept",
        {"acknowledge_warnings": acknowledge_warnings},
    )


def _try_accept_batch(client: TestClient, batch_id: str, *, acknowledge_warnings: bool = True) -> dict[str, Any]:
    response = client.post(
        f"/api/import-batches/{batch_id}/accept",
        json={"acknowledge_warnings": acknowledge_warnings},
    )
    if response.status_code not in {200, 409}:
        raise QaSeedError(f"accept {batch_id} failed: {response.status_code} {response.text}")
    return {"status_code": response.status_code, "body": response.json()}


def _confirm_source_profiles(client: TestClient) -> None:
    confirmation_changes = [
        {
            "domain": "sources",
            "setting_key": f"sources.{profile.source_key}.profile_confirmation_status",
            "value": "owner_confirmed_header_sample",
            "note": f"Synthetic QA confirms header-only source profile for {profile.source_key}.",
        }
        for profile in list_source_profiles()
    ]
    _patch_json(
        client,
        "/api/settings",
        {
            "actor": "system",
            "actor_context": _system_actor_context("system:importer"),
            "changes": confirmation_changes,
        },
    )


def _enable_required_sources(client: TestClient, source_keys: tuple[str, ...] = SOURCE_KEYS) -> None:
    _patch_json(
        client,
        "/api/settings",
        {
            "actor": "system",
            "actor_context": _system_actor_context("system:validator"),
            "changes": [
                {
                    "domain": "sources",
                    "setting_key": f"sources.{source_key}.required",
                    "value": True,
                    "note": f"Synthetic QA marks {source_key} as required for scenario coverage.",
                }
                for source_key in source_keys
            ],
        },
    )


def _review_transactions(client: TestClient, *, limit: int | None = None) -> int:
    transactions = client.get("/api/transactions").json()["transactions"]
    selected_transactions = transactions if limit is None else transactions[:limit]
    for transaction in selected_transactions:
        _post_json(
            client,
            "/api/decision-events",
            {
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "review_status_change",
                "field_name": "review_status",
                "proposed_value": "reviewed",
                "approved_value": "reviewed",
                "actor": "owner",
                "actor_context": _owner_actor_context(),
                "suggestion_source": "owner",
                "explicit_user_action": True,
                "notes": "Synthetic QA review decision.",
            },
        )
    return len(selected_transactions)


def _run_reports(client: TestClient) -> dict[str, Any]:
    return _post_json(
        client,
        "/api/reports/run",
        {
            "actor": "system",
            "actor_context": _system_actor_context("system:report_generator"),
        },
    )


def _draft_close(client: TestClient, *, notes: str) -> dict[str, Any]:
    return _post_json(
        client,
        "/api/monthly-close/draft",
        {
            "actor": "system",
            "actor_context": _system_actor_context("system:report_generator"),
            "notes": notes,
        },
    )


def _finalize_close(client: TestClient, *, notes: str) -> dict[str, Any]:
    return _post_json(
        client,
        "/api/monthly-close/finalize",
        {
            "actor": "owner",
            "actor_context": _owner_actor_context(),
            "notes": notes,
        },
    )


def _try_finalize_close(client: TestClient, *, notes: str) -> dict[str, Any]:
    response = client.post(
        "/api/monthly-close/finalize",
        json={
            "actor": "owner",
            "actor_context": _owner_actor_context(),
            "notes": notes,
        },
    )
    if response.status_code not in {200, 409}:
        raise QaSeedError(f"monthly close finalize failed: {response.status_code} {response.text}")
    return {"status_code": response.status_code, "body": response.json()}


def _advisor_export(client: TestClient) -> dict[str, Any]:
    return _post_json(
        client,
        "/api/exports/advisor",
        {
            "actor": "system",
            "actor_context": _system_actor_context("system:report_generator"),
        },
    )


def _accepted_imports(
    client: TestClient,
    *,
    scenario_name: str,
    source_files: dict[str, str],
) -> list[str]:
    accepted_batch_ids: list[str] = []
    for source_key, content in source_files.items():
        batch_id = _upload_source(client, source_key, content, scenario_name=scenario_name)
        _validate_batch(client, batch_id)
        _accept_batch(client, batch_id, acknowledge_warnings=True)
        accepted_batch_ids.append(batch_id)
    return accepted_batch_ids


def _operator_state(client: TestClient) -> dict[str, Any]:
    summary = client.get("/api/operator-summary")
    if summary.status_code >= 400:
        raise QaSeedError(f"operator summary failed: {summary.status_code} {summary.text}")
    validation = client.get("/api/validation-findings")
    if validation.status_code >= 400:
        raise QaSeedError(f"validation findings failed: {validation.status_code} {validation.text}")
    transactions = client.get("/api/transactions")
    if transactions.status_code >= 400:
        raise QaSeedError(f"transactions failed: {transactions.status_code} {transactions.text}")
    artifacts = client.get("/api/artifacts")
    if artifacts.status_code >= 400:
        raise QaSeedError(f"artifacts failed: {artifacts.status_code} {artifacts.text}")

    findings = validation.json()["findings"]
    transactions_payload = transactions.json()["transactions"]
    return {
        "operator_summary": summary.json(),
        "validation_findings": {
            "total": len(findings),
            "open_blocking": len(
                [
                    finding
                    for finding in findings
                    if finding["status"] == "open" and finding["severity"] == "blocking"
                ]
            ),
            "open_warning": len(
                [
                    finding
                    for finding in findings
                    if finding["status"] == "open" and finding["severity"] == "warning"
                ]
            ),
            "codes": sorted({finding["code"] for finding in findings if finding["status"] == "open"}),
        },
        "transactions": {
            "total": len(transactions_payload),
            "reviewed": len(
                [transaction for transaction in transactions_payload if transaction["review_status"] == "reviewed"]
            ),
            "unreviewed": len(
                [transaction for transaction in transactions_payload if transaction["review_status"] == "unreviewed"]
            ),
            "blocked": len(
                [transaction for transaction in transactions_payload if transaction["validation_status"] == "blocked"]
            ),
        },
        "artifact_total": len(artifacts.json()["artifacts"]),
    }


def _write_manifest(
    *,
    data_root: Path,
    scenario_name: str,
    payload: dict[str, Any],
) -> Path:
    manifest_dir = data_root / "manifests"
    manifest_dir.mkdir(exist_ok=True)
    manifest_path = manifest_dir / f"{scenario_name}-{SCENARIO_VERSION}.json"
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return manifest_path


def _scenario_context(data_root: Path) -> tuple[Path, TestClient]:
    runtime_identity = runtime_environment_from_env()
    if not runtime_identity.qa_controls_enabled:
        raise QaSeedError("QA seed requires APP_ENV=qa, DATASET_KIND=synthetic, and DEV_MODE=true.")

    resolved_data_root = bootstrap_data_root(data_root)
    app = create_app(
        data_root=resolved_data_root,
        local_bind_host="127.0.0.1",
        runtime_environment=runtime_identity,
    )
    return resolved_data_root, TestClient(app)


def seed_baseline_scenario(data_root: Path) -> Path:
    return seed_scenario(data_root, BASELINE_SCENARIO)


def _seed_baseline(client: TestClient) -> dict[str, Any]:
    accepted_batch_ids: list[str] = []
    _confirm_source_profiles(client)
    accepted_batch_ids.extend(
        _accepted_imports(client, scenario_name=BASELINE_SCENARIO, source_files=_source_files())
    )
    reviewed_count = _review_transactions(client, limit=4)
    reports = _run_reports(client)
    draft_close = _draft_close(client, notes="Synthetic baseline draft close.")
    advisor_export = _advisor_export(client)

    return {
        "description": "Smallest useful closed loop with accepted imports, several reviewed transactions, reports, draft close, and advisor export.",
        "accepted_import_batch_ids": accepted_batch_ids,
        "accepted_source_keys": sorted(_source_files().keys()),
        "reviewed_transaction_count": reviewed_count,
        "artifact_counts": {
            "reports": len(reports["artifacts"]),
            "monthly_close": len(draft_close["artifacts"]),
            "advisor_export": len(advisor_export["artifacts"]),
        },
        "expected_operator_state": {
            "next_action": "review_ledger_decisions",
            "open_blocking": 0,
            "review_unreviewed_min": 1,
        },
    }


def _seed_stale_source(client: TestClient) -> dict[str, Any]:
    _confirm_source_profiles(client)
    _enable_required_sources(client)
    accepted_batch_ids = _accepted_imports(
        client,
        scenario_name=STALE_SOURCE_SCENARIO,
        source_files=_source_files(stale_sources={"chase_prime_visa"}),
    )
    reviewed_count = _review_transactions(client)
    finalize_attempt = _try_finalize_close(client, notes="Synthetic stale-source final close should be blocked.")
    return {
        "description": "Required source coverage where Chase is accepted but stale against the freshness threshold.",
        "accepted_import_batch_ids": accepted_batch_ids,
        "accepted_source_keys": sorted(_source_files().keys()),
        "reviewed_transaction_count": reviewed_count,
        "blocked_finalize_status_code": finalize_attempt["status_code"],
        "expected_operator_state": {
            "next_action": "run_reports_monthly_close",
            "stale_required_sources": ["chase_prime_visa"],
            "open_warning_codes": ["source_stale"],
            "final_close_blocked": True,
        },
    }


def _seed_blocked_import(client: TestClient) -> dict[str, Any]:
    _confirm_source_profiles(client)
    batch_id = _upload_source(
        client,
        None,
        _blocked_import_file(),
        scenario_name=BLOCKED_IMPORT_SCENARIO,
    )
    validation = _validate_batch(client, batch_id)
    accept_attempt = _try_accept_batch(client, batch_id, acknowledge_warnings=True)
    return {
        "description": "A blocked schema mismatch import that should remain unresolved and quarantined.",
        "blocked_import_batch_id": batch_id,
        "blocked_accept_status_code": accept_attempt["status_code"],
        "blocked_validation_codes": sorted({finding["code"] for finding in validation["findings"]}),
        "expected_operator_state": {
            "next_action": "resolve_validation_blockers",
            "open_blocking_codes": ["schema_mismatch"],
            "quarantine_expected": True,
        },
    }


def _seed_review_backlog(client: TestClient) -> dict[str, Any]:
    _confirm_source_profiles(client)
    accepted_batch_ids = _accepted_imports(
        client,
        scenario_name=REVIEW_BACKLOG_SCENARIO,
        source_files=_source_files(),
    )
    return {
        "description": "Accepted imports with intentionally unreviewed transactions for Ledger Review QA.",
        "accepted_import_batch_ids": accepted_batch_ids,
        "accepted_source_keys": sorted(_source_files().keys()),
        "expected_operator_state": {
            "next_action": "review_ledger_decisions",
            "review_unreviewed_min": 1,
            "open_blocking": 0,
        },
    }


def _seed_monthly_close_ready(client: TestClient) -> dict[str, Any]:
    _confirm_source_profiles(client)
    _enable_required_sources(client)
    accepted_batch_ids = _accepted_imports(
        client,
        scenario_name=MONTHLY_CLOSE_READY_SCENARIO,
        source_files=_source_files(),
    )
    reviewed_count = _review_transactions(client)
    reports = _run_reports(client)
    draft_close = _draft_close(client, notes="Synthetic monthly-close-ready draft close.")
    final_close = _finalize_close(client, notes="Synthetic monthly-close-ready final close.")
    advisor_export = _advisor_export(client)
    return {
        "description": "Fully reviewed and final-close-ready dataset with reports, draft close, final close, and advisor export.",
        "accepted_import_batch_ids": accepted_batch_ids,
        "accepted_source_keys": sorted(_source_files().keys()),
        "reviewed_transaction_count": reviewed_count,
        "monthly_close_status": final_close["monthly_close"]["status"],
        "artifact_counts": {
            "reports": len(reports["artifacts"]),
            "monthly_close_draft": len(draft_close["artifacts"]),
            "monthly_close_final": len(final_close["artifacts"]),
            "advisor_export": len(advisor_export["artifacts"]),
        },
        "expected_operator_state": {
            "next_action": "refresh_source_data",
            "monthly_close_status": "final",
            "ready_for_final": True,
            "open_blocking": 0,
            "review_unreviewed": 0,
        },
    }


SCENARIOS: dict[str, Callable[[TestClient], dict[str, Any]]] = {
    BASELINE_SCENARIO: _seed_baseline,
    STALE_SOURCE_SCENARIO: _seed_stale_source,
    BLOCKED_IMPORT_SCENARIO: _seed_blocked_import,
    REVIEW_BACKLOG_SCENARIO: _seed_review_backlog,
    MONTHLY_CLOSE_READY_SCENARIO: _seed_monthly_close_ready,
}


def seed_scenario(data_root: Path, scenario_name: str) -> Path:
    if scenario_name not in SCENARIOS:
        raise QaSeedError(f"Unknown QA scenario: {scenario_name}.")

    runtime_identity = runtime_environment_from_env()
    resolved_data_root, client_context = _scenario_context(data_root)
    with client_context as client:
        scenario_payload = SCENARIOS[scenario_name](client)
        payload = {
            "scenario": scenario_name,
            "scenario_version": SCENARIO_VERSION,
            "dataset_kind": runtime_identity.dataset_kind,
            "synthetic_artifact_marker": SYNTHETIC_ARTIFACT_MARKER,
            **scenario_payload,
            **_operator_state(client),
        }

    return _write_manifest(data_root=resolved_data_root, scenario_name=scenario_name, payload=payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a local QA synthetic scenario.")
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--scenario", default=BASELINE_SCENARIO, choices=sorted(SCENARIOS))
    args = parser.parse_args()

    try:
        manifest_path = seed_scenario(args.data_root, args.scenario)
    except QaSeedError as exc:
        parser.error(str(exc))
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
