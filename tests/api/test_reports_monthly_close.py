from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from family_finance_os.main import create_app
from family_finance_os.runtime import DataRootConfigurationError


CHASE_HEADER = "Transaction Date,Post Date,Description,Category,Amount\n"


def fresh_row(description: str = "SYNTHETIC GROCERY", amount: str = "12.34") -> str:
    transaction_date = date.today() - timedelta(days=1)
    post_date = date.today()
    return (
        f"{transaction_date.isoformat()},{post_date.isoformat()},"
        f"{description},Food,{amount}\n"
    )


def write_inbox_file(data_root: Path, filename: str, content: str) -> None:
    inbox_path = data_root / "inbox" / filename
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(content)


def accept_first_batch(client: TestClient) -> dict:
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    validation_response = client.post(f"/api/import-batches/{batch_id}/validate")
    assert validation_response.status_code == 200
    accept_response = client.post(f"/api/import-batches/{batch_id}/accept")
    assert accept_response.status_code == 200
    return accept_response.json()


def create_accepted_chase_batch(client: TestClient, data_root: Path) -> dict:
    write_inbox_file(
        data_root,
        "SYNTHETIC_chase_reports.csv",
        CHASE_HEADER
        + fresh_row("SYNTHETIC GROCERY", "12.34")
        + fresh_row("SYNTHETIC FUEL", "45.67"),
    )
    return accept_first_batch(client)


def disable_unavailable_required_sources(client: TestClient) -> None:
    response = client.patch(
        "/api/settings",
        json={
            "actor": "mason",
            "changes": [
                {
                    "domain": "sources",
                    "setting_key": "sources.alliant_checking.required",
                    "value": False,
                    "note": "Synthetic PR9 final close covers Chase only until owner source samples are confirmed.",
                },
                {
                    "domain": "sources",
                    "setting_key": "sources.alliant_savings.required",
                    "value": False,
                    "note": "Synthetic PR9 final close covers Chase only until owner source samples are confirmed.",
                },
                {
                    "domain": "sources",
                    "setting_key": "sources.alliant_credit_card.required",
                    "value": False,
                    "note": "Synthetic PR9 final close covers Chase only until owner source samples are confirmed.",
                },
            ],
        },
    )
    assert response.status_code == 200


def enable_required_sources(client: TestClient, *source_keys: str) -> None:
    response = client.patch(
        "/api/settings",
        json={
            "actor": "mason",
            "changes": [
                {
                    "domain": "sources",
                    "setting_key": f"sources.{source_key}.required",
                    "value": True,
                    "note": f"Synthetic test enables required source coverage for {source_key}.",
                }
                for source_key in source_keys
            ],
        },
    )
    assert response.status_code == 200


def confirm_source_profile_sample(client: TestClient, source_key: str) -> None:
    response = client.patch(
        "/api/settings",
        json={
            "actor": "mason",
            "changes": [
                {
                    "domain": "sources",
                    "setting_key": f"sources.{source_key}.profile_confirmation_status",
                    "value": "owner_confirmed_header_sample",
                    "note": f"Synthetic confirmation of header-only sample for {source_key}.",
                }
            ],
        },
    )
    assert response.status_code == 200


def artifact_paths(body: dict) -> list[Path]:
    return [Path(artifact["path"]) for artifact in body["artifacts"]]


def assert_artifact_registry_integrity(artifact: dict, *, expected_root: Path, expected_job_id: str) -> None:
    path = Path(artifact["path"])
    content = path.read_bytes()

    assert path.exists()
    assert path.is_relative_to(expected_root)
    assert artifact["sha256"] == hashlib.sha256(content).hexdigest()
    assert artifact["byte_size"] == len(content)
    assert artifact["producing_job_id"] == expected_job_id
    assert artifact["source_inputs"]["month"]
    assert artifact["source_inputs"]["validation_summary"]
    assert artifact["retention_category"] == "v1_operational_artifact"
    assert artifact["sensitivity"].startswith("household_financial_")


