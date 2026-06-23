from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_open_source_category_catalog"
down_revision = "0003_validation_finding_events"
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
        "categories",
        *_id_columns(),
        sa.Column("category_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("category_type", sa.String(length=40), nullable=False),
        sa.Column("aliases_json", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_note", sa.Text()),
        sa.Column("updated_by", sa.String(length=120)),
        sa.Column("updated_note", sa.Text()),
        sa.UniqueConstraint("category_key"),
    )


def downgrade() -> None:
    op.drop_table("categories")
