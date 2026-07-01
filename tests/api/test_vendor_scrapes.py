from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from family_finance_os.database import create_sqlite_engine
from family_finance_os.jobs import record_job
from family_finance_os.main import create_app
from family_finance_os.models import Job
from family_finance_os.vendor_scrapes import (
    VendorScrapeAdapterOutput,
    VendorScrapeError,
    load_synthetic_fixture,
    validate_vendor_scrape_output,
)


def _session_factory(data_root):
    engine = create_sqlite_engine(data_root / "database" / "family_finance_os.sqlite3")
    return sessionmaker(bind=engine)


def _enable_vendor(client: TestClient, vendor_key: str) -> None:
    response = client.patch(
        "/api/settings",
        json={
            "actor": "owner",
            "changes": [
                {
                    "domain": "future_integrations",
                    "setting_key": f"vendor_scraper.{vendor_key}.enabled",
                    "value": True,
                    "note": f"Enable synthetic {vendor_key} scraper for tests.",
                }
            ],
        },
    )
    assert response.status_code == 200


def test_vendor_adapter_registry_lists_three_vendors_disabled_by_default(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.get("/api/vendor-adapters")

    assert response.status_code == 200
    adapters = response.json()["adapters"]
    assert {adapter["vendor_key"] for adapter in adapters} == {"amazon", "costco", "walmart"}
    assert all(adapter["enabled"] is False for adapter in adapters)
    assert all(adapter["last_run"] is None for adapter in adapters)


def test_vendor_scrape_rejects_credential_fields(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _enable_vendor(client, "amazon")
        response = client.post(
            "/api/vendor-scrapes",
            json={
                "actor": "owner",
                "vendor_key": "amazon",
                "mode": "synthetic",
                "access_token": "secret",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "vendor_scrape_credentials_forbidden"


def test_disabled_adapter_cannot_run(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.post(
            "/api/vendor-scrapes",
            json={
                "actor": "owner",
                "vendor_key": "amazon",
                "mode": "synthetic",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "vendor_scrape_disabled"


def test_synthetic_run_creates_receipts_and_review_queue_items(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _enable_vendor(client, "amazon")
        run = client.post(
            "/api/vendor-scrapes",
            json={
                "actor": "owner",
                "vendor_key": "amazon",
                "mode": "synthetic",
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
            },
        )
        job_id = run.json()["job"]["id"]
        events = client.get(f"/api/vendor-scrapes/{job_id}/events")
        queue = client.get("/api/receipt-review-queue")
        receipts = client.get("/api/receipts")

    assert run.status_code == 200
    assert run.json()["job"]["status"] == "completed"
    assert len(run.json()["receipts"]) == 1
    assert run.json()["receipts"][0]["source_type"] == "vendor_scraper"
    assert events.status_code == 200
    stage_names = [event["stage"] for event in events.json()["events"]]
    assert stage_names == [
        "prepare",
        "prepare",
        "collect",
        "collect",
        "normalize",
        "normalize",
        "validate",
        "validate",
        "persist",
        "persist",
        "audit",
        "audit",
    ]
    assert queue.status_code == 200
    assert queue.json()["count"] >= 1
    assert receipts.status_code == 200
    assert len(receipts.json()["receipts"]) == 1

    artifact_path = tmp_path / "vendor_scrapes" / job_id / "normalized_output.json"
    assert artifact_path.exists()


def test_vendor_scrape_rejects_unsafe_output_path(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _enable_vendor(client, "amazon")
        response = client.post(
            "/api/vendor-scrapes",
            json={
                "actor": "owner",
                "vendor_key": "amazon",
                "mode": "synthetic",
                "output_directory": "/tmp/vendor-scrape-outside-data-root",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "vendor_scrape_output_path_unsafe"


def test_cancel_marks_job_canceled_with_event(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    Session = _session_factory(tmp_path)

    with TestClient(app):
        pass

    with Session() as session:
        job = record_job(
            session,
            job_type="vendor_scrape",
            status="running",
            actor="owner",
            input_json=json.dumps({"vendor_key": "amazon", "mode": "synthetic"}, sort_keys=True),
            output_json=json.dumps({"events": []}, sort_keys=True),
        )
        session.commit()
        job_id = job.id

    with TestClient(app) as client:
        response = client.post(
            f"/api/vendor-scrapes/{job_id}/cancel",
            json={"actor": "owner"},
        )
        events = client.get(f"/api/vendor-scrapes/{job_id}/events")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "canceled"
    assert events.status_code == 200
    assert events.json()["events"][-1]["stage"] == "cancel"
    assert events.json()["events"][-1]["status"] == "canceled"


def test_validation_catches_invalid_synthetic_fixture(tmp_path):
    payload = VendorScrapeAdapterOutput.model_validate(load_synthetic_fixture("amazon", fixture_name="vendor_scrape_amazon_invalid.json"))

    with pytest.raises(VendorScrapeError) as exc_info:
        validate_vendor_scrape_output(payload)
    findings = exc_info.value.detail["findings"]
    codes = {finding["code"] for finding in findings}
    assert "duplicate_external_receipt_id" in codes
    assert "missing_receipt_total" in codes or "receipt_total_mismatch" in codes
