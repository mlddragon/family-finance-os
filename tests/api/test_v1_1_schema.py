from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from family_finance_os.database import create_sqlite_engine, upgrade_database


FINANCE_TABLES = {
    "fund_pools",
    "pool_category_links",
    "monthly_pool_commitments",
    "financial_goals",
    "budget_targets",
    "transaction_allocations",
    "net_worth_snapshots",
    "receipts",
    "receipt_line_items",
    "manual_obligations",
    "spendable_balance_snapshots",
}

AUTH_TABLES = {
    "users",
    "user_sessions",
    "totp_secrets",
    "recovery_codes",
}

TIMESTAMP_COLUMNS = {"id", "created_at", "updated_at"}


def _upgrade_fresh_database(tmp_path):
    database_path = tmp_path / "database" / "family_finance_os.sqlite3"
    upgrade_database(database_path)
    return create_sqlite_engine(database_path)


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _unique_columns(inspector, table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(table_name)
    }


def _index_columns(inspector, table_name: str) -> set[tuple[str, ...]]:
    return {tuple(index["column_names"]) for index in inspector.get_indexes(table_name)}


def _foreign_key_targets(inspector, table_name: str) -> set[tuple[tuple[str, ...], str, tuple[str, ...]]]:
    return {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
        )
        for foreign_key in inspector.get_foreign_keys(table_name)
    }


def test_v1_1_migrations_apply_all_planning_and_auth_tables_on_fresh_database(tmp_path):
    engine = _upgrade_fresh_database(tmp_path)
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())

    assert FINANCE_TABLES.issubset(table_names)
    assert AUTH_TABLES.issubset(table_names)
    for table_name in FINANCE_TABLES | AUTH_TABLES:
        assert TIMESTAMP_COLUMNS.issubset(_column_names(inspector, table_name))


def test_v1_1_finance_tables_expose_key_constraints_and_indexes(tmp_path):
    engine = _upgrade_fresh_database(tmp_path)
    inspector = inspect(engine)

    assert ("pool_key",) in _unique_columns(inspector, "fund_pools")
    assert ("status", "sort_order") in _index_columns(inspector, "fund_pools")
    assert ("fund_pool_id", "category_id", "subcategory_key") in _unique_columns(
        inspector,
        "pool_category_links",
    )
    assert ("goal_key",) in _unique_columns(inspector, "financial_goals")
    assert ("status", "goal_type") in _index_columns(inspector, "financial_goals")
    assert ("target_key",) in _unique_columns(inspector, "budget_targets")
    assert ("allocation_group_id", "line_number") in _unique_columns(
        inspector,
        "transaction_allocations",
    )
    assert ("receipt_id", "line_number") in _unique_columns(inspector, "receipt_line_items")
    assert ("obligation_key",) in _unique_columns(inspector, "manual_obligations")
    assert ("month", "snapshot_type") in _index_columns(
        inspector,
        "spendable_balance_snapshots",
    )


def test_v1_1_auth_tables_expose_secret_safe_constraints(tmp_path):
    engine = _upgrade_fresh_database(tmp_path)
    inspector = inspect(engine)

    assert ("username",) in _unique_columns(inspector, "users")
    assert ("status", "role") in _index_columns(inspector, "users")
    assert ("session_token_hash",) in _unique_columns(inspector, "user_sessions")
    assert ("user_id", "revoked_at", "absolute_expires_at") in _index_columns(
        inspector,
        "user_sessions",
    )
    assert ("user_id", "disabled_at") in _index_columns(inspector, "totp_secrets")
    assert ("code_hash",) in _unique_columns(inspector, "recovery_codes")

    assert "session_token_hash" in _column_names(inspector, "user_sessions")
    assert "code_hash" in _column_names(inspector, "recovery_codes")
    assert "secret_ciphertext" in _column_names(inspector, "totp_secrets")
    assert "session_token" not in _column_names(inspector, "user_sessions")
    assert "code_plaintext" not in _column_names(inspector, "recovery_codes")
    assert "secret_plaintext" not in _column_names(inspector, "totp_secrets")


def test_v1_1_user_attribution_columns_are_foreign_keys_after_auth_migration(tmp_path):
    engine = _upgrade_fresh_database(tmp_path)
    inspector = inspect(engine)

    assert ((("created_by_user_id",), "users", ("id",))) in _foreign_key_targets(
        inspector,
        "fund_pools",
    )
    assert ((("updated_by_user_id",), "users", ("id",))) in _foreign_key_targets(
        inspector,
        "fund_pools",
    )
    assert ((("created_by_user_id",), "users", ("id",))) in _foreign_key_targets(
        inspector,
        "financial_goals",
    )
    assert ((("created_by_user_id",), "users", ("id",))) in _foreign_key_targets(
        inspector,
        "spendable_balance_snapshots",
    )


def test_v1_1_financial_goal_name_rejects_null_and_blank_values(tmp_path):
    engine = _upgrade_fresh_database(tmp_path)

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO financial_goals (
                        id, created_at, updated_at, goal_key, name, goal_type,
                        target_amount, reserved_balance, status
                    )
                    VALUES (
                        'goal-null-name', '2026-01-01T00:00:00+00:00',
                        '2026-01-01T00:00:00+00:00', 'goal_null_name', NULL,
                        'sinking_fund', 100, 0, 'active'
                    )
                    """,
                ),
            )

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO financial_goals (
                        id, created_at, updated_at, goal_key, name, goal_type,
                        target_amount, reserved_balance, status
                    )
                    VALUES (
                        'goal-blank-name', '2026-01-01T00:00:00+00:00',
                        '2026-01-01T00:00:00+00:00', 'goal_blank_name', '   ',
                        'sinking_fund', 100, 0, 'active'
                    )
                    """,
                ),
            )


def test_v1_1_unique_pool_key_is_enforced(tmp_path):
    engine = _upgrade_fresh_database(tmp_path)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO fund_pools (
                    id, created_at, updated_at, pool_key, name, status,
                    sort_order, rollover_policy
                )
                VALUES (
                    'pool-1', '2026-01-01T00:00:00+00:00',
                    '2026-01-01T00:00:00+00:00', 'household_pool',
                    'Household Pool', 'active', 10, 'none'
                )
                """,
            ),
        )

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO fund_pools (
                        id, created_at, updated_at, pool_key, name, status,
                        sort_order, rollover_policy
                    )
                    VALUES (
                        'pool-2', '2026-01-01T00:00:00+00:00',
                        '2026-01-01T00:00:00+00:00', 'household_pool',
                        'Duplicate Household Pool', 'active', 20, 'none'
                    )
                    """,
                ),
            )
