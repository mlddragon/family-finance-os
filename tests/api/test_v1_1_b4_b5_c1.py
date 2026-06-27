from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from family_finance_os.main import create_app
from tests.api.test_elevated_mode import SESSION_HEADER, finance_manager_context
from tests.api.test_reports_monthly_close import (
    confirm_source_profile_sample,
    create_accepted_chase_batch,
    disable_unavailable_required_sources,
    enable_required_sources,
)


def test_analyst_pack_build_writes_manifest_and_summary(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        response = client.post(
            "/api/analyst-pack/build",
            json={
                "actor": "owner",
                "prompt_key": "monthly_spending_review",
                "include_raw_transactions": False,
                "include_estimates": False,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["job_type"] == "analyst_pack_export"
    manifest = body["manifest"]
    assert manifest["privacy_boundary"] == "local_file_only_no_in_app_ai"
    assert manifest["includes_raw_transactions"] is False
    artifact_types = {artifact["artifact_type"] for artifact in body["artifacts"]}
    assert "analyst_pack_manifest" in artifact_types
    assert "analyst_pack_summary" in artifact_types
    assert all(Path(artifact["path"]).is_relative_to(tmp_path / "exports" / "analyst_pack") for artifact in body["artifacts"])


def test_analyst_pack_rejects_unknown_prompt(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.post(
            "/api/analyst-pack/build",
            json={"actor": "owner", "prompt_key": "unknown_prompt"},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "analyst_pack_prompt_not_found"


def test_dashboard_endpoints_return_chart_ready_payloads(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        summary = client.get("/api/dashboard/summary")
        cashflow = client.get("/api/dashboard/cashflow?months=3")
        categories = client.get("/api/dashboard/category-spend")
        pools = client.get("/api/dashboard/pool-progress")
        net_worth = client.get("/api/dashboard/net-worth")

    assert summary.status_code == 200
    assert "freshness" in summary.json()
    assert cashflow.status_code == 200
    assert len(cashflow.json()["points"]) == 3
    assert categories.status_code == 200
    assert "categories" in categories.json()
    assert pools.status_code == 200
    assert "pools" in pools.json()
    assert net_worth.status_code == 200
    assert net_worth.json()["view_label"] == "actual_only"


def test_monthly_close_draft_includes_funds_and_spendable_section(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_chase_batch(client, tmp_path)
        response = client.post("/api/monthly-close/draft", json={"actor": "mason"})

    assert response.status_code == 200
    funds = response.json()["validation_summary"]["funds_and_spendable"]
    assert "blockers" in funds
    assert "pool_summaries" in funds
    artifact_types = {artifact["artifact_type"] for artifact in response.json()["artifacts"]}
    assert {"fund_pool_summary", "spendable_snapshot"}.issubset(artifact_types)


def test_final_close_blocks_funds_blockers_without_governor_override(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        disable_unavailable_required_sources(client)
        enable_required_sources(client, "chase_prime_visa")
        create_accepted_chase_batch(client, tmp_path)
        confirm_source_profile_sample(client, "chase_prime_visa")
        pool = client.post(
            "/api/fund-pools",
            json={"name": "Synthetic Missing Commitment Pool", "actor": "owner"},
        ).json()["pool"]
        month = client.get("/api/funds/summary").json()["month"]
        client.post(
            "/api/budget-targets",
            json={
                "target_scope": "fund_pool",
                "fund_pool_id": pool["id"],
                "month": month,
                "target_amount": "100.00",
                "actor": "owner",
            },
        )
        response = client.post(
            "/api/monthly-close/finalize",
            json={"actor": "owner", "actor_context": finance_manager_context()},
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "monthly_close_governor_required"


def enter_governor_close_mode(client: TestClient, session_id: str = "governor-close-session") -> dict:
    response = client.post(
        "/api/elevated-mode/enter",
        headers={SESSION_HEADER: session_id},
        json={
            "context": "financial_governance",
            "purpose_code": "monthly_close_governance_review",
            "note": "SYNTHETIC governor review for monthly close override.",
            "actor": "owner",
            "actor_context": finance_manager_context(),
        },
    )
    assert response.status_code == 200
    return response.json()


def test_final_close_succeeds_with_governor_override_and_purpose_note(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "governor-close-session"

    with TestClient(app) as client:
        disable_unavailable_required_sources(client)
        enable_required_sources(client, "chase_prime_visa")
        create_accepted_chase_batch(client, tmp_path)
        confirm_source_profile_sample(client, "chase_prime_visa")
        pool = client.post(
            "/api/fund-pools",
            json={"name": "Synthetic Override Pool", "actor": "owner"},
        ).json()["pool"]
        month = client.get("/api/funds/summary").json()["month"]
        client.post(
            "/api/budget-targets",
            json={
                "target_scope": "fund_pool",
                "fund_pool_id": pool["id"],
                "month": month,
                "target_amount": "100.00",
                "actor": "owner",
            },
        )
        enter_governor_close_mode(client, session_id=session_id)
        response = client.post(
            "/api/monthly-close/finalize",
            headers={SESSION_HEADER: session_id},
            json={
                "actor": "owner",
                "actor_context": finance_manager_context(),
                "override_purpose": "Synthetic governor override for missing fund commitment.",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["governor_override_applied"] is True
    assert body["monthly_close"]["provisional"] is True
    manifest_path = next(path for path in (Path(a["path"]) for a in body["artifacts"]) if path.name == "manifest.json")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["governor_override_applied"] is True
