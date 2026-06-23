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


def accept_first_batch(client: TestClient) -> dict:
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    validation_response = client.post(f"/api/import-batches/{batch_id}/validate")
    assert validation_response.status_code == 200
    accept_response = client.post(f"/api/import-batches/{batch_id}/accept")
    assert accept_response.status_code == 200
    return accept_response.json()


def test_operator_summary_reports_empty_local_state(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.get("/api/operator-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["runtime"]["local_only"] is True
    assert body["runtime"]["data_root"]["path"] == str(tmp_path)
    assert body["latest_import"]["status"] == "none"
    assert body["sources"]["required_count"] == 0
    assert body["sources"]["missing_required_count"] == 0
    assert body["validation"]["open_blocking"] == 0
    assert body["review"]["total_transactions"] == 0
    assert body["monthly_close"]["status"] == "not_started"
    assert body["next_action"]["code"] == "upload_source_files"


def test_operator_summary_counts_import_validation_and_review_state(tmp_path):
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_chase_summary.csv",
        CHASE_HEADER + fresh_row("SYNTHETIC GROCERY", "12.34"),
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accepted_batch = accept_first_batch(client)
        response = client.get("/api/operator-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["latest_import"]["id"] == accepted_batch["id"]
    assert body["latest_import"]["status"] == "accepted"
    assert body["sources"]["imported_source_keys"] == ["chase_prime_visa"]
    assert body["sources"]["missing_required_count"] == 0
    assert body["validation"]["open_blocking"] == 0
    assert body["review"]["total_transactions"] == 1
    assert body["review"]["unreviewed"] == 1
    assert body["monthly_close"]["ready_for_draft"] is True
    assert body["monthly_close"]["ready_for_final"] is True
    assert body["next_action"]["code"] == "review_ledger_decisions"
