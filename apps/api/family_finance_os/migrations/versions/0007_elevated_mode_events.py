from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_elevated_mode_events"
down_revision = "0006_permission_state_events"
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
        "elevated_mode_events",
        *_id_columns(),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("recorded_at", sa.String(length=40), nullable=False),
        sa.Column("actor_context_json", sa.Text()),
        sa.Column("context", sa.String(length=80), nullable=False),
        sa.Column("purpose_code", sa.String(length=120), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("exit_reason", sa.String(length=120)),
    )


def downgrade() -> None:
    op.drop_table("elevated_mode_events")
