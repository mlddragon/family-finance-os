from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from family_finance_os.database import create_sqlite_engine
from family_finance_os.main import create_app
from family_finance_os.models import (
    CanonicalTransaction,
    Category,
    DecisionEvent,
    ImportBatch,
    ImportedRow,
    Receipt,
    Source,
    SourceAccount,
    SourceFile,
    TransactionAllocation,
)


def _session_factory(data_root):
    engine = create_sqlite_engine(data_root / "database" / "family_finance_os.sqlite3")
    return sessionmaker(bind=engine)


def _seed_outflow_transaction(session, *, identity: str, amount: Decimal, row_number: int) -> CanonicalTransaction:
    source = Source(
        source_key=f"synthetic_receipt_source_{row_number}",
        display_name=f"SYNTHETIC Receipt Source {row_number}",
        source_type="credit_card",
    )
    account = SourceAccount(
        source=source,
        account_key=f"synthetic_receipt_account_{row_number}",
        display_name=f"SYNTHETIC Receipt Account {row_number}",
        account_type="credit_card",
    )
    batch = ImportBatch(
        source=source,
        source_account=account,
        status="accepted",
        parser_version="synthetic-v1",
        validation_status="passed",
        row_count=1,
        transaction_date_min="2026-06-17",
        transaction_date_max="2026-06-17",
    )
    source_file = SourceFile(
        source=source,
        source_account=account,
        import_batch=batch,
        original_filename=f"SYNTHETIC_receipt_{row_number}.csv",
        stored_path=f"/data/raw/SYNTHETIC_receipt_{row_number}.csv",
        file_sha256=str(row_number) * 64,
        byte_size=128,
        validation_status="passed",
        row_count=1,
        parser_version="synthetic-v1",
    )
    canonical = CanonicalTransaction(
        canonical_identity=identity,
        source_account=account,
        posted_date="2026-06-17",
        amount=amount,
        description_fingerprint=identity,
        status="active",
    )
    session.add(
        ImportedRow(
            import_batch=batch,
            source_file=source_file,
            source_account=account,
            canonical_transaction=canonical,
            source_row_number=row_number,
            imported_row_hash=str(row_number) * 64,
            imported_row_identity=f"synthetic-receipt-row-{row_number}",
            posted_date="2026-06-17",
            raw_description="SYNTHETIC MARKET",
            normalized_merchant="Synthetic Market",
            amount=amount,
            direction="outflow",
            parser_version="synthetic-v1",
        )
    )
    session.flush()
    return canonical


def _seed_receipt_fixture(data_root) -> dict[str, str]:
    Session = _session_factory(data_root)
    with Session() as session:
        groceries = session.scalar(select(Category).where(Category.category_key == "groceries"))
        household = session.scalar(select(Category).where(Category.category_key == "household"))
        assert groceries is not None
        assert household is not None
        transaction = _seed_outflow_transaction(
            session,
            identity="synthetic-receipt-mixed-basket",
            amount=Decimal("-120.00"),
            row_number=1,
        )
        session.commit()
        return {
            "transaction_id": transaction.id,
            "groceries_id": groceries.id,
            "household_id": household.id,
        }


SYNTHETIC_RECEIPT_CSV = """merchant,purchase_date,receipt_total,line_description,line_quantity,line_amount,category_id,transaction_id
SYNTHETIC Market,2026-06-17,120.00,SYNTHETIC groceries,1,80.00,{groceries_id},
SYNTHETIC Market,2026-06-17,120.00,SYNTHETIC household,1,40.00,{household_id},
"""


