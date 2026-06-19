from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from dillon_finances.main import create_app


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "synthetic"

VALID_SOURCE_FIXTURES = {
    "v1_valid_alliant_checking.csv": "alliant_checking",
    "v1_valid_alliant_savings.csv": "alliant_savings",
    "v1_valid_alliant_credit_card.csv": "alliant_credit_card",
    "v1_valid_chase_prime_visa.csv": "chase_prime_visa",
}

SCENARIO_FIXTURES = {
    "v1_missing_required_source_note.txt",
    "v1_stale_chase_prime_visa.csv",
    "v1_wrong_header.csv",
    "v1_malformed_date.csv",
    "v1_malformed_amount.csv",
    "v1_unexpected_amount_sign.csv",
    "v1_duplicate_imported_row.csv",
    "v1_ambiguous_canonical_transaction.csv",
    "v1_warning_acknowledgment.csv",
    "v1_high_impact_decision_requires_note.json",
}


def render_fixture(name: str) -> str:
    fresh_date = date.today() - timedelta(days=1)
    fresh_post_date = date.today()
    stale_date = date.today() - timedelta(days=60)
    text = (FIXTURE_DIR / name).read_text()
    return (
        text.replace("{{FRESH_DATE}}", fresh_date.isoformat())
        .replace("{{FRESH_POST_DATE}}", fresh_post_date.isoformat())
        .replace("{{STALE_DATE}}", stale_date.isoformat())
        .replace("{{STALE_POST_DATE}}", (stale_date + timedelta(days=1)).isoformat())
    )


def write_fixture_to_inbox(data_root: Path, fixture_name: str, *, filename: str | None = None) -> Path:
    inbox_path = data_root / "inbox" / (filename or fixture_name)
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(render_fixture(fixture_name))
    return inbox_path


def scan_validate_accept_all(client: TestClient, *, acknowledge_warnings: bool = False) -> list[dict]:
    scan_response = client.post("/api/inbox/scan")
    assert scan_response.status_code == 200
    accepted_batches = []
    for batch in scan_response.json()["import_batches"]:
        validate_response = client.post(f"/api/import-batches/{batch['id']}/validate")
        assert validate_response.status_code == 200
        if not acknowledge_warnings:
            assert [finding for finding in validate_response.json()["findings"] if finding["severity"] == "blocking"] == []
        accept_response = client.post(
            f"/api/import-batches/{batch['id']}/accept",
            json={"acknowledge_warnings": acknowledge_warnings},
        )
        assert accept_response.status_code == 200
        accepted_batches.append(accept_response.json())
    return accepted_batches


