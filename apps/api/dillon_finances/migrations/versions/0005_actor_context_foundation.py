from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_actor_context_foundation"
down_revision = "0004_open_source_category_catalog"
branch_labels = None
depends_on = None


TABLES = (
    "import_batch_events",
    "validation_finding_events",
    "settings_events",
    "decision_events",
    "jobs",
    "report_runs",
    "monthly_closes",
)


def upgrade() -> None:
    for table_name in TABLES:
        op.add_column(table_name, sa.Column("actor_context_json", sa.Text()))


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_column(table_name, "actor_context_json")