def test_report_run_generates_registered_core_artifacts(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accepted_batch = create_accepted_chase_batch(client, tmp_path)
        response = client.post("/api/reports/run", json={"actor": "mason"})
        artifacts_response = client.get("/api/artifacts")
        summary_response = client.get("/api/operator-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["status"] == "completed"
    assert body["report_run"]["status"] == "completed"
    assert body["report_run"]["validation_status"] == "passed"
    artifact_types = {artifact["artifact_type"] for artifact in body["artifacts"]}
    assert {
        "import_validation_summary",
        "cashflow_summary",
        "category_spending_summary",
        "review_backlog_summary",
        "top_merchants_sources",
        "reviewed_transactions_export",
    }.issubset(artifact_types)
    assert all(path.exists() and path.is_relative_to(tmp_path / "reports") for path in artifact_paths(body))
    assert accepted_batch["id"] in body["report_run"]["input_snapshot"]["import_batch_ids"]
    assert artifacts_response.status_code == 200
    assert len(artifacts_response.json()["artifacts"]) == len(body["artifacts"])
    assert summary_response.status_code == 200
    assert summary_response.json()["artifacts"] == {
        "generated_count": len(body["artifacts"]),
        "status": "available",
    }


def test_report_artifacts_include_integrity_and_source_input_metadata(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accepted_batch = create_accepted_chase_batch(client, tmp_path)
        response = client.post("/api/reports/run", json={"actor": "mason"})

    assert response.status_code == 200
    body = response.json()
    expected_job_id = body["job"]["id"]
    for artifact in body["artifacts"]:
        assert_artifact_registry_integrity(
            artifact,
            expected_root=tmp_path / "reports",
            expected_job_id=expected_job_id,
        )
        assert artifact["source_inputs"]["import_batch_ids"] == [accepted_batch["id"]]
        assert artifact["source_inputs"]["validation_summary"]["accepted_import_batch_ids"] == [
            accepted_batch["id"]
        ]

    artifact_by_type = {artifact["artifact_type"]: artifact for artifact in body["artifacts"]}
    assert artifact_by_type["reviewed_transactions_export"]["sensitivity"] == "household_financial_export"
    assert artifact_by_type["import_validation_summary"]["sensitivity"] == "household_financial_summary"


def test_report_run_blocks_artifact_root_symlink_escape(tmp_path):
    outside_reports_dir = tmp_path.parent / f"{tmp_path.name}_outside_reports"
    outside_reports_dir.mkdir()
    (tmp_path / "reports").symlink_to(outside_reports_dir, target_is_directory=True)
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with pytest.raises(DataRootConfigurationError, match="DATA_ROOT/reports must be a safe directory"):
        with TestClient(app):
            pass
    assert list(outside_reports_dir.iterdir()) == []


def test_monthly_close_draft_writes_provisional_manifest_and_bundle(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        response = client.post("/api/monthly-close/draft", json={"actor": "mason"})
        summary_response = client.get("/api/operator-summary")

    assert response.status_code == 200
    assert summary_response.status_code == 200
    body = response.json()
    assert body["monthly_close"]["status"] == "draft"
    assert body["monthly_close"]["provisional"] is True
    assert summary_response.json()["monthly_close"]["status"] == "draft"
    assert body["validation_summary"]["missing_required_count"] == 0
    artifact_types = {artifact["artifact_type"] for artifact in body["artifacts"]}
    assert {"monthly_close_manifest", "monthly_close_memo", "settings_snapshot", "decision_event_export"}.issubset(
        artifact_types
    )
    manifest = next(path for path in artifact_paths(body) if path.name == "manifest.json")
    assert manifest.exists()
    assert manifest.is_relative_to(tmp_path / "monthly_close")
    assert '"status":"draft"' in manifest.read_text()


def test_monthly_close_manifest_references_registered_bundle_artifacts(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        response = client.post("/api/monthly-close/draft", json={"actor": "mason"})

    assert response.status_code == 200
    body = response.json()
    expected_job_id = body["job"]["id"]
    artifact_by_type = {artifact["artifact_type"]: artifact for artifact in body["artifacts"]}
    manifest_artifact = artifact_by_type["monthly_close_manifest"]
    manifest = json.loads(Path(manifest_artifact["path"]).read_text())

    for artifact in body["artifacts"]:
        assert_artifact_registry_integrity(
            artifact,
            expected_root=tmp_path / "monthly_close",
            expected_job_id=expected_job_id,
        )
        assert artifact["source_inputs"]["monthly_close_id"] == body["monthly_close"]["id"]
        assert artifact["source_inputs"]["validation_summary"] == body["validation_summary"]

    manifest_artifact_ids = {artifact["id"] for artifact in manifest["artifacts"]}
    expected_bundle_artifact_ids = {
        artifact_by_type["monthly_close_memo"]["id"],
        artifact_by_type["settings_snapshot"]["id"],
        artifact_by_type["decision_event_export"]["id"],
        artifact_by_type["fund_pool_summary"]["id"],
        artifact_by_type["spendable_snapshot"]["id"],
    }
    assert manifest["monthly_close_id"] == body["monthly_close"]["id"]
    assert manifest["status"] == "draft"
    assert manifest["validation_summary"] == body["validation_summary"]
    assert manifest_artifact_ids == expected_bundle_artifact_ids


def test_monthly_close_blocks_artifact_root_symlink_escape(tmp_path):
    outside_close_dir = tmp_path.parent / f"{tmp_path.name}_outside_monthly_close"
    outside_close_dir.mkdir()
    (tmp_path / "monthly_close").symlink_to(outside_close_dir, target_is_directory=True)
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with pytest.raises(DataRootConfigurationError, match="DATA_ROOT/monthly_close must be a safe directory"):
        with TestClient(app):
            pass
    assert list(outside_close_dir.iterdir()) == []


def test_final_close_blocks_missing_required_source_coverage(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_required_sources(
            client,
            "alliant_checking",
            "alliant_savings",
            "alliant_credit_card",
            "chase_prime_visa",
        )
        create_accepted_chase_batch(client, tmp_path)
        response = client.post("/api/monthly-close/finalize", json={"actor": "mason"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "final_close_blocked"
    assert "missing_required_sources" in detail["validation_summary"]
    assert detail["validation_summary"]["missing_required_count"] == 3


def test_final_close_blocks_unconfirmed_required_source_profiles(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_required_sources(client, "chase_prime_visa")
        create_accepted_chase_batch(client, tmp_path)
        readiness_before_confirmation = client.post(
            "/api/monthly-close/finalize",
            json={"actor": "mason", "notes": "Synthetic final close should wait for source confirmation."},
        )

        assert readiness_before_confirmation.status_code == 409
        detail = readiness_before_confirmation.json()["detail"]
        assert detail["code"] == "final_close_blocked"
        assert "unconfirmed_source_profiles" in detail["validation_summary"]["blockers"]
        assert detail["validation_summary"]["unconfirmed_source_profiles"] == ["chase_prime_visa"]

        confirm_source_profile_sample(client, "chase_prime_visa")
        readiness_after_confirmation = client.post(
            "/api/monthly-close/finalize",
            json={"actor": "mason", "notes": "Synthetic final close after profile confirmation."},
        )

    assert readiness_after_confirmation.status_code == 200
    assert readiness_after_confirmation.json()["validation_summary"]["unconfirmed_source_profiles"] == []


def test_monthly_close_duplicate_month_status_returns_controlled_conflict(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        first_response = client.post("/api/monthly-close/draft", json={"actor": "mason"})
        second_response = client.post("/api/monthly-close/draft", json={"actor": "mason"})

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"]["code"] == "monthly_close_already_exists"


def test_final_close_writes_immutable_bundle_after_owner_required_source_settings_change(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_required_sources(client, "chase_prime_visa")
        create_accepted_chase_batch(client, tmp_path)
        confirm_source_profile_sample(client, "chase_prime_visa")
        response = client.post(
            "/api/monthly-close/finalize",
            json={"actor": "mason", "notes": "Synthetic final close after explicit source requirement settings review."},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["monthly_close"]["status"] == "final"
    assert body["monthly_close"]["provisional"] is False
    assert body["validation_summary"]["missing_required_count"] == 0
    bundle_path = Path(body["monthly_close"]["artifact_folder_path"])
    assert bundle_path.exists()
    assert bundle_path.is_relative_to(tmp_path / "monthly_close")
    assert (bundle_path / "manifest.json").exists()
    assert all(path.exists() for path in artifact_paths(body))


def test_advisor_export_is_explicit_owner_action_and_carries_validation_state(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        missing_actor = client.post("/api/exports/advisor", json={})
        response = client.post("/api/exports/advisor", json={"actor": "mason"})

    assert missing_actor.status_code == 422
    assert response.status_code == 200
    body = response.json()
    assert body["job"]["job_type"] == "advisor_export"
    assert body["validation_summary"]["missing_required_count"] == 0
    artifact_types = {artifact["artifact_type"] for artifact in body["artifacts"]}
    assert {"advisor_summary", "advisor_transactions_export"}.issubset(artifact_types)
    assert all(path.exists() and path.is_relative_to(tmp_path / "exports") for path in artifact_paths(body))


def test_advisor_export_artifacts_include_integrity_and_validation_metadata(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accepted_batch = create_accepted_chase_batch(client, tmp_path)
        response = client.post("/api/exports/advisor", json={"actor": "mason"})

    assert response.status_code == 200
    body = response.json()
    expected_job_id = body["job"]["id"]
    artifact_by_type = {artifact["artifact_type"]: artifact for artifact in body["artifacts"]}

    for artifact in body["artifacts"]:
        assert_artifact_registry_integrity(
            artifact,
            expected_root=tmp_path / "exports",
            expected_job_id=expected_job_id,
        )
        assert artifact["source_inputs"]["import_batch_ids"] == [accepted_batch["id"]]
        assert artifact["source_inputs"]["validation_summary"] == body["validation_summary"]

    advisor_summary = json.loads(Path(artifact_by_type["advisor_summary"]["path"]).read_text())
    assert advisor_summary["validation_summary"] == body["validation_summary"]
    assert artifact_by_type["advisor_transactions_export"]["sensitivity"] == "household_financial_export"


def test_advisor_export_blocks_artifact_root_symlink_escape(tmp_path):
    outside_exports_dir = tmp_path.parent / f"{tmp_path.name}_outside_exports"
    outside_exports_dir.mkdir()
    (tmp_path / "exports").symlink_to(outside_exports_dir, target_is_directory=True)
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with pytest.raises(DataRootConfigurationError, match="DATA_ROOT/exports must be a safe directory"):
        with TestClient(app):
            pass
    assert list(outside_exports_dir.iterdir()) == []


def test_artifact_download_returns_registered_artifact_file(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        run_response = client.post("/api/reports/run", json={"actor": "mason"})
        artifact_id = run_response.json()["artifacts"][0]["id"]
        download_response = client.get(f"/api/artifacts/{artifact_id}/download")

    assert download_response.status_code == 200
    assert download_response.content


def test_artifact_download_rejects_registered_file_when_integrity_metadata_no_longer_matches(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        run_response = client.post("/api/reports/run", json={"actor": "mason"})
        artifact = run_response.json()["artifacts"][0]
        Path(artifact["path"]).write_text("tampered synthetic report content")

        download_response = client.get(f"/api/artifacts/{artifact['id']}/download")

    assert download_response.status_code == 409
    assert download_response.json()["detail"]["code"] == "artifact_integrity_mismatch"


def test_artifact_download_rejects_registered_path_replaced_by_symlink(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        run_response = client.post("/api/reports/run", json={"actor": "mason"})
        artifact = run_response.json()["artifacts"][0]
        artifact_path = Path(artifact["path"])
        replacement_target = artifact_path.with_name(f"{artifact_path.stem}_same_content{artifact_path.suffix}")
        replacement_target.write_bytes(artifact_path.read_bytes())
        artifact_path.unlink()
        artifact_path.symlink_to(replacement_target)

        download_response = client.get(f"/api/artifacts/{artifact['id']}/download")

    assert download_response.status_code == 409
    assert download_response.json()["detail"]["code"] == "artifact_file_not_regular"
