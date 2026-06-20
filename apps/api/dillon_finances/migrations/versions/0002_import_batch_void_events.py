from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_import_batch_void_events"
down_revision = "0001_create_audit_core"
branch_labels = None
depends_on = None


def _id_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
    ]


def upgrade() -> None:
    op.add_column(
        "source_files",
        sa.Column("storage_status", sa.String(length=40), nullable=False, server_default="present"),
    )
    op.add_column("source_files", sa.Column("destroyed_at", sa.String(length=40)))
    op.add_column("source_files", sa.Column("destroyed_by", sa.String(length=120)))
    op.add_column("source_files", sa.Column("destroyed_reason", sa.Text()))

    op.create_table(
        "import_batch_events",
        *_id_columns(),
        sa.Column("import_batch_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
    )


def downgrade() -> None:
    op.drop_table("import_batch_events")
    op.drop_column("source_files", "destroyed_reason")
    op.drop_column("source_files", "destroyed_by")
    op.drop_column("source_files", "destroyed_at")
    op.drop_column("source_files", "storage_status")
