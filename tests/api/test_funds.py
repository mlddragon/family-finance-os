from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from family_finance_os.database import create_sqlite_engine
from family_finance_os.main import create_app
from family_finance_os.models import (
    BudgetTarget,
    CanonicalTransaction,
    Category,
    DecisionEvent,
    FundPool,
    MonthlyPoolCommitment,
    TransactionAllocation,
)
from tests.api.test_spendable import _seed_spendable_fixture


def _session_factory(data_root):
    engine = create_sqlite_engine(data_root / "database" / "family_finance_os.sqlite3")
    return sessionmaker(bind=engine)


def _seed_funds_fixture(data_root) -> None:
    _seed_spendable_fixture(data_root)
    Session = _session_factory(data_root)
    with Session() as session:
        groceries = FundPool(
            pool_key="groceries",
            name="Groceries",
            status="active",
            sort_order=10,
            rollover_policy="none",
        )
        auto = FundPool(
            pool_key="auto_fuel",
            name="Auto & fuel",
            status="active",
            sort_order=20,
            rollover_policy="none",
        )
        session.add_all([groceries, auto])
        session.flush()
        session.add_all(
            [
                MonthlyPoolCommitment(
                    fund_pool_id=groceries.id,
                    month="2026-06",
                    committed_amount=Decimal("700.00"),
                    funding_source="monthly_income",
                    status="active",
                ),
                MonthlyPoolCommitment(
                    fund_pool_id=auto.id,
                    month="2026-06",
                    committed_amount=Decimal("300.00"),
                    funding_source="monthly_income",
                    status="active",
                ),
                BudgetTarget(
                    target_key="funding-2026-06",
                    month="2026-06",
                    target_scope="monthly_funding",
                    target_amount=Decimal("900.00"),
                    status="active",
                ),
            ]
        )
        groceries_category = session.scalar(select(Category).where(Category.category_key == "groceries"))
        auto_category = session.scalar(select(Category).where(Category.category_key == "transportation"))
        assert groceries_category is not None
        assert auto_category is not None
        grocery_txn = CanonicalTransaction(
            canonical_identity="synthetic-funds-grocery",
            source_account_id=session.scalar(select(CanonicalTransaction.source_account_id)),
            posted_date="2026-06-12",
            amount=Decimal("-512.40"),
            description_fingerprint="synthetic grocery",
            status="active",
        )
        auto_txn = CanonicalTransaction(
            canonical_identity="synthetic-funds-auto",
            source_account_id=grocery_txn.source_account_id,
            posted_date="2026-06-13",
            amount=Decimal("-341.10"),
            description_fingerprint="synthetic auto",
            status="active",
        )
        session.add_all([grocery_txn, auto_txn])
        session.flush()
        session.add_all(
            [
                TransactionAllocation(
                    canonical_transaction_id=grocery_txn.id,
                    allocation_group_id="synthetic-grocery-allocation",
                    line_number=1,
                    amount=Decimal("512.40"),
                    category_id=groceries_category.id,
                    fund_pool_id=groceries.id,
                    source="owner",
                    status="active",
                ),
                TransactionAllocation(
                    canonical_transaction_id=auto_txn.id,
                    allocation_group_id="synthetic-auto-allocation",
                    line_number=1,
                    amount=Decimal("341.10"),
                    category_id=auto_category.id,
                    fund_pool_id=auto.id,
                    source="owner",
                    status="active",
                ),
            ]
        )
        session.commit()


