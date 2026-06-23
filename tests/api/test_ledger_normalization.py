from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from family_finance_os.ledger_normalization import (
    NormalizedLedgerRow,
    canonical_transaction_identity,
    imported_row_hash,
    imported_row_identity,
)
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


def accept_first_batch(client: TestClient, acknowledge_warnings: bool = False) -> dict:
    batch_id = client.post("/api/inbox/scan").json()["import_batches"][-1]["id"]
    validation_response = client.post(f"/api/import-batches/{batch_id}/validate")
    assert validation_response.status_code == 200
    accept_response = client.post(
        f"/api/import-batches/{batch_id}/accept",
        json={"acknowledge_warnings": acknowledge_warnings},
    )
    assert accept_response.status_code == 200
    return accept_response.json()


def test_identity_hashes_are_deterministic():
    row = NormalizedLedgerRow(
        source_row_number=2,
        posted_date="2026-06-18",
        effective_date="2026-06-19",
        raw_description="SYNTHETIC GROCERY",
        normalized_merchant="synthetic grocery",
        amount="12.34",
        direction="outflow",
        balance=None,
        initial_category="Food",
        initial_subcategory=None,
        source_transaction_id=None,
        parser_version="chase_prime_visa:v1",
    )

    row_hash = imported_row_hash(row)

    assert row_hash == imported_row_hash(row)
    assert imported_row_identity("account-1", "a" * 64, 2, row_hash) == imported_row_identity(
        "account-1",
        "a" * 64,
        2,
        row_hash,
    )
    assert canonical_transaction_identity(row, "account-1") == canonical_transaction_identity(
        row,
        "account-1",
    )


def test_accepting_synthetic_file_normalizes_rows_and_exposes_transaction_api(tmp_path):
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_chase_normalize.csv",
        CHASE_HEADER
        + fresh_row("SYNTHETIC GROCERY", "12.34")
        + fresh_row("SYNTHETIC FUEL", "45.67"),
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accept_first_batch(client)
        transactions_response = client.get("/api/transactions")
        assert transactions_response.status_code == 200
        transactions = transactions_response.json()["transactions"]
        detail_response = client.get(f"/api/transactions/{transactions[0]['id']}")

    assert len(transactions) == 2
    assert transactions[0]["review_status"] == "unreviewed"
    assert transactions[0]["validation_status"] == "ready_for_review"
    assert transactions[0]["imported_fact_count"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["transaction"]["imported_facts"][0]["raw_description"].startswith(
        "SYNTHETIC"
    )


def test_reimport_does_not_overwrite_imported_rows(tmp_path):
    content = CHASE_HEADER + fresh_row("SYNTHETIC DUPLICATE", "12.34")
    write_inbox_file(tmp_path, "SYNTHETIC_duplicate_one.csv", content)
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accept_first_batch(client)
        first_transactions = client.get("/api/transactions").json()["transactions"]
        first_detail = client.get(f"/api/transactions/{first_transactions[0]['id']}").json()
        first_fact_id = first_detail["transaction"]["imported_facts"][0]["id"]

        write_inbox_file(tmp_path, "SYNTHETIC_duplicate_two.csv", content)
        accept_first_batch(client, acknowledge_warnings=True)
        second_transactions = client.get("/api/transactions").json()["transactions"]
        second_detail = client.get(f"/api/transactions/{second_transactions[0]['id']}").json()

    assert len(second_transactions) == 1
    assert second_detail["transaction"]["imported_facts"][0]["id"] == first_fact_id
    assert second_detail["transaction"]["imported_facts"][0]["raw_description"] == "SYNTHETIC DUPLICATE"


def test_ambiguous_canonical_candidates_create_blocking_finding(tmp_path):
    duplicate_row = fresh_row("SYNTHETIC SAME STORE", "12.34")
    write_inbox_file(
        tmp_path,
        "SYNTHETIC_ambiguous.csv",
        CHASE_HEADER + duplicate_row + duplicate_row,
    )
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        accept_first_batch(client)
        findings_response = client.get("/api/validation-findings")
        transactions_response = client.get("/api/transactions")

    findings = findings_response.json()["findings"]
    transactions = transactions_response.json()["transactions"]
    assert any(
        finding["severity"] == "blocking" and finding["code"] == "duplicate_canonical_candidate"
        for finding in findings
    )
    assert len(transactions) == 1
    assert transactions[0]["validation_status"] == "blocked"
    assert transactions[0]["imported_fact_count"] == 2
