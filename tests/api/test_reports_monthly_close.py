from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from dillon_finances.main import create_app


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


def artifact_paths(body: dict) -> list[Path]:
    return [Path(artifact["path"]) for artifact in body["artifacts"]]


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
    assert body["report_run"]["validation_status"] == "passed_with_warnings"
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
    assert body["validation_summary"]["missing_required_count"] == 3
    artifact_types = {artifact["artifact_type"] for artifact in body["artifacts"]}
    assert {"monthly_close_manifest", "monthly_close_memo", "settings_snapshot", "decision_event_export"}.issubset(
        artifact_types
    )
    manifest = next(path for path in artifact_paths(body) if path.name == "manifest.json")
    assert manifest.exists()
    assert manifest.is_relative_to(tmp_path / "monthly_close")
    assert '"status":"draft"' in manifest.read_text()


def test_final_close_blocks_missing_required_source_coverage(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        response = client.post("/api/monthly-close/finalize", json={"actor": "mason"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "final_close_blocked"
    assert "missing_required_sources" in detail["validation_summary"]
    assert detail["validation_summary"]["missing_required_count"] == 3


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
        create_accepted_chase_batch(client, tmp_path)
        disable_unavailable_required_sources(client)
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
    assert body["validation_summary"]["missing_required_count"] == 3
    artifact_types = {artifact["artifact_type"] for artifact in body["artifacts"]}
    assert {"advisor_summary", "advisor_transactions_export"}.issubset(artifact_types)
    assert all(path.exists() and path.is_relative_to(tmp_path / "exports") for path in artifact_paths(body))


def test_artifact_download_returns_registered_artifact_file(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        run_response = client.post("/api/reports/run", json={"actor": "mason"})
        artifact_id = run_response.json()["artifacts"][0]["id"]
        download_response = client.get(f"/api/artifacts/{artifact_id}/download")

    assert download_response.status_code == 200
    assert download_response.content
