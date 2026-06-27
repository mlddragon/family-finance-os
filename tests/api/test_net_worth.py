from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from family_finance_os.database import create_sqlite_engine
from family_finance_os.main import create_app
from family_finance_os.models import DecisionEvent, NetWorthSnapshot


SYNTHETIC_NET_WORTH_CSV = """snapshot_date,asset_or_liability,account_name,institution,category,subcategory,balance,valuation_method,confidence,source_notes
2026-06-30,asset,SYNTHETIC Cash,Local Credit Union,liquid_cash,checking,1200.00,actual,high,
2026-06-30,liability,SYNTHETIC Card,Card Issuer,consumer_debt,card,300.00,actual,high,
2026-06-30,asset,SYNTHETIC Vehicle,Garage,vehicle,sedan,8000.00,estimate,medium,SYNTHETIC market estimate
"""


def _session_factory(data_root: Path):
    engine = create_sqlite_engine(data_root / "database" / "family_finance_os.sqlite3")
    return sessionmaker(bind=engine)


def test_snapshot_crud_records_decisions_and_summary_excludes_estimates_by_default(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        actual = client.post(
            "/api/net-worth/snapshots",
            json={
                "actor": "owner",
                "snapshot_date": "2026-06-30",
                "asset_or_liability": "asset",
                "account_name": "SYNTHETIC Checking",
                "institution": "Local Credit Union",
                "category": "liquid_cash",
                "balance": "1500.00",
                "valuation_method": "actual",
            },
        )
        estimate = client.post(
            "/api/net-worth/snapshots",
            json={
                "actor": "owner",
                "snapshot_date": "2026-06-30",
                "asset_or_liability": "asset",
                "account_name": "SYNTHETIC Vehicle",
                "institution": "Garage",
                "category": "vehicle",
                "balance": "8000.00",
                "valuation_method": "estimate",
                "confidence": "medium",
                "source_notes": "SYNTHETIC market estimate.",
            },
        )
        liability = client.post(
            "/api/net-worth/snapshots",
            json={
                "actor": "owner",
                "snapshot_date": "2026-06-30",
                "asset_or_liability": "liability",
                "account_name": "SYNTHETIC Card",
                "category": "consumer_debt",
                "balance": "275.00",
                "valuation_method": "actual",
            },
        )
        patched = client.patch(
            f"/api/net-worth/snapshots/{liability.json()['snapshot']['id']}",
            json={"actor": "owner", "balance": "300.00", "note": "Correct synthetic liability."},
        )
        listed = client.get("/api/net-worth/snapshots?from=2026-06-01&to=2026-06-30")
        summary = client.get("/api/net-worth/summary?from=2026-06-01&to=2026-06-30")
        summary_with_estimates = client.get("/api/net-worth/summary?include_estimates=true")
        deleted = client.request(
            "DELETE",
            f"/api/net-worth/snapshots/{estimate.json()['snapshot']['id']}",
            json={"actor": "owner", "note": "Remove synthetic estimate."},
        )

    assert actual.status_code == 200
    assert actual.json()["snapshot"]["confidence"] == "high"
    assert actual.json()["snapshot"]["include_in_actual_net_worth"] is True
    assert estimate.status_code == 200
    assert estimate.json()["snapshot"]["include_in_actual_net_worth"] is False
    assert liability.status_code == 200
    assert patched.status_code == 200
    assert patched.json()["snapshot"]["balance"] == "300.00"
    assert listed.status_code == 200
    assert [snapshot["account_name"] for snapshot in listed.json()["snapshots"]] == [
        "SYNTHETIC Checking",
        "SYNTHETIC Vehicle",
        "SYNTHETIC Card",
    ]
    assert summary.status_code == 200
    assert summary.json()["actual"] == {"assets": "1500.00", "liabilities": "300.00", "net_worth": "1200.00"}
    assert summary.json()["with_estimates"] == {
        "assets": "9500.00",
        "liabilities": "300.00",
        "net_worth": "9200.00",
        "includes_estimates": True,
    }
    assert summary.json()["include_estimates"] is False
    assert summary_with_estimates.json()["include_estimates"] is True
    assert summary_with_estimates.json()["series"][0]["includes_estimates"] is True
    assert deleted.status_code == 200

    Session = _session_factory(tmp_path)
    with Session() as session:
        snapshots = session.scalars(select(NetWorthSnapshot)).all()
        decision_types = [
            event.decision_type
            for event in session.scalars(select(DecisionEvent).order_by(DecisionEvent.created_at, DecisionEvent.id)).all()
        ]
    assert [snapshot.account_name for snapshot in snapshots] == ["SYNTHETIC Checking", "SYNTHETIC Card"]
    assert decision_types == [
        "net_worth_snapshot_create",
        "net_worth_snapshot_create",
        "net_worth_snapshot_create",
        "net_worth_snapshot_update",
        "net_worth_snapshot_delete",
    ]


def test_estimate_and_csv_validation_use_stable_error_codes(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        missing_estimate_metadata = client.post(
            "/api/net-worth/snapshots",
            json={
                "actor": "owner",
                "snapshot_date": "2026-06-30",
                "asset_or_liability": "asset",
                "account_name": "SYNTHETIC Home",
                "category": "home",
                "balance": "350000.00",
                "valuation_method": "estimate",
            },
        )
        account_number_column = client.post(
            "/api/net-worth/imports",
            files={
                "file": (
                    "SYNTHETIC_net_worth_invalid.csv",
                    "snapshot_date,asset_or_liability,account_name,institution,category,subcategory,balance,valuation_method,confidence,source_notes,account_number\n"
                    "2026-06-30,asset,SYNTHETIC Cash,Credit Union,liquid_cash,checking,100.00,actual,high,,1234\n",
                    "text/csv",
                )
            },
            data={"actor": "owner"},
        )
        invalid_date = client.post(
            "/api/net-worth/imports",
            files={
                "file": (
                    "SYNTHETIC_net_worth_bad_date.csv",
                    "snapshot_date,asset_or_liability,account_name,institution,category,subcategory,balance,valuation_method,confidence,source_notes\n"
                    "06/30/2026,asset,SYNTHETIC Cash,Credit Union,liquid_cash,checking,100.00,actual,high,\n",
                    "text/csv",
                )
            },
            data={"actor": "owner"},
        )

    assert missing_estimate_metadata.status_code == 422
    assert missing_estimate_metadata.json()["detail"]["code"] == "estimate_metadata_required"
    assert account_number_column.status_code == 422
    assert account_number_column.json()["detail"]["code"] == "net_worth_csv_unexpected_columns"
    assert invalid_date.status_code == 422
    assert invalid_date.json()["detail"]["code"] == "net_worth_csv_validation_failed"
    assert invalid_date.json()["detail"]["findings"][0]["code"] == "invalid_snapshot_date"


def test_csv_import_preview_requires_accept_before_rows_affect_summary(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        preview = client.post(
            "/api/net-worth/imports",
            files={"file": ("SYNTHETIC_net_worth.csv", SYNTHETIC_NET_WORTH_CSV, "text/csv")},
            data={"actor": "owner"},
        )
        before_accept = client.get("/api/net-worth/summary?include_estimates=true")
        accepted = client.post(
            f"/api/net-worth/imports/{preview.json()['import']['id']}/accept",
            json={"actor": "owner", "note": "Accept synthetic net worth CSV."},
        )
        after_accept = client.get("/api/net-worth/summary?include_estimates=true")

    assert preview.status_code == 200
    preview_body = preview.json()["import"]
    assert preview_body["status"] == "validated"
    assert preview_body["accepted_count"] == 3
    assert preview_body["rejected_count"] == 0
    assert preview_body["stored_path"].startswith(str(tmp_path / "net_worth_imports"))
    assert before_accept.json()["actual"] == {"assets": "0.00", "liabilities": "0.00", "net_worth": "0.00"}
    assert accepted.status_code == 200
    assert accepted.json()["created_count"] == 3
    assert after_accept.json()["actual"] == {"assets": "1200.00", "liabilities": "300.00", "net_worth": "900.00"}
    assert after_accept.json()["with_estimates"]["net_worth"] == "8900.00"


def test_report_run_includes_net_worth_summary_artifact(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        created = client.post(
            "/api/net-worth/snapshots",
            json={
                "actor": "owner",
                "snapshot_date": "2026-06-30",
                "asset_or_liability": "asset",
                "account_name": "SYNTHETIC Checking",
                "category": "liquid_cash",
                "balance": "1500.00",
                "valuation_method": "actual",
            },
        )
        response = client.post("/api/reports/run", json={"actor": "owner", "month": "2026-06"})

    assert created.status_code == 200
    assert response.status_code == 200
    body = response.json()
    artifact_by_type = {artifact["artifact_type"]: artifact for artifact in body["artifacts"]}
    assert "net_worth_summary" in artifact_by_type
    artifact_path = Path(artifact_by_type["net_worth_summary"]["path"])
    assert artifact_path.name == "net_worth_summary.json"
    payload = json.loads(artifact_path.read_text())
    assert payload["actual"]["net_worth"] == "1500.00"
    assert payload["with_estimates"]["includes_estimates"] is True
