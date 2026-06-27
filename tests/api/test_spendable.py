from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from family_finance_os.database import create_sqlite_engine
from family_finance_os.main import create_app
from family_finance_os.models import (
    CanonicalTransaction,
    FinancialGoal,
    ImportBatch,
    ImportedRow,
    ManualObligation,
    Setting,
    Source,
    SourceAccount,
    SourceFile,
    SpendableBalanceSnapshot,
)


def _seed_source_row(
    session,
    *,
    source_key: str,
    display_name: str,
    account_type: str,
    posted_date: str,
    amount: Decimal,
    direction: str,
    balance: Decimal | None,
    row_number: int,
) -> None:
    source = Source(
        source_key=source_key,
        display_name=display_name,
        source_type=account_type,
    )
    account = SourceAccount(
        source=source,
        account_key=f"{source_key}_primary",
        display_name=f"{display_name} Primary",
        account_type=account_type,
    )
    batch = ImportBatch(
        source=source,
        source_account=account,
        status="accepted",
        parser_version="synthetic-v1",
        validation_status="passed",
        row_count=1,
        transaction_date_min=posted_date,
        transaction_date_max=posted_date,
    )
    source_file = SourceFile(
        source=source,
        source_account=account,
        import_batch=batch,
        original_filename=f"SYNTHETIC_{source_key}.csv",
        stored_path=f"/data/raw/SYNTHETIC_{source_key}.csv",
        file_sha256=str(row_number) * 64,
        byte_size=128,
        validation_status="passed",
        row_count=1,
        parser_version="synthetic-v1",
    )
    canonical = CanonicalTransaction(
        canonical_identity=f"synthetic-{source_key}-{row_number}",
        source_account=account,
        posted_date=posted_date,
        amount=amount,
        description_fingerprint=f"synthetic-{source_key}",
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
            imported_row_identity=f"synthetic-imported-{source_key}-{row_number}",
            posted_date=posted_date,
            raw_description=f"SYNTHETIC {display_name}",
            amount=amount,
            direction=direction,
            balance=balance,
            parser_version="synthetic-v1",
        )
    )


def _seed_spendable_fixture(data_root) -> None:
    engine = create_sqlite_engine(data_root / "database" / "family_finance_os.sqlite3")
    Session = sessionmaker(bind=engine)
    with Session() as session:
        _seed_source_row(
            session,
            source_key="alliant_checking",
            display_name="Alliant Checking",
            account_type="checking",
            posted_date="2026-06-24",
            amount=Decimal("-12.00"),
            direction="debit",
            balance=Decimal("4380.00"),
            row_number=1,
        )
        _seed_source_row(
            session,
            source_key="alliant_savings",
            display_name="Alliant Savings",
            account_type="savings",
            posted_date="2026-06-23",
            amount=Decimal("25.00"),
            direction="credit",
            balance=Decimal("1800.00"),
            row_number=2,
        )
        _seed_source_row(
            session,
            source_key="alliant_credit_card",
            display_name="Synthetic Rewards Card",
            account_type="credit_card",
            posted_date="2026-06-22",
            amount=Decimal("-40.00"),
            direction="debit",
            balance=Decimal("-1018.23"),
            row_number=3,
        )
        _seed_source_row(
            session,
            source_key="chase_prime_visa",
            display_name="Synthetic Travel Card",
            account_type="credit_card",
            posted_date="2026-06-20",
            amount=Decimal("-60.00"),
            direction="debit",
            balance=Decimal("-505.00"),
            row_number=4,
        )
        for source_key in (
            "alliant_checking",
            "alliant_savings",
            "alliant_credit_card",
            "chase_prime_visa",
        ):
            setting = session.scalar(
                select(Setting).where(
                    Setting.domain == "sources",
                    Setting.setting_key == f"sources.{source_key}.profile_confirmation_status",
                )
            )
            assert setting is not None
            setting.value_json = '"owner_confirmed_header_sample"'

        session.add_all(
            [
                FinancialGoal(
                    goal_key="synthetic-emergency",
                    name="SYNTHETIC Emergency",
                    goal_type="emergency",
                    target_amount=Decimal("3000.00"),
                    reserved_balance=Decimal("1900.00"),
                    status="active",
                ),
                ManualObligation(
                    obligation_key="synthetic-rent",
                    name="SYNTHETIC Rent",
                    amount=Decimal("867.42"),
                    due_date="2026-06-28",
                    month="2026-06",
                    status="active",
                    obligation_type="bill",
                ),
            ]
        )
        session.commit()


def test_spendable_api_returns_d1_formula_and_card_obligations(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _seed_spendable_fixture(tmp_path)
        response = client.get("/api/spendable?month=2026-06")

    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2026-06"
    assert body["verified_liquid_cash"] == "6180.00"
    assert body["reserved_goal_balance"] == "1900.00"
    assert body["manual_obligations_total"] == "867.42"
    assert body["provisional_exposure"] == "112.00"
    assert body["include_provisional"] is False
    assert body["headline_spendable"] == "3412.58"
    assert body["card_obligation_total"] == "1523.23"
    assert [item["owed"] for item in body["card_obligation_items"]] == ["1018.23", "505.00"]
    assert body["snapshot_id"] is None


def test_spendable_include_provisional_reduces_headline(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _seed_spendable_fixture(tmp_path)
        response = client.get("/api/spendable?month=2026-06&include_provisional=true")

    assert response.status_code == 200
    body = response.json()
    assert body["include_provisional"] is True
    assert body["headline_spendable"] == "3300.58"


def test_spendable_snapshot_is_persisted_only_when_requested(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _seed_spendable_fixture(tmp_path)
        response = client.get(
            "/api/spendable?month=2026-06&persist_snapshot=true&snapshot_type=draft_close"
        )

    assert response.status_code == 200
    snapshot_id = response.json()["snapshot_id"]
    assert snapshot_id

    engine = create_sqlite_engine(tmp_path / "database" / "family_finance_os.sqlite3")
    Session = sessionmaker(bind=engine)
    with Session() as session:
        snapshot = session.scalar(
            select(SpendableBalanceSnapshot).where(SpendableBalanceSnapshot.id == snapshot_id)
        )

    assert snapshot is not None
    assert snapshot.month == "2026-06"
    assert snapshot.snapshot_type == "draft_close"
    assert snapshot.headline_spendable == Decimal("3412.58")
    assert snapshot.card_obligation == Decimal("1523.23")


def test_operator_summary_includes_spendable_and_next_action(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        _seed_spendable_fixture(tmp_path)
        response = client.get("/api/operator-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["spendable"]["headline_spendable"] == "3412.58"
    assert body["spendable"]["card_obligation_total"] == "1523.23"
    assert body["spendable"]["warnings"] == []
    assert body["next_action"]["code"] == "review_ledger_decisions"


def test_invalid_spendable_month_returns_stable_error(tmp_path):
    app = create_app(data_root=tmp_path, local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.get("/api/spendable?month=202606")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_month"
