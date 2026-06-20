from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_validation_finding_events"
down_revision = "0002_import_batch_void_events"
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
        "validation_finding_events",
        *_id_columns(),
        sa.Column("validation_finding_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.ForeignKeyConstraint(["validation_finding_id"], ["validation_findings.id"]),
    )


def downgrade() -> None:
    op.drop_table("validation_finding_events")
