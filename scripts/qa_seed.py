from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from dillon_finances.main import create_app
from dillon_finances.runtime import SYNTHETIC_ARTIFACT_MARKER, bootstrap_data_root, runtime_environment_from_env
from dillon_finances.source_profiles import list_source_profiles


SCENARIO_NAME = "baseline"
SCENARIO_VERSION = "0.3.0"


class QaSeedError(RuntimeError):
    pass


def _fresh_dates() -> tuple[str, str]:
    transaction_date = date.today() - timedelta(days=1)
    post_date = date.today()
    return transaction_date.isoformat(), post_date.isoformat()


def _source_files() -> dict[str, str]:
    transaction_date, post_date = _fresh_dates()
    return {
        "alliant_checking": "\n".join(
            [
                "Date,Description,Amount,Balance",
                f"{transaction_date},SYNTHETIC PAYROLL,2450.00,5200.00",
                f"{transaction_date},SYNTHETIC UTILITY BILL,-125.32,5074.68",
                "",
            ]
        ),
        "alliant_savings": "\n".join(
            [
                "Date,Description,Amount,Balance",
                f"{transaction_date},SYNTHETIC SAVINGS TRANSFER,300.00,12000.00",
                f"{transaction_date},SYNTHETIC INTEREST,4.25,12004.25",
                "",
            ]
        ),
        "alliant_credit_card": "\n".join(
            [
                "Date,Description,Amount,Balance,Post Date",
                f"{transaction_date},SYNTHETIC HARDWARE STORE,78.42,78.42,{post_date}",
                f"{transaction_date},SYNTHETIC CARD PAYMENT,-78.42,0.00,{post_date}",
                "",
            ]
        ),
        "chase_prime_visa": "\n".join(
            [
                "Transaction Date,Post Date,Description,Category,Amount",
                f"{transaction_date},{post_date},SYNTHETIC GROCERY MARKET,Food & Drink,-62.41",
                f"{transaction_date},{post_date},SYNTHETIC ONLINE ORDER,Shopping,-44.18",
                "",
            ]
        ),
    }


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


def _upload_source(client: TestClient, source_key: str, content: str) -> str:
    response = client.post(
        "/api/uploads",
        data={"source_key": source_key},
        files={"file": (f"SYNTHETIC_{source_key}_baseline.csv", content, "text/csv")},
    )
    if response.status_code >= 400:
        raise QaSeedError(f"upload {source_key} failed: {response.status_code} {response.text}")
    batch_id = response.json()["import_batch"]["id"]
    _post_json(client, f"/api/import-batches/{batch_id}/validate", {})
    _post_json(client, f"/api/import-batches/{batch_id}/accept", {"acknowledge_warnings": True})
    return batch_id


def seed_baseline_scenario(data_root: Path) -> Path:
    runtime_identity = runtime_environment_from_env()
    if not runtime_identity.qa_controls_enabled:
        raise QaSeedError("Baseline seed requires APP_ENV=qa, DATASET_KIND=synthetic, and DEV_MODE=true.")

    resolved_data_root = bootstrap_data_root(data_root)
    app = create_app(
        data_root=resolved_data_root,
        local_bind_host="127.0.0.1",
        runtime_environment=runtime_identity,
    )

    accepted_batch_ids: list[str] = []
    with TestClient(app) as client:
        confirmation_changes = [
            {
                "domain": "sources",
                "setting_key": f"sources.{profile.source_key}.profile_confirmation_status",
                "value": "owner_confirmed_header_sample",
                "note": f"Synthetic baseline confirms header-only source profile for {profile.source_key}.",
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

        for source_key, content in _source_files().items():
            accepted_batch_ids.append(_upload_source(client, source_key, content))

        transactions = client.get("/api/transactions").json()["transactions"]
        for transaction in transactions[:4]:
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
                    "notes": "Synthetic baseline review decision.",
                },
            )

        reports = _post_json(
            client,
            "/api/reports/run",
            {
                "actor": "system",
                "actor_context": _system_actor_context("system:report_generator"),
            },
        )
        draft_close = _post_json(
            client,
            "/api/monthly-close/draft",
            {
                "actor": "system",
                "actor_context": _system_actor_context("system:report_generator"),
                "notes": "Synthetic baseline draft close.",
            },
        )
        advisor_export = _post_json(
            client,
            "/api/exports/advisor",
            {
                "actor": "system",
                "actor_context": _system_actor_context("system:report_generator"),
            },
        )

    manifest_dir = resolved_data_root / "manifests"
    manifest_dir.mkdir(exist_ok=True)
    manifest_path = manifest_dir / f"{SCENARIO_NAME}-{SCENARIO_VERSION}.json"
    manifest_path.write_text(
        json.dumps(
            {
                "scenario": SCENARIO_NAME,
                "scenario_version": SCENARIO_VERSION,
                "dataset_kind": runtime_identity.dataset_kind,
                "synthetic_artifact_marker": SYNTHETIC_ARTIFACT_MARKER,
                "accepted_import_batch_ids": accepted_batch_ids,
                "accepted_source_keys": sorted(_source_files().keys()),
                "artifact_counts": {
                    "reports": len(reports["artifacts"]),
                    "monthly_close": len(draft_close["artifacts"]),
                    "advisor_export": len(advisor_export["artifacts"]),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a local QA synthetic scenario.")
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--scenario", default=SCENARIO_NAME, choices=[SCENARIO_NAME])
    args = parser.parse_args()

    try:
        manifest_path = seed_baseline_scenario(args.data_root)
    except QaSeedError as exc:
        parser.error(str(exc))
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
