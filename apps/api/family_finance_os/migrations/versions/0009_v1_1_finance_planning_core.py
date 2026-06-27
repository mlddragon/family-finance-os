from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_v1_1_finance_planning_core"
down_revision = "0008_suggestions_approvals"
branch_labels = None
depends_on = None


def _id_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "fund_pools",
        *_id_columns(),
        sa.Column("pool_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("rollover_policy", sa.String(length=40), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36)),
        sa.Column("updated_by_user_id", sa.String(length=36)),
        sa.UniqueConstraint("pool_key"),
    )
    op.create_index(
        "ix_fund_pools_status_sort",
        "fund_pools",
        ["status", "sort_order"],
    )

    op.create_table(
        "pool_category_links",
        *_id_columns(),
        sa.Column("fund_pool_id", sa.String(length=36), nullable=False),
        sa.Column("category_id", sa.String(length=36), nullable=False),
        sa.Column("subcategory_key", sa.String(length=120)),
        sa.Column("link_type", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["fund_pool_id"], ["fund_pools.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.UniqueConstraint("fund_pool_id", "category_id", "subcategory_key"),
    )
    op.create_index(
        "ix_pool_category_links_category_active",
        "pool_category_links",
        ["category_id", "active"],
    )
    op.create_index(
        "ix_pool_category_links_pool_active",
        "pool_category_links",
        ["fund_pool_id", "active"],
    )

    op.create_table(
        "monthly_pool_commitments",
        *_id_columns(),
        sa.Column("fund_pool_id", sa.String(length=36), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("committed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("funding_source", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("decision_event_id", sa.String(length=36)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["fund_pool_id"], ["fund_pools.id"]),
        sa.ForeignKeyConstraint(["decision_event_id"], ["decision_events.id"]),
        sa.UniqueConstraint("fund_pool_id", "month", "status"),
    )
    op.create_index(
        "ix_monthly_pool_commitments_month_status",
        "monthly_pool_commitments",
        ["month", "status"],
    )

    op.create_table(
        "financial_goals",
        *_id_columns(),
        sa.Column("goal_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("goal_type", sa.String(length=40), nullable=False),
        sa.Column("target_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("target_date", sa.String(length=10)),
        sa.Column("linked_fund_pool_id", sa.String(length=36)),
        sa.Column("reserved_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", sa.String(length=36)),
        sa.Column("updated_by_user_id", sa.String(length=36)),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_financial_goals_name_required",
        ),
        sa.ForeignKeyConstraint(["linked_fund_pool_id"], ["fund_pools.id"]),
        sa.UniqueConstraint("goal_key"),
    )
    op.create_index(
        "ix_financial_goals_status_type",
        "financial_goals",
        ["status", "goal_type"],
    )
    op.create_index(
        "ix_financial_goals_pool_status",
        "financial_goals",
        ["linked_fund_pool_id", "status"],
    )

    op.create_table(
        "budget_targets",
        *_id_columns(),
        sa.Column("target_key", sa.String(length=120), nullable=False),
        sa.Column("month", sa.String(length=7)),
        sa.Column("target_scope", sa.String(length=40), nullable=False),
        sa.Column("category_id", sa.String(length=36)),
        sa.Column("fund_pool_id", sa.String(length=36)),
        sa.Column("financial_goal_id", sa.String(length=36)),
        sa.Column("target_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("warning_threshold_amount", sa.Numeric(14, 2)),
        sa.Column("hard_cap_amount", sa.Numeric(14, 2)),
        sa.Column("review_threshold_amount", sa.Numeric(14, 2)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("decision_event_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["fund_pool_id"], ["fund_pools.id"]),
        sa.ForeignKeyConstraint(["financial_goal_id"], ["financial_goals.id"]),
        sa.ForeignKeyConstraint(["decision_event_id"], ["decision_events.id"]),
        sa.UniqueConstraint("target_key"),
    )
    op.create_index(
        "ix_budget_targets_month_scope_status",
        "budget_targets",
        ["month", "target_scope", "status"],
    )
    op.create_index(
        "ix_budget_targets_category_month",
        "budget_targets",
        ["category_id", "month"],
    )
    op.create_index(
        "ix_budget_targets_pool_month",
        "budget_targets",
        ["fund_pool_id", "month"],
    )

    op.create_table(
        "transaction_allocations",
        *_id_columns(),
        sa.Column("canonical_transaction_id", sa.String(length=36), nullable=False),
        sa.Column("allocation_group_id", sa.String(length=36), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("category_id", sa.String(length=36), nullable=False),
        sa.Column("subcategory", sa.String(length=120)),
        sa.Column("fund_pool_id", sa.String(length=36)),
        sa.Column("financial_goal_id", sa.String(length=36)),
        sa.Column("memo", sa.Text()),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("decision_event_id", sa.String(length=36)),
        sa.Column("created_by_user_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["canonical_transaction_id"], ["canonical_transactions.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["fund_pool_id"], ["fund_pools.id"]),
        sa.ForeignKeyConstraint(["financial_goal_id"], ["financial_goals.id"]),
        sa.ForeignKeyConstraint(["decision_event_id"], ["decision_events.id"]),
        sa.UniqueConstraint("allocation_group_id", "line_number"),
    )
    op.create_index(
        "ix_transaction_allocations_txn_status",
        "transaction_allocations",
        ["canonical_transaction_id", "status"],
    )
    op.create_index(
        "ix_transaction_allocations_pool_status",
        "transaction_allocations",
        ["fund_pool_id", "status"],
    )
    op.create_index(
        "ix_transaction_allocations_category_status",
        "transaction_allocations",
        ["category_id", "status"],
    )

    op.create_table(
        "net_worth_snapshots",
        *_id_columns(),
        sa.Column("snapshot_date", sa.String(length=10), nullable=False),
        sa.Column("asset_or_liability", sa.String(length=20), nullable=False),
        sa.Column("account_name", sa.String(length=160), nullable=False),
        sa.Column("institution", sa.String(length=160)),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("subcategory", sa.String(length=120)),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("valuation_method", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.String(length=40), nullable=False),
        sa.Column("source_notes", sa.Text()),
        sa.Column("include_in_actual_net_worth", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36)),
    )
    op.create_index(
        "ix_net_worth_snapshots_date_method",
        "net_worth_snapshots",
        ["snapshot_date", "valuation_method"],
    )
    op.create_index(
        "ix_net_worth_snapshots_category_date",
        "net_worth_snapshots",
        ["category", "snapshot_date"],
    )

    op.create_table(
        "receipts",
        *_id_columns(),
        sa.Column("canonical_transaction_id", sa.String(length=36)),
        sa.Column("merchant_name", sa.String(length=255), nullable=False),
        sa.Column("purchase_date", sa.String(length=10), nullable=False),
        sa.Column("receipt_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_file_id", sa.String(length=36)),
        sa.Column("stored_artifact_path", sa.Text()),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("applied_as_split_decision_event_id", sa.String(length=36)),
        sa.Column("created_by_user_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["canonical_transaction_id"], ["canonical_transactions.id"]),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"]),
        sa.ForeignKeyConstraint(["applied_as_split_decision_event_id"], ["decision_events.id"]),
    )
    op.create_index(
        "ix_receipts_transaction_status",
        "receipts",
        ["canonical_transaction_id", "status"],
    )
    op.create_index("ix_receipts_purchase_date", "receipts", ["purchase_date"])
    op.create_index(
        "ix_receipts_source_type_status",
        "receipts",
        ["source_type", "status"],
    )

    op.create_table(
        "receipt_line_items",
        *_id_columns(),
        sa.Column("receipt_id", sa.String(length=36), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4)),
        sa.Column("unit_price", sa.Numeric(14, 2)),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("category_id", sa.String(length=36)),
        sa.Column("subcategory", sa.String(length=120)),
        sa.Column("fund_pool_id", sa.String(length=36)),
        sa.Column("tax_relevant_candidate", sa.Boolean(), nullable=False),
        sa.Column("reimbursement_candidate", sa.Boolean(), nullable=False),
        sa.Column("business_candidate", sa.Boolean(), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.Text()),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["fund_pool_id"], ["fund_pools.id"]),
        sa.UniqueConstraint("receipt_id", "line_number"),
    )
    op.create_index(
        "ix_receipt_line_items_receipt",
        "receipt_line_items",
        ["receipt_id"],
    )
    op.create_index(
        "ix_receipt_line_items_category_review",
        "receipt_line_items",
        ["category_id", "review_status"],
    )

    op.create_table(
        "manual_obligations",
        *_id_columns(),
        sa.Column("obligation_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.String(length=10)),
        sa.Column("month", sa.String(length=7)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("obligation_type", sa.String(length=40), nullable=False),
        sa.Column("linked_canonical_transaction_id", sa.String(length=36)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["linked_canonical_transaction_id"], ["canonical_transactions.id"]),
        sa.UniqueConstraint("obligation_key"),
    )
    op.create_index(
        "ix_manual_obligations_month_status",
        "manual_obligations",
        ["month", "status"],
    )
    op.create_index(
        "ix_manual_obligations_due_status",
        "manual_obligations",
        ["due_date", "status"],
    )

    op.create_table(
        "spendable_balance_snapshots",
        *_id_columns(),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("snapshot_type", sa.String(length=40), nullable=False),
        sa.Column("headline_spendable", sa.Numeric(14, 2), nullable=False),
        sa.Column("verified_liquid_cash", sa.Numeric(14, 2), nullable=False),
        sa.Column("reserved_goal_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("manual_obligations_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("provisional_exposure", sa.Numeric(14, 2), nullable=False),
        sa.Column("include_provisional", sa.Boolean(), nullable=False),
        sa.Column("card_obligation", sa.Numeric(14, 2), nullable=False),
        sa.Column("confidence", sa.String(length=40), nullable=False),
        sa.Column("input_summary_json", sa.Text(), nullable=False),
        sa.Column("monthly_close_id", sa.String(length=36)),
        sa.Column("created_by_user_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["monthly_close_id"], ["monthly_closes.id"]),
    )
    op.create_index(
        "ix_spendable_snapshots_month_type",
        "spendable_balance_snapshots",
        ["month", "snapshot_type"],
    )
    op.create_index(
        "ix_spendable_snapshots_close",
        "spendable_balance_snapshots",
        ["monthly_close_id"],
    )


def downgrade() -> None:
    op.drop_table("spendable_balance_snapshots")
    op.drop_table("manual_obligations")
    op.drop_table("receipt_line_items")
    op.drop_table("receipts")
    op.drop_table("net_worth_snapshots")
    op.drop_table("transaction_allocations")
    op.drop_table("budget_targets")
    op.drop_table("financial_goals")
    op.drop_table("monthly_pool_commitments")
    op.drop_table("pool_category_links")
    op.drop_table("fund_pools")
