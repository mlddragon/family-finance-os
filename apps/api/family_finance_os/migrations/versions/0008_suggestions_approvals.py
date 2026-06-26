from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_suggestions_approvals"
down_revision = "0007_elevated_mode_events"
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
        "suggestions",
        *_id_columns(),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("action_key", sa.String(length=120), nullable=False),
        sa.Column("decision_type", sa.String(length=80), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("previous_value", sa.Text()),
        sa.Column("proposed_value", sa.Text()),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("proposer_actor", sa.String(length=120), nullable=False),
        sa.Column("proposer_actor_context_json", sa.Text()),
        sa.Column("suggestion_source", sa.String(length=80), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("decision_event_id", sa.String(length=36)),
        sa.Column("approval_request_id", sa.String(length=36)),
    )
    op.create_index(
        "ix_suggestions_target_status",
        "suggestions",
        ["target_type", "target_id", "status"],
    )

    op.create_table(
        "suggestion_events",
        *_id_columns(),
        sa.Column("suggestion_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("actor_context_json", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.ForeignKeyConstraint(["suggestion_id"], ["suggestions.id"]),
    )

    op.create_table(
        "approval_requests",
        *_id_columns(),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("action_key", sa.String(length=120), nullable=False),
        sa.Column("decision_type", sa.String(length=80), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("previous_value", sa.Text()),
        sa.Column("proposed_value", sa.Text()),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("proposer_actor", sa.String(length=120), nullable=False),
        sa.Column("proposer_actor_context_json", sa.Text()),
        sa.Column("policy_trigger", sa.String(length=120), nullable=False),
        sa.Column("expires_at", sa.String(length=40), nullable=False),
        sa.Column("source_suggestion_id", sa.String(length=36)),
        sa.Column("notes", sa.Text()),
        sa.Column("applied_decision_event_id", sa.String(length=36)),
        sa.ForeignKeyConstraint(["source_suggestion_id"], ["suggestions.id"]),
    )
    op.create_index(
        "ix_approval_requests_pending_target",
        "approval_requests",
        ["target_type", "target_id", "action_key", "field_name", "status"],
    )

    op.create_table(
        "approval_request_events",
        *_id_columns(),
        sa.Column("approval_request_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("actor_context_json", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
    )


def downgrade() -> None:
    op.drop_table("approval_request_events")
    op.drop_table("approval_requests")
    op.drop_table("suggestion_events")
    op.drop_table("suggestions")
