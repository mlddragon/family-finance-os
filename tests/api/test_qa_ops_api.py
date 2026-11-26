from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from family_finance_os.main import create_app
from family_finance_os.qa_assets import materialize_vendor_synthetic_fixtures, vendor_synthetic_fixture_dir
from family_finance_os.qa_ops import RESET_CONFIRMATION, SCENARIOS
from family_finance_os.runtime import RuntimeEnvironment


QA_RUNTIME = RuntimeEnvironment(
    app_env="qa",
    app_env_label="QA synthetic demo",
    dataset_kind="synthetic",
    dev_mode=True,
)
PERSONAL_RUNTIME = RuntimeEnvironment(
    app_env="personal",
    app_env_label="Personal data",
    dataset_kind="personal",
    dev_mode=False,
)


def _qa_client(data_root) -> TestClient:
    return TestClient(
        create_app(data_root=data_root, local_bind_host="127.0.0.1", runtime_environment=QA_RUNTIME)
    )


def test_scenario_catalog_lists_operator_friendly_metadata(tmp_path):
    with _qa_client(tmp_path) as client:
        response = client.get("/api/qa/scenarios")

    assert response.status_code == 200
    body = response.json()
    assert body["reset_confirmation_phrase"] == RESET_CONFIRMATION
    assert [scenario["key"] for scenario in body["scenarios"]] == list(SCENARIOS)
    for scenario in body["scenarios"]:
        assert scenario["display_name"]
        assert scenario["description"]
        assert scenario["when_to_use"]
        assert scenario["changes_from_default"]


def test_qa_routes_are_hidden_on_personal_runtime(tmp_path):
    app = create_app(
        data_root=tmp_path,
        local_bind_host="127.0.0.1",
        runtime_environment=PERSONAL_RUNTIME,
    )

    with TestClient(app) as client:
        catalog = client.get("/api/qa/scenarios")
        seed = client.post("/api/qa/seed", json={"actor": "owner", "scenario": "baseline"})
        reset = client.post("/api/qa/reset", json={"actor": "owner", "confirmation": RESET_CONFIRMATION})

    for response in (catalog, seed, reset):
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "qa_controls_disabled"


def test_reset_requires_exact_confirmation_phrase(tmp_path):
    with _qa_client(tmp_path) as client:
        response = client.post("/api/qa/reset", json={"actor": "owner", "confirmation": "reset qa data"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "qa_reset_confirmation_invalid"


def test_reset_clears_data_and_restores_vendor_fixtures(tmp_path):
    leftover = tmp_path / "reports" / "SYNTHETIC_leftover.json"

    with _qa_client(tmp_path) as client:
        leftover.parent.mkdir(parents=True, exist_ok=True)
        leftover.write_text("{}", encoding="utf-8")
        response = client.post(
            "/api/qa/reset",
            json={"actor": "owner", "confirmation": RESET_CONFIRMATION},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "reset"
    assert not leftover.exists()
    assert (vendor_synthetic_fixture_dir(tmp_path) / "vendor_collect_amazon.json").is_file()


def test_reset_refuses_report_viewer_actor(tmp_path):
    with _qa_client(tmp_path) as client:
        response = client.post(
            "/api/qa/reset",
            json={
                "actor": "viewer",
                "confirmation": RESET_CONFIRMATION,
                "actor_context": {
                    "actor_key": "viewer",
                    "actor_type": "human",
                    "display_name": "Report Viewer",
                    "persona_key": "report_viewer",
                    "group_keys": ["report_viewer"],
                    "source": "local_selector",
                },
            },
        )

    assert response.status_code == 403


@pytest.mark.parametrize("scenario", ["baseline", "review-backlog"])
def test_seed_scenario_through_api_populates_runtime_state(tmp_path, scenario: str):
    with _qa_client(tmp_path) as client:
        seed = client.post("/api/qa/seed", json={"actor": "owner", "scenario": scenario})
        transactions = client.get("/api/transactions")
        catalog = client.get("/api/qa/scenarios")

    assert seed.status_code == 200
    assert seed.json()["scenario"] == scenario
    assert seed.json()["latest_manifest"]["scenario"] == scenario
    assert transactions.status_code == 200
    assert transactions.json()["transactions"]
    assert catalog.json()["latest_manifest"]["scenario"] == scenario


def test_seed_rejects_unknown_scenario(tmp_path):
    with _qa_client(tmp_path) as client:
        response = client.post("/api/qa/seed", json={"actor": "owner", "scenario": "not-a-scenario"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "qa_scenario_unknown"


def test_seeded_vendor_fixtures_enable_synthetic_scrape_from_data_root(tmp_path):
    materialize_vendor_synthetic_fixtures(tmp_path)

    with _qa_client(tmp_path) as client:
        client.patch(
            "/api/settings",
            json={
                "actor": "owner",
                "changes": [
                    {
                        "domain": "future_integrations",
                        "setting_key": "vendor_scraper.amazon.enabled",
                        "value": True,
                        "note": "Enable synthetic amazon scraper for QA route test.",
                    }
                ],
            },
        )
        run = client.post(
            "/api/vendor-scrapes",
            json={"actor": "owner", "vendor_key": "amazon", "mode": "synthetic"},
        )

    assert run.status_code == 200
    assert run.json()["job"]["status"] == "completed"
