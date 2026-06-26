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


def finance_manager_context() -> dict:
    return {
        "actor_key": "owner",
        "actor_type": "human",
        "display_name": "Finance Manager",
        "persona_key": "finance_manager",
        "persona_label": "Finance Manager",
        "group_keys": ["finance_manager"],
        "source": "local_selector",
    }


def finance_contributor_context() -> dict:
    return {
        "actor_key": "contributor",
        "actor_type": "human",
        "display_name": "Contributor",
        "persona_key": "finance_contributor",
        "persona_label": "Finance Contributor",
        "group_keys": ["finance_contributor"],
        "source": "local_selector",
    }


def create_transaction(client: TestClient, data_root: Path, *, amount: str = "12.34") -> dict:
    content = CHASE_HEADER + fresh_row(amount=amount)
    write_inbox_file(data_root, "SYNTHETIC_suggestions_source.csv", content)
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
    assert client.post(
        f"/api/import-batches/{batch_id}/accept",
        json={"actor": "owner", "actor_context": finance_manager_context()},
    ).status_code == 200
    return client.get("/api/transactions").json()["transactions"][0]


def decision_payload(transaction_id: str, **overrides) -> dict:
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
    return payload


def enable_approval_mode(client: TestClient) -> None:
    response = client.patch(
        "/api/settings",
        json={
            "actor": "owner",
            "actor_context": finance_manager_context(),
            "changes": [
                {
                    "domain": "approval",
                    "setting_key": "approval.approval_mode_enabled",
                    "value": True,
                    "note": "Enable approval mode for QA.",
                }
            ],
        },
    )
    assert response.status_code == 200


def test_default_approval_settings_are_off(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        settings = client.get("/api/settings").json()["settings"]
        approval_mode = next(
            item for item in settings if item["setting_key"] == "approval.approval_mode_enabled"
        )
        threshold = next(
            item for item in settings if item["setting_key"] == "approval.high_value_threshold"
        )

    assert approval_mode["value"] is False
    assert threshold["value"] == 500


def test_contributor_review_decide_routes_to_suggestion_when_approval_mode_off(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        response = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="contributor",
                actor_context=finance_contributor_context(),
            ),
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]
        suggestions = client.get(
            "/api/suggestions",
            params={"target_id": transaction["id"]},
            headers={"X-Actor-Context": __import__("json").dumps(finance_contributor_context())},
        ).json()["suggestions"]

    assert response.status_code == 200
    assert response.json()["route"] == "suggestion"
    assert response.json()["suggestion"]["status"] == "active"
    assert response.json()["suggestion"]["proposed_value"] == "business"
    assert detail["category_current"] == "Groceries"
    assert detail["decision_history_count"] == 0
    assert len(suggestions) == 1


def test_manager_can_accept_suggestion_directly(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        suggestion_id = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="contributor",
                actor_context=finance_contributor_context(),
            ),
        ).json()["suggestion"]["id"]
        accepted = client.post(
            f"/api/suggestions/{suggestion_id}/accept",
            json={
                "actor": "mason",
                "actor_context": finance_manager_context(),
                "explicit_user_action": True,
            },
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert accepted.status_code == 200
    assert accepted.json()["suggestion"]["status"] == "accepted_direct"
    assert detail["category_current"] == "Business"
    assert detail["decision_history_count"] == 1


def test_approval_management_hidden_when_mode_off(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.get("/api/approval-requests")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "approval_mode_disabled"


def test_contributor_routes_to_approval_request_when_mode_on(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_approval_mode(client)
        transaction = create_transaction(client, tmp_path)
        response = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="contributor",
                actor_context=finance_contributor_context(),
            ),
        )
        queue = client.get("/api/approval-requests").json()["approval_requests"]

    assert response.status_code == 200
    assert response.json()["route"] == "approval_request"
    assert queue[0]["status"] == "pending"
    assert queue[0]["proposer_actor"] == "contributor"
    assert queue[0]["policy_trigger"] == "lacking_authority"


def test_proposer_cannot_approve_own_request(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_approval_mode(client)
        transaction = create_transaction(client, tmp_path, amount="600.00")
        approval_request_id = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="mason",
                actor_context=finance_manager_context(),
            ),
        ).json()["approval_request"]["id"]
        blocked = client.post(
            f"/api/approval-requests/{approval_request_id}/approve",
            json={
                "actor": "mason",
                "actor_context": finance_manager_context(),
            },
        )

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "proposer_cannot_approve"


def test_manager_can_approve_contributor_request(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_approval_mode(client)
        transaction = create_transaction(client, tmp_path)
        approval_request_id = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="contributor",
                actor_context=finance_contributor_context(),
            ),
        ).json()["approval_request"]["id"]
        approved = client.post(
            f"/api/approval-requests/{approval_request_id}/approve",
            json={
                "actor": "mason",
                "actor_context": finance_manager_context(),
            },
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert approved.status_code == 200
    assert approved.json()["approval_request"]["status"] == "approved"
    assert detail["category_current"] == "Business"


def test_only_one_pending_request_per_target_action_field(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_approval_mode(client)
        transaction = create_transaction(client, tmp_path)
        first = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="contributor",
                actor_context=finance_contributor_context(),
            ),
        )
        second = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="contributor",
                actor_context=finance_contributor_context(),
                proposed_value="travel",
                approved_value="travel",
            ),
        )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "pending_approval_request_exists"


def test_high_value_transaction_routes_manager_to_approval_request(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_approval_mode(client)
        transaction = create_transaction(client, tmp_path, amount="600.00")
        response = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="mason",
                actor_context=finance_manager_context(),
            ),
        )
        detail = client.get(f"/api/transactions/{transaction['id']}").json()["transaction"]

    assert response.status_code == 200
    assert response.json()["route"] == "approval_request"
    assert response.json()["approval_request"]["policy_trigger"] == "high_value"
    assert detail["decision_history_count"] == 0


def test_create_suggestion_via_post_api(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        response = client.post(
            "/api/suggestions",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "action_key": "review.decide",
                "field_name": "category",
                "decision_type": "category_change",
                "proposed_value": "business",
                "actor": "contributor",
                "actor_context": finance_contributor_context(),
                "suggestion_source": "user",
            },
        )

    assert response.status_code == 200
    assert response.json()["suggestion"]["status"] == "active"


def test_dismiss_suggestion(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        transaction = create_transaction(client, tmp_path)
        suggestion_id = client.post(
            "/api/suggestions",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "action_key": "review.decide",
                "field_name": "category",
                "decision_type": "category_change",
                "proposed_value": "business",
                "actor": "contributor",
                "actor_context": finance_contributor_context(),
                "suggestion_source": "user",
            },
        ).json()["suggestion"]["id"]
        dismissed = client.post(
            f"/api/suggestions/{suggestion_id}/dismiss",
            json={
                "actor": "contributor",
                "actor_context": finance_contributor_context(),
            },
        )

    assert dismissed.status_code == 200
    assert dismissed.json()["suggestion"]["status"] == "dismissed"


def test_cancel_approval_request_by_proposer(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enable_approval_mode(client)
        transaction = create_transaction(client, tmp_path)
        approval_request_id = client.post(
            "/api/decision-events",
            json=decision_payload(
                transaction["id"],
                actor="contributor",
                actor_context=finance_contributor_context(),
            ),
        ).json()["approval_request"]["id"]
        cancelled = client.post(
            f"/api/approval-requests/{approval_request_id}/cancel",
            json={
                "actor": "contributor",
                "actor_context": finance_contributor_context(),
            },
        )

    assert cancelled.status_code == 200
    assert cancelled.json()["approval_request"]["status"] == "cancelled"
