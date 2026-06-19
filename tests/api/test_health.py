from fastapi.testclient import TestClient

from dillon_finances.main import create_app


def test_health_reports_local_only_data_root_and_database_status(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["app"] == "Dillon Finances"
    assert body["version"] == "0.1.0"
    assert body["local_only"] is True
    assert body["bind_host"] == "127.0.0.1"
    assert body["data_root"]["path"] == str(tmp_path)
    assert body["data_root"]["exists"] is True
    assert body["database"]["status"] == "not_initialized"


def test_status_uses_same_operational_payload_as_health(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    client = TestClient(app)

    health_response = client.get("/api/health")
    status_response = client.get("/api/status")

    assert status_response.status_code == 200
    assert status_response.json() == health_response.json()