def test_receipt_crud_records_decisions_and_review_queue(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        fixture = _seed_receipt_fixture(tmp_path)
        created = client.post(
            "/api/receipts",
            json={
                "actor": "owner",
                "merchant_name": "SYNTHETIC Market",
                "purchase_date": "2026-06-17",
                "receipt_total": "120.00",
                "canonical_transaction_id": fixture["transaction_id"],
                "lines": [
                    {
                        "item_description": "SYNTHETIC groceries",
                        "line_total": "80.00",
                        "category_id": fixture["groceries_id"],
                    },
                    {
                        "item_description": "SYNTHETIC household",
                        "line_total": "40.00",
                        "category_id": fixture["household_id"],
                    },
                ],
            },
        )
        receipt_id = created.json()["receipt"]["id"]
        fetched = client.get(f"/api/receipts/{receipt_id}")
        listed = client.get(f"/api/receipts?transaction_id={fixture['transaction_id']}")
        patched = client.patch(
            f"/api/receipts/{receipt_id}",
            json={"actor": "owner", "review_status": "reviewed", "note": "SYNTHETIC receipt reviewed."},
        )
        queue = client.get("/api/receipt-review-queue")

    assert created.status_code == 200
    assert created.json()["receipt"]["status"] == "matched"
    assert created.json()["receipt"]["summary"]["unaccounted_amount"] == "0.00"
    assert fetched.status_code == 200
    assert len(listed.json()["receipts"]) == 1
    assert patched.status_code == 200
    assert patched.json()["receipt"]["review_status"] == "reviewed"
    assert queue.status_code == 200
    assert queue.json()["count"] == 0

    Session = _session_factory(tmp_path)
    with Session() as session:
        event_types = session.scalars(
            select(DecisionEvent.decision_type).order_by(DecisionEvent.created_at, DecisionEvent.id)
        ).all()
    assert "receipt_create" in event_types
    assert "receipt_update" in event_types


def test_receipt_csv_import_preview_and_accept(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        fixture = _seed_receipt_fixture(tmp_path)
        csv_text = SYNTHETIC_RECEIPT_CSV.format(**fixture)
        preview = client.post(
            "/api/receipts/imports",
            data={"actor": "owner"},
            files={"file": ("SYNTHETIC_receipts.csv", BytesIO(csv_text.encode("utf-8")), "text/csv")},
        )
        import_id = preview.json()["import"]["id"]
        accepted = client.post(
            f"/api/receipts/imports/{import_id}/accept",
            json={"actor": "owner", "note": "Accept synthetic receipt import."},
        )
        duplicate = client.post(
            f"/api/receipts/imports/{import_id}/accept",
            json={"actor": "owner"},
        )

    assert preview.status_code == 200
    assert preview.json()["import"]["status"] == "validated"
    assert preview.json()["import"]["accepted_count"] == 1
    assert accepted.status_code == 200
    assert accepted.json()["created_count"] == 1
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "receipt_import_already_accepted"

    Session = _session_factory(tmp_path)
    with Session() as session:
        receipts = session.scalars(select(Receipt)).all()
    assert len(receipts) == 1
    assert receipts[0].source_type == "csv_import"


def test_receipt_promotion_creates_balanced_splits(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        fixture = _seed_receipt_fixture(tmp_path)
        created = client.post(
            "/api/receipts",
            json={
                "actor": "owner",
                "merchant_name": "SYNTHETIC Market",
                "purchase_date": "2026-06-17",
                "receipt_total": "120.00",
                "canonical_transaction_id": fixture["transaction_id"],
                "lines": [
                    {
                        "item_description": "SYNTHETIC groceries",
                        "line_total": "80.00",
                        "category_id": fixture["groceries_id"],
                    },
                    {
                        "item_description": "SYNTHETIC household",
                        "line_total": "40.00",
                        "category_id": fixture["household_id"],
                    },
                ],
            },
        )
        receipt_id = created.json()["receipt"]["id"]
        blocked = client.post(
            f"/api/receipts/{receipt_id}/promote-to-splits",
            json={
                "actor": "owner",
                "transaction_id": fixture["transaction_id"],
                "confirm": False,
            },
        )
        promoted = client.post(
            f"/api/receipts/{receipt_id}/promote-to-splits",
            json={
                "actor": "owner",
                "transaction_id": fixture["transaction_id"],
                "confirm": True,
                "note": "Promote synthetic receipt lines.",
            },
        )
        allocations = client.get(f"/api/transactions/{fixture['transaction_id']}/allocations")

    assert blocked.status_code == 422
    assert blocked.json()["detail"]["code"] == "receipt_promotion_confirmation_required"
    assert promoted.status_code == 200
    assert promoted.json()["summary"]["balanced"] is True
    assert allocations.status_code == 200
    assert allocations.json()["summary"]["allocation_count"] == 2
    assert allocations.json()["allocations"][0]["source"] == "receipt_promoted"

    Session = _session_factory(tmp_path)
    with Session() as session:
        receipt = session.get(Receipt, receipt_id)
        allocation_sources = session.scalars(select(TransactionAllocation.source)).all()
        event_types = session.scalars(select(DecisionEvent.decision_type)).all()
    assert receipt is not None
    assert receipt.status == "matched"
    assert receipt.review_status == "reviewed"
    assert receipt.applied_as_split_decision_event_id is not None
    assert allocation_sources == ["receipt_promoted", "receipt_promoted"]
    assert "transaction_split_replace" in event_types
