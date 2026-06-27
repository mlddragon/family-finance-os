from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from family_finance_os.database import create_sqlite_engine
from family_finance_os.main import create_app
from family_finance_os.models import (
    CanonicalTransaction,
    Category,
    DecisionEvent,
    FundPool,
    ImportBatch,
    ImportedRow,
    Source,
    SourceAccount,
    SourceFile,
    TransactionAllocation,
)
from family_finance_os.reporting import _category_spending_summary, _reviewed_transaction_rows


def _session_factory(data_root):
    engine = create_sqlite_engine(data_root / "database" / "family_finance_os.sqlite3")
    return sessionmaker(bind=engine)


def _seed_outflow_transaction(
    session,
    *,
    identity: str,
    description: str,
    amount: Decimal,
    row_number: int,
) -> CanonicalTransaction:
    source = Source(
        source_key=f"synthetic_split_source_{row_number}",
        display_name=f"SYNTHETIC Split Source {row_number}",
        source_type="credit_card",
    )
    account = SourceAccount(
        source=source,
        account_key=f"synthetic_split_account_{row_number}",
        display_name=f"SYNTHETIC Split Account {row_number}",
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
        original_filename=f"SYNTHETIC_split_{row_number}.csv",
        stored_path=f"/data/raw/SYNTHETIC_split_{row_number}.csv",
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
            imported_row_identity=f"synthetic-split-row-{row_number}",
            posted_date="2026-06-17",
            raw_description=description,
            normalized_merchant=description.title(),
            amount=amount,
            direction="outflow",
            parser_version="synthetic-v1",
        )
    )
    session.flush()
    return canonical


def _seed_split_fixture(data_root) -> dict[str, str]:
    Session = _session_factory(data_root)
    with Session() as session:
        groceries = session.scalar(select(Category).where(Category.category_key == "groceries"))
        utilities = session.scalar(select(Category).where(Category.category_key == "utilities"))
        household = session.scalar(select(Category).where(Category.category_key == "household"))
        assert groceries is not None
        assert utilities is not None
        assert household is not None
        pool = FundPool(
            pool_key="synthetic_household",
            name="SYNTHETIC Household",
            status="active",
            sort_order=10,
            rollover_policy="none",
        )
        session.add(pool)
        split_txn = _seed_outflow_transaction(
            session,
            identity="synthetic-split-mixed-basket",
            description="SYNTHETIC MIXED BASKET",
            amount=Decimal("-120.00"),
            row_number=1,
        )
        fallback_txn = _seed_outflow_transaction(
            session,
            identity="synthetic-unsplit-utility",
            description="SYNTHETIC UTILITY",
            amount=Decimal("-50.00"),
            row_number=2,
        )
        session.flush()
        session.add(
            DecisionEvent(
                target_type="canonical_transaction",
                target_id=fallback_txn.id,
                decision_type="category_change",
                field_name="category",
                proposed_value="utilities",
                approved_value="utilities",
                actor="owner",
                suggestion_source="owner",
            )
        )
        session.commit()
        return {
            "transaction_id": split_txn.id,
            "fallback_transaction_id": fallback_txn.id,
            "groceries_id": groceries.id,
            "household_id": household.id,
            "utilities_id": utilities.id,
            "pool_id": pool.id,
        }


