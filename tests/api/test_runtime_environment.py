from fastapi.testclient import TestClient
import pytest

from dillon_finances.main import create_app
from dillon_finances.runtime import RuntimeEnvironmentConfigurationError


def test_status_reports_personal_runtime_identity_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_ENV_LABEL", raising=False)
    monkeypatch.delenv("DATASET_KIND", raising=False)
    monkeypatch.delenv("DEV_MODE", raising=False)
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        body = client.get("/api/status").json()
        settings = client.get("/api/settings").json()

    assert body["app_env"] == "personal"
    assert body["app_env_label"] == "Personal data"
    assert body["dataset_kind"] == "personal"
    assert body["dev_mode"] is False
    assert body["qa_controls_enabled"] is False
    assert settings["runtime"]["app_env"] == "personal"
    assert settings["runtime"]["qa_controls_enabled"] is False


def test_status_reports_qa_runtime_identity_and_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "qa")
    monkeypatch.delenv("APP_ENV_LABEL", raising=False)
    monkeypatch.setenv("DATASET_KIND", "synthetic")
    monkeypatch.setenv("DEV_MODE", "true")
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        body = client.get("/api/health").json()
        summary = client.get("/api/operator-summary").json()

    assert body["app_env"] == "qa"
    assert body["app_env_label"] == "QA synthetic demo"
    assert body["dataset_kind"] == "synthetic"
    assert body["dev_mode"] is True
    assert body["qa_controls_enabled"] is True
    assert summary["runtime"]["app_env"] == "qa"
    assert summary["runtime"]["dataset_kind"] == "synthetic"


def test_invalid_runtime_environment_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeEnvironmentConfigurationError, match="APP_ENV"):
        create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
