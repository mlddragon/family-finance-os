from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_create_audit_core"
down_revision = None
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
        "sources",
        *_id_columns(),
        sa.Column("source_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("source_key"),
    )
    op.create_table(
        "source_accounts",
        *_id_columns(),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("account_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("account_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.UniqueConstraint("source_id", "account_key"),
    )
    op.create_table(
        "import_batches",
        *_id_columns(),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("source_account_id", sa.String(length=36)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("parser_version", sa.String(length=80)),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("transaction_date_min", sa.String(length=10)),
        sa.Column("transaction_date_max", sa.String(length=10)),
        sa.Column("supersedes_import_batch_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.ForeignKeyConstraint(["source_account_id"], ["source_accounts.id"]),
        sa.ForeignKeyConstraint(["supersedes_import_batch_id"], ["import_batches.id"]),
    )
    op.create_table(
        "source_files",
        *_id_columns(),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("source_account_id", sa.String(length=36)),
        sa.Column("import_batch_id", sa.String(length=36)),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("parser_version", sa.String(length=80)),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.ForeignKeyConstraint(["source_account_id"], ["source_accounts.id"]),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
    )
    op.create_table(
        "canonical_transactions",
        *_id_columns(),
        sa.Column("canonical_identity", sa.String(length=200), nullable=False),
        sa.Column("source_account_id", sa.String(length=36), nullable=False),
        sa.Column("posted_date", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("description_fingerprint", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["source_account_id"], ["source_accounts.id"]),
        sa.UniqueConstraint("canonical_identity"),
    )
    op.create_table(
        "imported_rows",
        *_id_columns(),
        sa.Column("import_batch_id", sa.String(length=36), nullable=False),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("source_account_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_transaction_id", sa.String(length=36)),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("imported_row_hash", sa.String(length=64), nullable=False),
        sa.Column("imported_row_identity", sa.String(length=200), nullable=False),
        sa.Column("posted_date", sa.String(length=10), nullable=False),
        sa.Column("effective_date", sa.String(length=10)),
        sa.Column("raw_description", sa.Text(), nullable=False),
        sa.Column("normalized_merchant", sa.String(length=255)),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("balance", sa.Numeric(14, 2)),
        sa.Column("initial_category", sa.String(length=120)),
        sa.Column("initial_subcategory", sa.String(length=120)),
        sa.Column("initial_review_flags_json", sa.Text()),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"]),
        sa.ForeignKeyConstraint(["source_account_id"], ["source_accounts.id"]),
        sa.ForeignKeyConstraint(["canonical_transaction_id"], ["canonical_transactions.id"]),
        sa.UniqueConstraint("imported_row_identity"),
    )
    op.create_table(
        "validation_findings",
        *_id_columns(),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=36)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("resolution_event_id", sa.String(length=36)),
    )
    op.create_table(
        "settings",
        *_id_columns(),
        sa.Column("domain", sa.String(length=120), nullable=False),
        sa.Column("setting_key", sa.String(length=200), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("domain", "setting_key"),
    )
    op.create_table(
        "settings_events",
        *_id_columns(),
        sa.Column("setting_id", sa.String(length=36)),
        sa.Column("domain", sa.String(length=120), nullable=False),
        sa.Column("setting_key", sa.String(length=200), nullable=False),
        sa.Column("previous_value_json", sa.Text()),
        sa.Column("new_value_json", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("validation_result_json", sa.Text()),
        sa.Column("supersedes_event_id", sa.String(length=36)),
        sa.Column("reverts_event_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["setting_id"], ["settings.id"]),
        sa.ForeignKeyConstraint(["supersedes_event_id"], ["settings_events.id"]),
        sa.ForeignKeyConstraint(["reverts_event_id"], ["settings_events.id"]),
    )
    op.create_table(
        "decision_events",
        *_id_columns(),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("decision_type", sa.String(length=80), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("previous_value", sa.Text()),
        sa.Column("proposed_value", sa.Text()),
        sa.Column("approved_value", sa.Text()),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("suggestion_source", sa.String(length=80), nullable=False),
        sa.Column("supersedes_event_id", sa.String(length=36)),
        sa.Column("reverts_event_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["supersedes_event_id"], ["decision_events.id"]),
        sa.ForeignKeyConstraint(["reverts_event_id"], ["decision_events.id"]),
    )
    op.create_table(
        "jobs",
        *_id_columns(),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("started_at", sa.String(length=40), nullable=False),
        sa.Column("finished_at", sa.String(length=40)),
        sa.Column("input_json", sa.Text()),
        sa.Column("output_json", sa.Text()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("logs_path", sa.Text()),
        sa.Column("root_job_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["root_job_id"], ["jobs.id"]),
    )
    op.create_table(
        "report_runs",
        *_id_columns(),
        sa.Column("report_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("job_id", sa.String(length=36)),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("input_snapshot_json", sa.Text()),
        sa.Column("output_summary_json", sa.Text()),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
    )
    op.create_table(
        "artifacts",
        *_id_columns(),
        sa.Column("artifact_type", sa.String(length=120), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255)),
        sa.Column("description", sa.Text()),
        sa.Column("producing_job_id", sa.String(length=36)),
        sa.Column("source_inputs_json", sa.Text()),
        sa.Column("retention_category", sa.String(length=80)),
        sa.Column("sensitivity", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["producing_job_id"], ["jobs.id"]),
    )
    op.create_table(
        "monthly_closes",
        *_id_columns(),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("validation_summary", sa.Text()),
        sa.Column("source_import_batch_ids_json", sa.Text()),
        sa.Column("report_run_ids_json", sa.Text()),
        sa.Column("settings_snapshot_artifact_id", sa.String(length=36)),
        sa.Column("decision_export_artifact_id", sa.String(length=36)),
        sa.Column("artifact_folder_path", sa.Text(), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("month", "status"),
    )


def downgrade() -> None:
    for table_name in (
        "monthly_closes",
        "artifacts",
        "report_runs",
        "jobs",
        "decision_events",
        "settings_events",
        "settings",
        "validation_findings",
        "imported_rows",
        "canonical_transactions",
        "source_files",
        "import_batches",
        "source_accounts",
        "sources",
    ):
        op.drop_table(table_name)
