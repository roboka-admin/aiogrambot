"""Add force subscription membership verification events.

Revision ID: 0005_membership_events
Revises: 0004_add_force_subscription
Create Date: 2026-09-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_membership_events"
down_revision: Union[str, Sequence[str], None] = "0004_add_force_subscription"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "force_subscription_membership_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("target_chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_force_subscription_events_created_at",
        "force_subscription_membership_events",
        ["created_at"],
    )
    op.create_index(
        "ix_force_subscription_events_target_created",
        "force_subscription_membership_events",
        ["target_chat_id", "created_at"],
    )
    op.create_index(
        "ix_force_subscription_events_user_created",
        "force_subscription_membership_events",
        ["user_telegram_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_force_subscription_events_user_created",
        table_name="force_subscription_membership_events",
    )
    op.drop_index(
        "ix_force_subscription_events_target_created",
        table_name="force_subscription_membership_events",
    )
    op.drop_index(
        "ix_force_subscription_events_created_at",
        table_name="force_subscription_membership_events",
    )
    op.drop_table("force_subscription_membership_events")
