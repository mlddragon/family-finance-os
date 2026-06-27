from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_v1_1_auth_core"
down_revision = "0009_v1_1_finance_planning_core"
branch_labels = None
depends_on = None


USER_ATTRIBUTION_FOREIGN_KEYS = {
    "fund_pools": ("created_by_user_id", "updated_by_user_id"),
    "pool_category_links": ("created_by_user_id",),
    "monthly_pool_commitments": ("created_by_user_id",),
    "financial_goals": ("created_by_user_id", "updated_by_user_id"),
    "transaction_allocations": ("created_by_user_id",),
    "net_worth_snapshots": ("created_by_user_id",),
    "receipts": ("created_by_user_id",),
    "manual_obligations": ("created_by_user_id",),
    "spendable_balance_snapshots": ("created_by_user_id",),
}


def _id_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
    ]


def _user_fk_name(table_name: str, column_name: str) -> str:
    return f"fk_{table_name}_{column_name}_users"


def _add_user_attribution_foreign_keys() -> None:
    for table_name, column_names in USER_ATTRIBUTION_FOREIGN_KEYS.items():
        with op.batch_alter_table(table_name) as batch_op:
            for column_name in column_names:
                batch_op.create_foreign_key(
                    _user_fk_name(table_name, column_name),
                    "users",
                    [column_name],
                    ["id"],
                )


def _drop_user_attribution_foreign_keys() -> None:
    for table_name, column_names in USER_ATTRIBUTION_FOREIGN_KEYS.items():
        with op.batch_alter_table(table_name) as batch_op:
            for column_name in column_names:
                batch_op.drop_constraint(
                    _user_fk_name(table_name, column_name),
                    type_="foreignkey",
                )


def upgrade() -> None:
    op.create_table(
        "users",
        *_id_columns(),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("passphrase_hash", sa.Text(), nullable=False),
        sa.Column("passphrase_updated_at", sa.String(length=40), nullable=False),
        sa.Column("totp_required", sa.Boolean(), nullable=False),
        sa.Column("recovery_required", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.String(length=40)),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.String(length=40)),
        sa.Column("invited_by_user_id", sa.String(length=36)),
        sa.Column("invitation_token_hash", sa.Text()),
        sa.Column("invitation_expires_at", sa.String(length=40)),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_status_role", "users", ["status", "role"])

    op.create_table(
        "user_sessions",
        *_id_columns(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("session_token_hash", sa.Text(), nullable=False),
        sa.Column("created_from", sa.String(length=40), nullable=False),
        sa.Column("last_seen_at", sa.String(length=40), nullable=False),
        sa.Column("idle_expires_at", sa.String(length=40), nullable=False),
        sa.Column("absolute_expires_at", sa.String(length=40), nullable=False),
        sa.Column("revoked_at", sa.String(length=40)),
        sa.Column("revoked_reason", sa.String(length=120)),
        sa.Column("user_agent_hash", sa.String(length=64)),
        sa.Column("client_host", sa.String(length=120)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("session_token_hash"),
    )
    op.create_index(
        "ix_user_sessions_user_active",
        "user_sessions",
        ["user_id", "revoked_at", "absolute_expires_at"],
    )
    op.create_index(
        "ix_user_sessions_idle_expiry",
        "user_sessions",
        ["idle_expires_at"],
    )

    op.create_table(
        "totp_secrets",
        *_id_columns(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("secret_version", sa.Integer(), nullable=False),
        sa.Column("confirmed_at", sa.String(length=40)),
        sa.Column("disabled_at", sa.String(length=40)),
        sa.Column("last_used_counter", sa.Integer()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_totp_secrets_user_active",
        "totp_secrets",
        ["user_id", "disabled_at"],
    )

    op.create_table(
        "recovery_codes",
        *_id_columns(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("code_label", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("used_at", sa.String(length=40)),
        sa.Column("used_session_id", sa.String(length=36)),
        sa.Column("rotated_at", sa.String(length=40)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["used_session_id"], ["user_sessions.id"]),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        "ix_recovery_codes_user_status",
        "recovery_codes",
        ["user_id", "status"],
    )

    _add_user_attribution_foreign_keys()


def downgrade() -> None:
    _drop_user_attribution_foreign_keys()
    op.drop_table("recovery_codes")
    op.drop_table("totp_secrets")
    op.drop_table("user_sessions")
    op.drop_table("users")
