from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from family_finance_os.main import create_app
from family_finance_os.permissions import ActionKey, DataScopeKey
from family_finance_os.runtime import RuntimeEnvironment


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


def administrator_context() -> dict:
    return {
        "actor_key": "owner",
        "actor_type": "human",
        "display_name": "Administrator",
        "persona_key": "administrator",
        "persona_label": "Administrator",
        "group_keys": ["administrator"],
        "source": "local_selector",
    }


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


def qa_runtime() -> RuntimeEnvironment:
    return RuntimeEnvironment(
        app_env="qa",
        app_env_label="QA synthetic demo",
        dataset_kind="synthetic",
        dev_mode=True,
    )


def test_administrator_denied_run_imports(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_permissions_admin.csv",
        CHASE_HEADER + fresh_row(),
    )

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
        assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
        response = client.post(
            f"/api/import-batches/{batch_id}/accept",
            json={"actor": "owner", "actor_context": administrator_context()},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_finance_manager_allowed_run_imports(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_permissions_fm.csv",
        CHASE_HEADER + fresh_row(),
    )

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
        assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
        response = client.post(
            f"/api/import-batches/{batch_id}/accept",
            json={"actor": "owner", "actor_context": finance_manager_context()},
        )

    assert response.status_code == 200


def test_finance_manager_legacy_owner_actor_retains_import_access(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_permissions_owner.csv",
        CHASE_HEADER + fresh_row(),
    )

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
        assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
        response = client.post(f"/api/import-batches/{batch_id}/accept")

    assert response.status_code == 200


def test_contributor_suggest_denied_for_review_decide(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_permissions_contrib.csv",
        CHASE_HEADER + fresh_row(),
    )

    with TestClient(app) as client:
        batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
        assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
        assert client.post(
            f"/api/import-batches/{batch_id}/accept",
            json={"actor": "owner", "actor_context": finance_manager_context()},
        ).status_code == 200
        transaction = client.get("/api/transactions").json()["transactions"][0]
        response = client.post(
            "/api/decision-events",
            json={
                "target_type": "canonical_transaction",
                "target_id": transaction["id"],
                "decision_type": "category_change",
                "field_name": "category",
                "proposed_value": "business",
                "approved_value": "business",
                "actor": "contributor",
                "actor_context": finance_contributor_context(),
                "suggestion_source": "owner",
                "explicit_user_action": True,
            },
        )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "permission_denied"
    assert detail["suggestion_allowed"] is True


def test_effective_permission_endpoint_reports_matrix(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        denied = client.get(
            "/api/permissions/effective",
            params={
                "action_key": ActionKey.IMPORTS_RUN.value,
                "data_scope_key": DataScopeKey.IMPORTED_SOURCE_RECORDS.value,
                "actor": "owner",
            },
            headers={"X-Actor-Context": json.dumps(administrator_context())},
        )
        allowed = client.get(
            "/api/permissions/effective",
            params={
                "action_key": ActionKey.IMPORTS_RUN.value,
                "data_scope_key": DataScopeKey.IMPORTED_SOURCE_RECORDS.value,
                "actor": "owner",
            },
            headers={"X-Actor-Context": json.dumps(finance_manager_context())},
        )

    assert denied.status_code == 200
    assert denied.json()["allowed"] is False
    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True


def test_preview_endpoint_qa_only(tmp_path):
    personal_app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    qa_app = create_app(
        data_root=tmp_path / "qa",
        local_bind_host="127.0.0.1",
        runtime_environment=qa_runtime(),
    )

    payload = {
        "persona_key": "finance_contributor",
        "action_key": ActionKey.REVIEW_DECIDE.value,
        "data_scope_key": DataScopeKey.REVIEW_DECISIONS.value,
    }

    with TestClient(personal_app) as personal_client:
        blocked = personal_client.post("/api/permissions/preview", json=payload)

    with TestClient(qa_app) as qa_client:
        allowed = qa_client.post("/api/permissions/preview", json=payload)

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "permission_preview_unavailable"
    assert allowed.status_code == 200
    assert allowed.json()["persona_key"] == "finance_contributor"
    assert allowed.json()["allowed"] is False
    assert allowed.json()["suggestion_allowed"] is True


def test_preview_endpoint_available_in_dev_mode(tmp_path):
    dev_runtime = RuntimeEnvironment(
        app_env="personal",
        app_env_label="Personal data",
        dataset_kind="personal",
        dev_mode=True,
    )
    app = create_app(
        data_root=tmp_path,
        local_bind_host="127.0.0.1",
        runtime_environment=dev_runtime,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/permissions/preview",
            json={
                "persona_key": "administrator",
                "action_key": ActionKey.IMPORTS_RUN.value,
                "data_scope_key": DataScopeKey.IMPORTED_SOURCE_RECORDS.value,
            },
        )

    assert response.status_code == 200
    assert response.json()["allowed"] is False