def save_decision(client: TestClient, transaction_id: str, *, field_name: str, decision_type: str, value: object, notes: str | None = None) -> dict:
    response = client.post(
        "/api/decision-events",
        json={
            "target_type": "canonical_transaction",
            "target_id": transaction_id,
            "decision_type": decision_type,
            "field_name": field_name,
            "proposed_value": value,
            "approved_value": value,
            "actor": "mason",
            "notes": notes,
            "suggestion_source": "owner",
            "explicit_user_action": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_required_pr10_synthetic_fixtures_exist_and_are_obviously_fake():
    expected_fixtures = set(VALID_SOURCE_FIXTURES) | SCENARIO_FIXTURES
    assert expected_fixtures
    for fixture_name in expected_fixtures:
        path = FIXTURE_DIR / fixture_name
        assert path.exists(), f"Missing synthetic fixture: {fixture_name}"
        assert "SYNTHETIC" in path.read_text()[:2048]


def test_full_synthetic_closed_loop_reaches_final_close_advisor_export_and_refresh_status(tmp_path):
    for fixture_name in VALID_SOURCE_FIXTURES:
        write_fixture_to_inbox(tmp_path, fixture_name)
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accepted_batches = scan_validate_accept_all(client)
        source_keys = sorted(batch["source_key"] for batch in accepted_batches)
        transactions_response = client.get("/api/transactions")
        assert transactions_response.status_code == 200
        transactions = transactions_response.json()["transactions"]

        save_decision(
            client,
            transactions[0]["id"],
            field_name="category",
            decision_type="category_change",
            value="Groceries",
        )
        for transaction in transactions:
            save_decision(
                client,
                transaction["id"],
                field_name="review_status",
                decision_type="review_status_change",
                value="reviewed",
            )

        reports_response = client.post("/api/reports/run", json={"actor": "mason"})
        draft_close_response = client.post("/api/monthly-close/draft", json={"actor": "mason"})
        final_close_response = client.post(
            "/api/monthly-close/finalize",
            json={"actor": "mason", "notes": "SYNTHETIC full closed-loop final close."},
        )
        advisor_response = client.post("/api/exports/advisor", json={"actor": "mason"})
        summary_response = client.get("/api/operator-summary")

    assert source_keys == sorted(VALID_SOURCE_FIXTURES.values())
    assert len(transactions) >= 4
    assert reports_response.status_code == 200
    assert draft_close_response.status_code == 200
    assert final_close_response.status_code == 200
    assert final_close_response.json()["monthly_close"]["status"] == "final"
    assert final_close_response.json()["monthly_close"]["provisional"] is False
    assert advisor_response.status_code == 200
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["sources"]["missing_required_count"] == 0
    assert summary["review"]["unreviewed"] == 0
    assert summary["monthly_close"]["status"] == "final"
    assert summary["next_action"]["code"] == "refresh_source_data"
    assert all(Path(artifact["path"]).is_relative_to(tmp_path) for artifact in advisor_response.json()["artifacts"])


def test_blocked_path_covers_schema_quarantine_stale_and_missing_required_sources(tmp_path):
    write_fixture_to_inbox(tmp_path, "v1_wrong_header.csv")
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        blocked_batch_id = client.post("/api/inbox/scan").json()["import_batches"][0]["id"]
        validate_blocked = client.post(f"/api/import-batches/{blocked_batch_id}/validate")
        accept_blocked = client.post(f"/api/import-batches/{blocked_batch_id}/accept")

        write_fixture_to_inbox(tmp_path, "v1_stale_chase_prime_visa.csv")
        stale_batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
        validate_stale = client.post(f"/api/import-batches/{stale_batch_id}/validate")
        accept_stale = client.post(
            f"/api/import-batches/{stale_batch_id}/accept",
            json={"acknowledge_warnings": True},
        )
        final_close_response = client.post("/api/monthly-close/finalize", json={"actor": "mason"})

    assert validate_blocked.json()["findings"][0]["code"] == "schema_mismatch"
    assert accept_blocked.status_code == 409
    assert list((tmp_path / "quarantine").glob("**/v1_wrong_header.csv"))
    assert any(finding["code"] == "source_stale" for finding in validate_stale.json()["findings"])
    assert accept_stale.status_code == 200
    assert final_close_response.status_code == 409
    validation_summary = final_close_response.json()["detail"]["validation_summary"]
    assert validation_summary["missing_required_sources"]
    assert validation_summary["stale_required_sources"] == ["chase_prime_visa"]


def test_owner_smoke_checklist_and_runbook_are_present_and_sanitized():
    checklist = REPO_ROOT / "docs" / "owner_smoke_checklist_v1.md"
    assert checklist.exists()
    checklist_text = checklist.read_text()
    assert "sanitized" in checklist_text.lower()
    assert "Do not record raw transaction" in checklist_text

    readme = (REPO_ROOT / "README.md").read_text()
    for expected in ["docker compose up", "127.0.0.1:8080", "DATA_ROOT", "backup", "troubleshooting"]:
        assert expected in readme


def test_pr10_security_contract_and_docker_e2e_scripts_exist_and_pass_static_checks():
    security_script = REPO_ROOT / "scripts" / "check_v1_security_contract.py"
    docker_e2e_script = REPO_ROOT / "scripts" / "run_docker_e2e.py"
    assert security_script.exists()
    assert docker_e2e_script.exists()
    docker_e2e_text = docker_e2e_script.read_text()
    assert "tests/fixtures/synthetic" in docker_e2e_text
    assert "OpenAI" not in docker_e2e_text

    result = subprocess.run(
        [sys.executable, str(security_script), str(REPO_ROOT)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
