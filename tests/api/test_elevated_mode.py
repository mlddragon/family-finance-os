from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.database import create_sqlite_engine, resolve_database_path
from family_finance_os.elevated_mode import INACTIVITY_TIMEOUT
from family_finance_os.main import create_app
from family_finance_os.models import ElevatedModeEvent


CHASE_HEADER = "Transaction Date,Post Date,Description,Category,Amount\n"
SESSION_HEADER = "X-Elevated-Session-Id"


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


def enter_system_admin_mode(client: TestClient, session_id: str = "test-session-1") -> dict:
    response = client.post(
        "/api/elevated-mode/enter",
        params={"has_unsaved_edits": "false"},
        headers={SESSION_HEADER: session_id},
        json={
            "context": "system_administration",
            "purpose_code": "source_or_system_settings",
            "note": "SYNTHETIC elevated mode entry for settings work.",
            "actor": "owner",
            "actor_context": administrator_context(),
        },
    )
    assert response.status_code == 200
    return response.json()


def enter_financial_governance_mode(client: TestClient, session_id: str = "test-session-fg") -> dict:
    response = client.post(
        "/api/elevated-mode/enter",
        headers={SESSION_HEADER: session_id},
        json={
            "context": "financial_governance",
            "purpose_code": "approval_rule_change",
            "note": "SYNTHETIC elevated mode entry for governance review.",
            "actor": "owner",
            "actor_context": finance_manager_context(),
        },
    )
    assert response.status_code == 200
    return response.json()


def prepare_validated_import_batch(client: TestClient, tmp_path: Path, filename: str) -> str:
    write_inbox_file(tmp_path, filename, CHASE_HEADER + fresh_row())
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
    return batch_id


