from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from family_finance_os.main import create_app
from family_finance_os.vendor_adapters import get_adapter
from family_finance_os.vendor_adapters.base import load_collect_fixture
from family_finance_os.vendor_scrapes import validate_vendor_scrape_output


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


@pytest.mark.parametrize("vendor_key", ["amazon", "costco", "walmart"])
def test_synthetic_pipeline_creates_vendor_scraper_receipts(tmp_path, vendor_key: str):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _enable_vendor(client, vendor_key)
        run = client.post(
            "/api/vendor-scrapes",
            json={
                "actor": "owner",
                "vendor_key": vendor_key,
                "mode": "synthetic",
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
            },
        )
        queue = client.get("/api/receipt-review-queue")

    assert run.status_code == 200
    assert run.json()["job"]["status"] == "completed"
    assert len(run.json()["receipts"]) >= 1
    assert all(receipt["source_type"] == "vendor_scraper" for receipt in run.json()["receipts"])
    assert queue.status_code == 200
    assert queue.json()["count"] >= 1


def test_amazon_split_charge_produces_warnings_and_review_flags():
    adapter = get_adapter("amazon")
    raw = load_collect_fixture("amazon", fixture_name="vendor_collect_amazon_split.json")
    output = adapter.normalize(raw, run_id="job_test_split")
    validate_vendor_scrape_output(output)

    assert any("amazon_split_charge" in warning for warning in output.quality.warnings)
    assert output.receipts[0].lines[0].review_status == "needs_review"
    assert output.receipts[0].lines[0].metadata_json is not None
    assert "split_charge" in output.receipts[0].lines[0].metadata_json


def test_costco_pharmacy_line_needs_review():
    adapter = get_adapter("costco")
    raw = load_collect_fixture("costco")
    output = adapter.normalize(raw, run_id="job_test_costco")
    validate_vendor_scrape_output(output)

    pharmacy_lines = [line for line in output.receipts[0].lines if "Ibuprofen" in line.item_description]
    assert pharmacy_lines
    assert pharmacy_lines[0].review_status == "needs_review"
    assert "pharmacy" in pharmacy_lines[0].metadata_json
    assert any("costco_mixed_basket_candidate" in warning for warning in output.quality.warnings)


def test_walmart_pickup_substitution_and_fee_lines():
    adapter = get_adapter("walmart")
    raw = load_collect_fixture("walmart")
    output = adapter.normalize(raw, run_id="job_test_walmart")
    validate_vendor_scrape_output(output)

    component_types = {
        json.loads(line.metadata_json)["review_reason"]
        for line in output.receipts[0].lines
        if line.metadata_json
    }
    assert "substitution" in component_types
    assert "pickup_fee" in component_types
    assert any("walmart_substitution" in warning for warning in output.quality.warnings)
    assert any("walmart_fee_line" in warning for warning in output.quality.warnings)


def test_manual_browser_assist_reads_inbox_json(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    inbox_dir = tmp_path / "vendor_scrapes" / "inbox" / "amazon"
    inbox_dir.mkdir(parents=True)
    inbox_payload = load_collect_fixture("amazon")
    (inbox_dir / "browser_export_1.json").write_text(json.dumps(inbox_payload), encoding="utf-8")

    with TestClient(app) as client:
        _enable_vendor(client, "amazon")
        run = client.post(
            "/api/vendor-scrapes",
            json={
                "actor": "owner",
                "vendor_key": "amazon",
                "mode": "manual_browser_assist",
            },
        )

    assert run.status_code == 200
    assert run.json()["job"]["status"] == "completed"
    assert len(run.json()["receipts"]) == 1
    assert run.json()["receipts"][0]["merchant_name"] == "SYNTHETIC Amazon"


def test_manual_browser_assist_empty_inbox_raises(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")
    inbox_dir = tmp_path / "vendor_scrapes" / "inbox" / "amazon"
    inbox_dir.mkdir(parents=True)

    with TestClient(app) as client:
        _enable_vendor(client, "amazon")
        response = client.post(
            "/api/vendor-scrapes",
            json={
                "actor": "owner",
                "vendor_key": "amazon",
                "mode": "manual_browser_assist",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "vendor_scrape_collect_empty"
