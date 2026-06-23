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


def fresh_row_without_category(description: str = "SYNTHETIC UNCATEGORIZED", amount: str = "12.34") -> str:
    transaction_date = date.today() - timedelta(days=1)
    post_date = date.today()
    return f"{transaction_date.isoformat()},{post_date.isoformat()},{description},,{amount}\n"


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
        "proposed_value": "business",
        "approved_value": "business",
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
    assert response_body["event"]["previous_value"] == "groceries"
    detail = detail_response.json()["transaction"]
    assert detail["category_original"] == "Groceries"
    assert detail["category_key_original"] == "groceries"
    assert detail["category_current"] == "Business"
    assert detail["category_key_current"] == "business"
    assert detail["category_display_name_current"] == "Business"
    assert detail["review_status"] == "unreviewed"
    assert detail["decision_history_count"] == 1
    assert detail["decision_history"][0]["approved_value"] == "business"
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
                "proposed_value": "business",
                "approved_value": "business",
                "actor": "mason",
                "suggestion_source": "codex",
                "explicit_user_action": False,
            },
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "explicit_user_action_required"
    assert detail["category_current"] == "Groceries"
    assert detail["category_key_current"] == "groceries"
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


def test_remaining_status_and_boolean_decision_fields_update_current_state(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        transfer = save_decision(
            client,
            transaction["id"],
            decision_type="transfer_flag_status",
            field_name="transfer_status",
            proposed_value="candidate",
            approved_value="candidate",
        )
        reimbursement = save_decision(
            client,
            transaction["id"],
            decision_type="reimbursement_candidate_status",
            field_name="reimbursement_status",
            proposed_value="candidate",
            approved_value="candidate",
            notes="Synthetic receipt may be reimbursable.",
        )
        project = save_decision(
            client,
            transaction["id"],
            decision_type="project_candidate_flag",
            field_name="project_candidate",
            proposed_value=True,
            approved_value=True,
            notes="Synthetic project tracking candidate.",
        )
        side_hustle = save_decision(
            client,
            transaction["id"],
            decision_type="side_hustle_candidate_flag",
            field_name="side_hustle_candidate",
            proposed_value=True,
            approved_value=True,
            notes="Synthetic side-hustle tracking candidate.",
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert transfer["event"]["field_name"] == "transfer_status"
    assert reimbursement["event"]["field_name"] == "reimbursement_status"
    assert project["event"]["approved_value"] is True
    assert side_hustle["event"]["approved_value"] is True
    assert detail["transfer_status"] == "candidate"
    assert detail["reimbursement_status"] == "candidate"
    assert detail["project_candidate"] is True
    assert detail["side_hustle_candidate"] is True


def test_subcategory_requires_category_before_save(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        write_inbox_file(
            tmp_path,
            "SYNTHETIC_uncategorized_decision_source.csv",
            CHASE_HEADER + fresh_row_without_category(),
        )
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
        assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
        assert client.post(f"/api/import-batches/{batch_id}/accept").status_code == 200
        transaction = client.get("/api/transactions").json()["transactions"][0]

        response = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "subcategory_change",
                "field_name": "subcategory",
                "proposed_value": "Dining",
                "approved_value": "Dining",
                "actor": "mason",
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "category_required_for_subcategory"


def test_decision_field_mismatch_and_invalid_controlled_values_are_rejected(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        mismatch = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "category_change",
                "field_name": "review_status",
                "proposed_value": "reviewed",
                "approved_value": "reviewed",
                "actor": "mason",
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )
        invalid_status = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "review_status_change",
                "field_name": "review_status",
                "proposed_value": "done",
                "approved_value": "done",
                "actor": "mason",
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )
        invalid_boolean = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "project_candidate_flag",
                "field_name": "project_candidate",
                "proposed_value": "maybe",
                "approved_value": "maybe",
                "actor": "mason",
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )

    assert mismatch.status_code == 422
    assert mismatch.json()["detail"]["code"] == "field_decision_type_mismatch"
    assert invalid_status.status_code == 422
    assert invalid_status.json()["detail"]["code"] == "invalid_controlled_value"
    assert invalid_boolean.status_code == 422
    assert invalid_boolean.json()["detail"]["code"] == "invalid_controlled_value"


def test_codex_and_future_ai_suggestions_require_owner_note_even_after_explicit_save(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        missing_note = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "category_change",
                "field_name": "category",
                "proposed_value": "business",
                "approved_value": "business",
                "actor": "mason",
                "suggestion_source": "codex",
                "explicit_user_action": True,
            },
        )
        saved = save_decision(
            client,
            transaction["id"],
            proposed_value="business",
            approved_value="business",
            suggestion_source="future_ai_proposal",
            notes="Owner reviewed synthetic future-AI proposal before saving.",
        )
        invalid_source = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "review_status_change",
                "field_name": "review_status",
                "proposed_value": "reviewed",
                "approved_value": "reviewed",
                "actor": "mason",
                "suggestion_source": "unapproved_model",
                "explicit_user_action": True,
            },
        )

    assert missing_note.status_code == 422
    assert missing_note.json()["detail"]["code"] == "required_note_missing"
    assert saved["event"]["suggestion_source"] == "future_ai_proposal"
    assert invalid_source.status_code == 422
    assert invalid_source.json()["detail"]["code"] == "suggestion_source_not_allowed"


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
            proposed_value="health",
            approved_value="health",
            notes="Correcting category after receipt review.",
            supersedes_event_id=first["event"]["id"],
        )
        reverted = save_decision(
            client,
            transaction["id"],
            proposed_value="groceries",
            approved_value="groceries",
            notes="Reverting correction after final review.",
            reverts_event_id=second["event"]["id"],
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert reverted["event"]["reverts_event_id"] == second["event"]["id"]
    assert detail["category_current"] == "Groceries"
    assert detail["category_key_current"] == "groceries"
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
