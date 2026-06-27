from __future__ import annotations

from datetime import datetime, timezone

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from family_finance_os.database import create_sqlite_engine
from family_finance_os.main import create_app
from family_finance_os.models import RecoveryCode, User, UserSession
from family_finance_os.runtime import RuntimeEnvironment


def _totp_code(secret: str) -> str:
    return pyotp.TOTP(secret).now()


def _enroll_owner(client: TestClient, username: str = "owner") -> dict:
    start = client.post(
        "/api/auth/enroll-owner",
        json={
            "username": username,
            "display_name": "SYNTHETIC Owner",
            "passphrase": "synthetic passphrase for tests",
            "totp_confirm_code": "000000",
            "recovery_acknowledged": True,
        },
    )
    assert start.status_code == 202
    secret = start.json()["totp_secret"]
    response = client.post(
        "/api/auth/enroll-owner",
        json={
            "username": username,
            "display_name": "SYNTHETIC Owner",
            "passphrase": "synthetic passphrase for tests",
            "totp_confirm_code": _totp_code(secret),
            "recovery_acknowledged": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def _database_session(data_root):
    engine = create_sqlite_engine(data_root / "database" / "family_finance_os.sqlite3")
    return sessionmaker(bind=engine)()


def test_auth_status_reports_first_boot_before_enrollment(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json()["requires_owner_enrollment"] is True
    assert response.json()["authenticated"] is False


def test_owner_enrollment_hashes_secrets_and_sets_http_only_session_cookie(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response_body = _enroll_owner(client)
        cookie_header = client.cookies.get("ffos_session")
        status = client.get("/api/auth/status").json()

    assert response_body["user"]["username"] == "owner"
    assert len(response_body["recovery_codes"]) == 10
    assert "ffos_session" not in response_body
    assert cookie_header
    assert status["authenticated"] is True
    assert status["user"]["role"] == "administrator"

    with _database_session(tmp_path) as session:
        user = session.scalar(select(User).where(User.username == "owner"))
        recovery_codes = session.scalars(select(RecoveryCode)).all()
        stored_session = session.scalar(select(UserSession))

    assert user is not None
    assert user.passphrase_hash.startswith("$argon2")
    assert user.passphrase_hash != "synthetic passphrase for tests"
    assert all(code.code_hash not in response_body["recovery_codes"] for code in recovery_codes)
    assert stored_session is not None
    assert stored_session.session_token_hash != cookie_header


def test_login_requires_passphrase_and_totp_after_logout(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enrollment = _enroll_owner(client)
        assert client.post("/api/auth/logout").status_code == 200
        failed = client.post(
            "/api/auth/login",
            json={
                "username": "owner",
                "passphrase": "wrong synthetic passphrase",
                "totp_code": "000000",
            },
        )
        success = client.post(
            "/api/auth/login",
            json={
                "username": "owner",
                "passphrase": "synthetic passphrase for tests",
                "totp_code": _totp_code(enrollment["totp_secret"]),
            },
        )

    assert failed.status_code == 401
    assert failed.json()["detail"]["code"] == "invalid_credentials"
    assert success.status_code == 200
    assert success.json()["user"]["username"] == "owner"


def test_recovery_login_marks_code_used_and_prevents_reuse(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        enrollment = _enroll_owner(client)
        recovery_code = enrollment["recovery_codes"][0]
        client.post("/api/auth/logout")
        first = client.post(
            "/api/auth/recovery-login",
            json={"username": "owner", "recovery_code": recovery_code},
        )
        client.post("/api/auth/logout")
        second = client.post(
            "/api/auth/recovery-login",
            json={"username": "owner", "recovery_code": recovery_code},
        )

    assert first.status_code == 200
    assert first.json()["session"]["created_from"] == "recovery"
    assert second.status_code == 401
    assert second.json()["detail"]["code"] == "invalid_recovery_code"

    with _database_session(tmp_path) as session:
        used_count = len(
            session.scalars(select(RecoveryCode).where(RecoveryCode.status == "used")).all()
        )

    assert used_count == 1


def test_authenticated_middleware_protects_routes_after_enrollment(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _enroll_owner(client)
        client.post("/api/auth/logout")
        protected = client.get("/api/operator-summary")
        public_health = client.get("/api/health")

    assert protected.status_code == 401
    assert protected.json()["detail"]["code"] == "authentication_required"
    assert public_health.status_code == 200


def test_dev_bypass_requires_qa_dev_mode_and_synthetic_data(tmp_path):
    personal_app = create_app(data_root=tmp_path / "personal", local_bind_host="127.0.0.1")
    qa_app = create_app(
        data_root=tmp_path / "qa",
        local_bind_host="127.0.0.1",
        runtime_environment=RuntimeEnvironment(
            app_env="qa",
            app_env_label="QA synthetic demo",
            dataset_kind="synthetic",
            dev_mode=True,
        ),
    )

    with TestClient(personal_app) as client:
        personal_response = client.post("/api/auth/dev-bypass", json={"role": "administrator"})

    with TestClient(qa_app) as client:
        qa_response = client.post("/api/auth/dev-bypass", json={"role": "administrator"})
        status_response = client.get("/api/auth/status")

    assert personal_response.status_code == 403
    assert personal_response.json()["detail"]["code"] == "dev_bypass_not_allowed"
    assert qa_response.status_code == 200
    assert qa_response.json()["user"]["username"] == "synthetic_admin"
    assert qa_response.json()["session"]["created_from"] == "dev_bypass"
    assert status_response.json()["qa_auth_bypass_available"] is True


def test_expired_session_is_revoked_and_rejected(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _enroll_owner(client)
        with _database_session(tmp_path) as session:
            stored_session = session.scalar(select(UserSession))
            assert stored_session is not None
            stored_session.idle_expires_at = "2000-01-01T00:00:00+00:00"
            session.commit()
        response = client.get("/api/operator-summary")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "authentication_required"

    with _database_session(tmp_path) as session:
        stored_session = session.scalar(select(UserSession))

    assert stored_session is not None
    assert stored_session.revoked_reason == "expired"
    assert datetime.fromisoformat(stored_session.revoked_at) <= datetime.now(timezone.utc)
