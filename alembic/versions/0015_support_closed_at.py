"""Track when a support ticket was closed so closed tickets can be retained
for a bounded period.

Existing closed tickets get ``closed_at = created_at`` as a conservative
backfill: their real close time is unknown, and using creation time means
they are never kept *longer* than intended.

Revision ID: 0015_support_closed_at
Revises: 0014_event_retention
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_support_closed_at"
down_revision: Union[str, Sequence[str], None] = "0014_event_retention"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "support_tickets", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_support_tickets_status_closed_at", "support_tickets", ["status", "closed_at"]
    )
    op.execute(
        "UPDATE support_tickets SET closed_at = created_at "
        "WHERE status = 'closed' AND closed_at IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_support_tickets_status_closed_at", table_name="support_tickets")
    op.drop_column("support_tickets", "closed_at")
