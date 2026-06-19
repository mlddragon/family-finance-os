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


def create_transaction(client: TestClient, data_root: Path, *, ambiguous: bool = False) -> dict:
    row = fresh_row("SYNTHETIC SAME STORE" if ambiguous else "SYNTHETIC GROCERY")
    content = CHASE_HEADER + row + (row if ambiguous else "")
    write_inbox_file(data_root, "SYNTHETIC_decision_source.csv", content)
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    validation_response = client.post(f"/api/import-batches/{batch_id}/validate")
    assert validation_response.status_code == 200
    accept_response = client.post(f"/api/import-batches/{batch_id}/accept")
    assert accept_response.status_code == 200
    return client.get("/api/transactions").json()["transactions"][0]


def save_decision(client: TestClient, transaction_id: str, **overrides) -> dict:
    payload = {
        "target_type": "canonical_transaction",
        "target_id": transaction_id,
        "decision_type": "category_change",
        "field_name": "category",
        "proposed_value": "Groceries",
        "approved_value": "Groceries",
        "actor": "mason",
        "suggestion_source": "owner",
        "explicit_user_action": True,
    }
    payload.update(overrides)
    response = client.post("/api/decision-events", json=payload)
    assert response.status_code == 200
    return response.json()


def test_category_decision_is_append_only_and_updates_current_state(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        response_body = save_decision(client, transaction["id"])
        detail_response = client.get(f"/api/transactions/{transaction['id']}")

    assert response_body["event"]["decision_type"] == "category_change"
    assert response_body["event"]["previous_value"] == "Food"
    detail = detail_response.json()["transaction"]
    assert detail["category_original"] == "Food"
    assert detail["category_current"] == "Groceries"
    assert detail["review_status"] == "unreviewed"
    assert detail["decision_history_count"] == 1
    assert detail["decision_history"][0]["approved_value"] == "Groceries"
    assert detail["imported_facts"][0]["initial_category"] == "Food"


def test_explicit_user_action_is_required_before_suggestion_becomes_decision(tmp_path):
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
                "proposed_value": "Groceries",
                "approved_value": "Groceries",
                "actor": "mason",
                "suggestion_source": "codex",
                "explicit_user_action": False,
            },
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "explicit_user_action_required"
    assert detail["category_current"] == "Food"
    assert detail["decision_history_count"] == 0


def test_high_impact_decision_requires_note(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        missing_note = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "medical_tax_candidate_status",
                "field_name": "medical_tax_status",
                "proposed_value": "candidate",
                "approved_value": "candidate",
                "actor": "mason",
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )
        saved = save_decision(
            client,
            transaction["id"],
            decision_type="medical_tax_candidate_status",
            field_name="medical_tax_status",
            proposed_value="candidate",
            approved_value="candidate",
            notes="Receipt may be HSA/tax relevant.",
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert missing_note.status_code == 422
    assert missing_note.json()["detail"]["code"] == "required_note_missing"
    assert saved["event"]["field_name"] == "medical_tax_status"
    assert detail["medical_tax_status"] == "candidate"


def test_review_reason_decision_allows_empty_previous_value(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        saved = save_decision(
            client,
            transaction["id"],
            decision_type="review_reason_change",
            field_name="review_reason",
            proposed_value="category confirmed",
            approved_value="category confirmed",
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert saved["event"]["previous_value"] is None
    assert detail["review_reason"] == "category confirmed"


def test_decisions_are_blocked_for_ambiguous_canonical_targets(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path, ambiguous=True)
        response = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "category_change",
                "field_name": "category",
                "approved_value": "Groceries",
                "actor": "mason",
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "target_blocked_by_validation"


def test_supersede_and_revert_events_update_current_state_without_editing_history(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        first = save_decision(client, transaction["id"])
        second = save_decision(
            client,
            transaction["id"],
            proposed_value="Medical",
            approved_value="Medical",
            notes="Correcting category after receipt review.",
            supersedes_event_id=first["event"]["id"],
        )
        reverted = save_decision(
            client,
            transaction["id"],
            proposed_value="Food",
            approved_value="Food",
            notes="Reverting correction after final review.",
            reverts_event_id=second["event"]["id"],
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert reverted["event"]["reverts_event_id"] == second["event"]["id"]
    assert detail["category_current"] == "Food"
    assert detail["decision_history_count"] == 3
    event_status_by_id = {event["id"]: event["active"] for event in detail["decision_history"]}
    assert event_status_by_id[first["event"]["id"]] is False
    assert event_status_by_id[second["event"]["id"]] is False
    assert event_status_by_id[reverted["event"]["id"]] is True


def test_imported_rows_are_not_valid_decision_targets(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]
        imported_fact_id = detail["imported_facts"][0]["id"]
        response = client.post(
            "/api/decision-events",
            json={
                "target_type": "imported_row",
                "target_id": imported_fact_id,
                "decision_type": "category_change",
                "field_name": "category",
                "approved_value": "Groceries",
                "actor": "mason",
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "target_type_not_allowed"