def test_balanced_split_save_replaces_prior_lines_and_records_decision(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        fixture = _seed_split_fixture(tmp_path)
        first = client.put(
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={
                "actor": "owner",
                "actor_context": {
                    "actor_key": "owner",
                    "actor_type": "human",
                    "display_name": "Owner",
                    "persona_key": "finance_manager",
                    "group_keys": ["finance_manager"],
                    "source": "local_selector",
                },
                "note": "Split synthetic mixed basket.",
                "lines": [
                    {
                        "amount": "-80.00",
                        "category_id": fixture["groceries_id"],
                        "fund_pool_id": fixture["pool_id"],
                        "memo": "SYNTHETIC groceries",
                    },
                    {
                        "amount": "-40.00",
                        "category_id": fixture["household_id"],
                        "memo": "SYNTHETIC household",
                    },
                ],
            },
        )
        second = client.put(
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={
                "actor": "owner",
                "note": "Replace synthetic split.",
                "lines": [
                    {"amount": "-120.00", "category_id": fixture["household_id"], "memo": "SYNTHETIC replacement"},
                ],
            },
        )
        listed = client.get(f"/api/transactions/{fixture['transaction_id']}/allocations")

    assert first.status_code == 200
    assert [line["line_number"] for line in first.json()["allocations"]] == [1, 2]
    assert second.status_code == 200
    assert listed.json()["summary"]["allocation_count"] == 1
    assert listed.json()["summary"]["remainder"] == "0.00"
    assert listed.json()["allocations"][0]["category_id"] == fixture["household_id"]

    Session = _session_factory(tmp_path)
    with Session() as session:
        active = session.scalars(
            select(TransactionAllocation).where(
                TransactionAllocation.canonical_transaction_id == fixture["transaction_id"],
                TransactionAllocation.status == "active",
            )
        ).all()
        superseded = session.scalars(
            select(TransactionAllocation).where(
                TransactionAllocation.canonical_transaction_id == fixture["transaction_id"],
                TransactionAllocation.status == "superseded",
            )
        ).all()
        events = session.scalars(
            select(DecisionEvent)
            .where(DecisionEvent.target_type == "canonical_transaction", DecisionEvent.target_id == fixture["transaction_id"])
            .order_by(DecisionEvent.created_at, DecisionEvent.id)
        ).all()
    assert len(active) == 1
    assert len(superseded) == 2
    assert [event.decision_type for event in events] == ["transaction_split_replace", "transaction_split_replace"]
    assert events[0].actor_context_json is not None
    assert "SYNTHETIC groceries" in (events[0].approved_value or "")
    assert active[0].decision_event_id == events[-1].id


def test_split_validation_rejects_unbalanced_empty_zero_and_bad_references(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        fixture = _seed_split_fixture(tmp_path)
        unbalanced = client.put(
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={
                "actor": "owner",
                "lines": [{"amount": "-119.99", "category_id": fixture["groceries_id"]}],
            },
        )
        empty = client.put(
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={"actor": "owner", "lines": []},
        )
        zero = client.put(
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={
                "actor": "owner",
                "lines": [{"amount": "0.00", "category_id": fixture["groceries_id"]}],
            },
        )
        bad_category = client.put(
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={"actor": "owner", "lines": [{"amount": "-120.00", "category_id": "missing-category"}]},
        )
        missing_transaction = client.get("/api/transactions/missing/allocations")

    assert unbalanced.status_code == 422
    assert unbalanced.json()["detail"]["code"] == "allocation_total_mismatch"
    assert empty.status_code == 422
    assert empty.json()["detail"]["code"] == "allocation_lines_required"
    assert zero.status_code == 422
    assert zero.json()["detail"]["code"] == "allocation_amount_invalid"
    assert bad_category.status_code == 422
    assert bad_category.json()["detail"]["code"] == "allocation_category_invalid"
    assert missing_transaction.status_code == 404
    assert missing_transaction.json()["detail"]["code"] == "transaction_not_found"


def test_delete_split_voids_active_lines_and_records_decision(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        fixture = _seed_split_fixture(tmp_path)
        created = client.put(
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={
                "actor": "owner",
                "lines": [{"amount": "-120.00", "category_id": fixture["groceries_id"]}],
            },
        )
        deleted = client.request(
            "DELETE",
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={"actor": "owner", "note": "Remove synthetic split."},
        )
        listed = client.get(f"/api/transactions/{fixture['transaction_id']}/allocations")

    assert created.status_code == 200
    assert deleted.status_code == 200
    assert deleted.json()["summary"]["allocation_count"] == 0
    assert listed.json()["allocations"] == []

    Session = _session_factory(tmp_path)
    with Session() as session:
        statuses = session.scalars(select(TransactionAllocation.status)).all()
        event_types = session.scalars(select(DecisionEvent.decision_type).order_by(DecisionEvent.created_at, DecisionEvent.id)).all()
    assert statuses == ["voided"]
    assert event_types[-1] == "transaction_split_delete"


def test_reporting_prefers_balanced_splits_and_preserves_unsplit_category_rollup(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        fixture = _seed_split_fixture(tmp_path)
        saved = client.put(
            f"/api/transactions/{fixture['transaction_id']}/allocations",
            json={
                "actor": "owner",
                "lines": [
                    {"amount": "-80.00", "category_id": fixture["groceries_id"]},
                    {"amount": "-40.00", "category_id": fixture["household_id"]},
                ],
            },
        )

    assert saved.status_code == 200
    Session = _session_factory(tmp_path)
    with Session() as session:
        category_summary = _category_spending_summary(session)
        reviewed_rows = _reviewed_transaction_rows(session)

    assert category_summary["categories"] == [
        {"category": "Groceries", "outflow": "80.00"},
        {"category": "Household", "outflow": "40.00"},
        {"category": "Utilities", "outflow": "50.00"},
    ]
    split_rows = [row for row in reviewed_rows if row["id"] == fixture["transaction_id"]]
    assert [row["allocation_line_number"] for row in split_rows] == [1, 2]
    assert [row["amount"] for row in split_rows] == ["-80.00", "-40.00"]
    unsplit_rows = [row for row in reviewed_rows if row["id"] == fixture["fallback_transaction_id"]]
    assert len(unsplit_rows) == 1
    assert unsplit_rows[0]["category_current"] == "Utilities"


def test_receipt_promotion_stub_requires_explicit_confirmation(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        fixture = _seed_split_fixture(tmp_path)
        response = client.post(
            f"/api/transactions/{fixture['transaction_id']}/allocations/from-receipt",
            json={"actor": "owner", "receipt_id": "receipt-missing", "confirm": False},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "receipt_promotion_confirmation_required"