def test_elevated_mode_enter_exit_and_status(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-enter-exit"

    with TestClient(app) as client:
        inactive = client.get("/api/elevated-mode/status", headers={SESSION_HEADER: session_id})
        assert inactive.status_code == 200
        assert inactive.json()["active"] is False

        active = enter_system_admin_mode(client, session_id=session_id)
        assert active["active"] is True
        assert active["context"] == "system_administration"
        assert active["session_id"] == session_id

        status = client.get("/api/elevated-mode/status", headers={SESSION_HEADER: session_id})
        assert status.status_code == 200
        assert status.json()["active"] is True
        assert status.json()["purpose_code"] == "source_or_system_settings"

        exit_response = client.post(
            "/api/elevated-mode/exit",
            headers={SESSION_HEADER: session_id},
            json={"actor": "owner", "actor_context": administrator_context()},
        )
        assert exit_response.status_code == 200
        assert exit_response.json()["active"] is False

        status_after = client.get("/api/elevated-mode/status", headers={SESSION_HEADER: session_id})
        assert status_after.json()["active"] is False


def test_elevated_mode_blocks_unsaved_edits_and_missing_permissions(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-blocked-entry"

    with TestClient(app) as client:
        blocked_edits = client.post(
            "/api/elevated-mode/enter",
            params={"has_unsaved_edits": "true"},
            headers={SESSION_HEADER: session_id},
            json={
                "context": "system_administration",
                "purpose_code": "source_or_system_settings",
                "note": "Should not enter with unsaved edits.",
                "actor": "owner",
                "actor_context": administrator_context(),
            },
        )
        assert blocked_edits.status_code == 409
        assert blocked_edits.json()["detail"]["code"] == "elevated_mode_unsaved_edits"

        blocked_permissions = client.post(
            "/api/elevated-mode/enter",
            headers={SESSION_HEADER: "session-contributor"},
            json={
                "context": "financial_governance",
                "purpose_code": "approval_rule_change",
                "note": "Contributor should not enter financial governance mode.",
                "actor": "contributor",
                "actor_context": finance_contributor_context(),
            },
        )
        assert blocked_permissions.status_code == 403
        assert blocked_permissions.json()["detail"]["code"] == "elevated_mode_permission_denied"


def test_elevated_mode_touch_extends_session(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-touch"
    base_time = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    later = base_time + timedelta(minutes=10)

    with TestClient(app) as client:
        with patch("family_finance_os.elevated_mode.utc_now", return_value=base_time):
            enter_system_admin_mode(client, session_id=session_id)

        with patch("family_finance_os.elevated_mode.utc_now", return_value=later):
            touch = client.post(
                "/api/elevated-mode/touch",
                headers={SESSION_HEADER: session_id},
                json={"actor": "owner", "actor_context": administrator_context()},
            )
            assert touch.status_code == 200
            assert touch.json()["last_activity_at"] == later.isoformat()


def test_elevated_mode_expires_after_inactivity(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-expiry"
    entered_at = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    expired_at = entered_at + INACTIVITY_TIMEOUT + timedelta(seconds=1)

    with TestClient(app) as client:
        with patch("family_finance_os.elevated_mode.utc_now", return_value=entered_at):
            enter_system_admin_mode(client, session_id=session_id)

        with patch("family_finance_os.elevated_mode.utc_now", return_value=expired_at):
            status = client.get("/api/elevated-mode/status", headers={SESSION_HEADER: session_id})
            assert status.status_code == 200
            assert status.json()["active"] is False

        from family_finance_os.database import create_sqlite_engine, resolve_database_path

        engine = create_sqlite_engine(resolve_database_path(tmp_path / "database"))
        with Session(engine) as db_session:
            events = db_session.scalars(
                select(ElevatedModeEvent.event_type).order_by(ElevatedModeEvent.created_at)
            ).all()
        assert events == ["entered", "expired"]


def test_financial_mutation_blocked_while_elevated(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-finance-readonly"

    with TestClient(app) as client:
        batch_id = prepare_validated_import_batch(
            client,
            tmp_path,
            "SYNTHETIC_elevated_finance_block.csv",
        )
        allowed_before = client.post(
            f"/api/import-batches/{batch_id}/accept",
            headers={SESSION_HEADER: session_id},
            json={"actor": "owner", "actor_context": finance_manager_context()},
        )
        assert allowed_before.status_code == 200

    with TestClient(app) as client:
        batch_id = prepare_validated_import_batch(
            client,
            tmp_path,
            "SYNTHETIC_elevated_finance_block_2.csv",
        )
        enter_financial_governance_mode(client, session_id=session_id)
        blocked = client.post(
            f"/api/import-batches/{batch_id}/accept",
            headers={SESSION_HEADER: session_id},
            json={"actor": "owner", "actor_context": finance_manager_context()},
        )

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "permission_denied"


def test_runtime_settings_allowed_in_system_admin_elevated_mode(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-settings-allowed"

    with TestClient(app) as client:
        client.get("/api/settings")
        enter_system_admin_mode(client, session_id=session_id)
        response = client.patch(
            "/api/settings",
            headers={SESSION_HEADER: session_id},
            json={
                "actor": "owner",
                "actor_context": administrator_context(),
                "changes": [
                    {
                        "domain": "branding",
                        "setting_key": "branding.app_display_name",
                        "value": "SYNTHETIC Elevated Settings",
                    }
                ],
            },
        )

    assert response.status_code == 200
    branding_setting = next(
        setting
        for setting in response.json()["settings"]
        if setting["setting_key"] == "branding.app_display_name"
    )
    assert branding_setting["value"] == "SYNTHETIC Elevated Settings"


def test_import_blocked_in_system_admin_elevated_mode(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-admin-readonly"

    with TestClient(app) as client:
        batch_id = prepare_validated_import_batch(
            client,
            tmp_path,
            "SYNTHETIC_elevated_admin_block.csv",
        )
        enter_system_admin_mode(client, session_id=session_id)
        blocked = client.post(
            f"/api/import-batches/{batch_id}/accept",
            headers={SESSION_HEADER: session_id},
            json={"actor": "owner", "actor_context": administrator_context()},
        )

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "permission_denied"


def test_elevated_mode_allows_optional_note_for_most_purposes(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-optional-note"

    with TestClient(app) as client:
        response = client.post(
            "/api/elevated-mode/enter",
            headers={SESSION_HEADER: session_id},
            json={
                "context": "system_administration",
                "purpose_code": "maintenance_health_review",
                "note": "",
                "actor": "owner",
                "actor_context": administrator_context(),
            },
        )
        assert response.status_code == 200
        assert response.json()["note"] == ""


def test_elevated_mode_requires_note_for_approval_rule_change(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    session_id = "session-required-note"

    with TestClient(app) as client:
        blocked = client.post(
            "/api/elevated-mode/enter",
            headers={SESSION_HEADER: session_id},
            json={
                "context": "financial_governance",
                "purpose_code": "approval_rule_change",
                "note": "",
                "actor": "owner",
                "actor_context": finance_manager_context(),
            },
        )
        assert blocked.status_code == 422
        assert blocked.json()["detail"]["code"] == "elevated_mode_note_required"


def test_elevated_mode_status_includes_purpose_requires_note(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        status = client.get("/api/elevated-mode/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["purpose_requires_note"] == ["approval_rule_change"]