def test_funds_summary_returns_spendable_commitment_health_and_pool_remaining(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _seed_funds_fixture(tmp_path)
        response = client.get("/api/funds/summary?month=2026-06")

    assert response.status_code == 200
    body = response.json()
    assert body["spendable"]["headline"] == "3412.58"
    assert body["spendable"]["manual_upcoming_obligations"] == "867.42"
    assert body["spendable"]["includes_provisional"] is False
    assert body["spendable"]["card_obligation_items"][0]["note"] == "Pool remaining already reflects this"
    assert body["commitment_health"] == {
        "funded_this_month": "900.00",
        "fund_commitments": "1000.00",
        "pool_remaining_total": "146.50",
        "uncommitted": "-100.00",
        "overcommitted": True,
    }
    assert [(pool["name"], pool["pool_remaining"], pool["status"]) for pool in body["pools"]] == [
        ("Groceries", "187.60", "On track"),
        ("Auto & fuel", "-41.10", "Over by $41.10"),
    ]
    assert body["goals"][0]["remaining_to_target"] == "1100.00"


def test_fund_pool_crud_rejects_duplicate_active_names_and_records_decisions(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        created = client.post(
            "/api/fund-pools",
            json={"name": "Groceries", "actor": "owner", "note": "Create synthetic fund pool."},
        )
        duplicate = client.post(
            "/api/fund-pools",
            json={"name": " groceries ", "actor": "owner", "note": "Duplicate synthetic fund pool."},
        )
        pool_id = created.json()["pool"]["id"]
        patched = client.patch(
            f"/api/fund-pools/{pool_id}",
            json={"name": "Household groceries", "actor": "owner", "note": "Rename synthetic fund pool."},
        )

    assert created.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "fund_pool_name_exists"
    assert patched.status_code == 200
    assert patched.json()["pool"]["name"] == "Household groceries"

    Session = _session_factory(tmp_path)
    with Session() as session:
        events = session.scalars(select(DecisionEvent).where(DecisionEvent.target_type == "fund_pool")).all()
    assert [event.decision_type for event in events] == ["fund_pool_create", "fund_pool_update"]


def test_financial_goal_requires_name_and_valid_type(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        missing_name = client.post(
            "/api/financial-goals",
            json={
                "name": "   ",
                "goal_type": "purchase",
                "target_amount": "1200.00",
                "actor": "owner",
            },
        )
        invalid_type = client.post(
            "/api/financial-goals",
            json={
                "name": "Synthetic goal",
                "goal_type": "project",
                "target_amount": "1200.00",
                "actor": "owner",
            },
        )
        created = client.post(
            "/api/financial-goals",
            json={
                "name": "Vacation 2026",
                "goal_type": "purchase",
                "target_amount": "2000.00",
                "reserved_balance": "400.00",
                "actor": "owner",
                "note": "Create synthetic goal.",
            },
        )

    assert missing_name.status_code == 422
    assert missing_name.json()["detail"]["code"] == "goal_name_required"
    assert invalid_type.status_code == 422
    assert invalid_type.json()["detail"]["code"] == "invalid_goal_type"
    assert created.status_code == 200
    assert created.json()["goal"]["remaining_to_target"] == "1600.00"


def test_commitment_and_budget_target_routes_update_summary_and_decision_events(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        pool = client.post(
            "/api/fund-pools",
            json={"name": "Utilities", "actor": "owner", "note": "Create synthetic utility pool."},
        ).json()["pool"]
        commitment = client.post(
            "/api/fund-commitments",
            json={
                "fund_pool_id": pool["id"],
                "month": "2026-06",
                "committed_amount": "420.00",
                "actor": "owner",
                "note": "Commit synthetic utility funding.",
            },
        )
        updated = client.patch(
            f"/api/fund-commitments/{commitment.json()['commitment']['id']}",
            json={"committed_amount": "460.00", "actor": "owner", "note": "Adjust synthetic utility funding."},
        )
        target = client.post(
            "/api/budget-targets",
            json={
                "target_scope": "monthly_funding",
                "month": "2026-06",
                "target_amount": "500.00",
                "actor": "owner",
                "note": "Set synthetic monthly funding.",
            },
        )
        summary = client.get("/api/funds/summary?month=2026-06")

    assert commitment.status_code == 200
    assert updated.status_code == 200
    assert target.status_code == 200
    assert summary.json()["commitment_health"]["funded_this_month"] == "500.00"
    assert summary.json()["commitment_health"]["fund_commitments"] == "460.00"

    Session = _session_factory(tmp_path)
    with Session() as session:
        decision_types = [
            event.decision_type
            for event in session.scalars(select(DecisionEvent).order_by(DecisionEvent.created_at, DecisionEvent.id)).all()
        ]
    assert decision_types == [
        "fund_pool_create",
        "fund_commitment_create",
        "fund_commitment_update",
        "budget_target_create",
    ]
