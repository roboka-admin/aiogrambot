"""Event retention: lifetime counters + indexes for time-window pruning.

``event_counters`` keeps the number of rows already deleted from an event
table so admin "all time" totals stay exact after pruning. The two indexes
make both the retention DELETEs and the existing ``created_at >= ?`` counts
on ``antispam_events`` index-backed (membership events and AI reports were
already indexed).

Revision ID: 0014_event_retention
Revises: 0013_update_gemini_model
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_event_retention"
down_revision: Union[str, Sequence[str], None] = "0013_update_gemini_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_counters",
        sa.Column("kind", sa.String(length=64), primary_key=True),
        sa.Column("archived_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_antispam_events_created_at", "antispam_events", ["created_at"])
    op.create_index(
        "ix_antispam_events_type_created", "antispam_events", ["event_type", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_antispam_events_type_created", table_name="antispam_events")
    op.drop_index("ix_antispam_events_created_at", table_name="antispam_events")
    op.drop_table("event_counters")
