from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from family_finance_os.main import create_app


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


def create_transaction(client: TestClient, data_root: Path) -> dict:
    write_inbox_file(data_root, "SYNTHETIC_actor_context_source.csv", CHASE_HEADER + fresh_row())
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
    assert client.post(f"/api/import-batches/{batch_id}/accept").status_code == 200
    return client.get("/api/transactions").json()["transactions"][0]


def owner_context(display_name: str = "Owner") -> dict:
    return {
        "actor_key": "owner",
        "actor_type": "human",
        "display_name": display_name,
        "persona_key": "finance_manager",
        "persona_label": "Finance Manager",
        "group_keys": ["finance_manager", "administrator"],
        "source": "local_selector",
    }


def test_actors_endpoint_returns_local_actor_foundation(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.get("/api/actors")

    assert response.status_code == 200
    body = response.json()
    assert body["default_actor_key"] == "owner"
    assert {actor["actor_key"] for actor in body["human_actors"]} == {"owner"}
    assert {actor["actor_key"] for actor in body["system_actors"]} == {"system"}
    assert "Finance Manager" in {group["display_name"] for group in body["groups"]}
    assert "system:importer" in {persona["system_persona_key"] for persona in body["system_personas"]}


def test_decision_events_persist_structured_actor_context(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        response = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "category_change",
                "field_name": "category",
                "proposed_value": "business",
                "approved_value": "business",
                "actor": "owner",
                "actor_context": owner_context(display_name="Preferred Owner Name"),
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert response.status_code == 200
    event = response.json()["event"]
    assert event["actor"] == "owner"
    assert event["actor_context"]["display_name"] == "Preferred Owner Name"
    assert event["actor_context"]["persona_key"] == "finance_manager"
    assert detail["decision_history"][0]["actor_context"]["display_name"] == "Preferred Owner Name"


def test_settings_events_derive_compatibility_actor_context(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.patch(
            "/api/settings",
            json={
                "actor": "legacy-user",
                "changes": [
                    {
                        "domain": "branding",
                        "setting_key": "branding.app_display_name",
                        "value": "Family Finance OS QA",
                    }
                ],
            },
        )

    assert response.status_code == 200
    event = response.json()["events"][0]
    assert event["actor"] == "legacy-user"
    assert event["actor_context"]["actor_key"] == "legacy-user"
    assert event["actor_context"]["display_name"] == "legacy-user"
    assert event["actor_context"]["source"] == "compat_actor_string"
