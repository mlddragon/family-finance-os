from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from family_finance_os.main import create_app
from family_finance_os.runtime import SYNTHETIC_ARTIFACT_MARKER


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


def create_accepted_batch(client: TestClient, data_root: Path) -> None:
    write_inbox_file(data_root, "SYNTHETIC_marker_chase.csv", CHASE_HEADER + fresh_row())
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    assert client.post(f"/api/import-batches/{batch_id}/validate").status_code == 200
    assert client.post(f"/api/import-batches/{batch_id}/accept").status_code == 200


def test_synthetic_reports_and_exports_include_artifact_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "qa")
    monkeypatch.setenv("DATASET_KIND", "synthetic")
    monkeypatch.setenv("DEV_MODE", "true")
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_batch(client, tmp_path)
        reports = client.post("/api/reports/run", json={"actor": "owner"})
        close = client.post("/api/monthly-close/draft", json={"actor": "owner"})
        export = client.post("/api/exports/advisor", json={"actor": "owner"})

    assert reports.status_code == 200
    assert close.status_code == 200
    assert export.status_code == 200
    for response in (reports, close, export):
        for artifact in response.json()["artifacts"]:
            content = Path(artifact["path"]).read_text()
            assert SYNTHETIC_ARTIFACT_MARKER in content

    manifest_artifact = next(
        artifact for artifact in close.json()["artifacts"] if artifact["artifact_type"] == "monthly_close_manifest"
    )
    manifest = json.loads(Path(manifest_artifact["path"]).read_text())
    assert manifest["synthetic_artifact_marker"] == SYNTHETIC_ARTIFACT_MARKER


def test_personal_reports_do_not_include_synthetic_artifact_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "personal")
    monkeypatch.setenv("DATASET_KIND", "personal")
    monkeypatch.setenv("DEV_MODE", "false")
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        create_accepted_batch(client, tmp_path)
        response = client.post("/api/reports/run", json={"actor": "owner"})

    assert response.status_code == 200
    for artifact in response.json()["artifacts"]:
        assert SYNTHETIC_ARTIFACT_MARKER not in Path(artifact["path"]).read_text()
