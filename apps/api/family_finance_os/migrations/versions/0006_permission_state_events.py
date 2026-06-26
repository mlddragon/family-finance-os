from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_permission_state_events"
down_revision = "0005_actor_context_foundation"
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
        "permission_state_events",
        *_id_columns(),
        sa.Column("recorded_at", sa.String(length=40), nullable=False),
        sa.Column("actor_context_json", sa.Text()),
        sa.Column("target_kind", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("effect", sa.String(length=20)),
        sa.Column("action_key", sa.String(length=120), nullable=False),
        sa.Column("data_scope_key", sa.String(length=120), nullable=False),
        sa.Column("scope_selector", sa.String(length=200)),
        sa.Column("reason_note", sa.Text(), nullable=False),
        sa.Column("supersedes_event_id", sa.String(length=36)),
    )


def downgrade() -> None:
    op.drop_table("permission_state_events")
