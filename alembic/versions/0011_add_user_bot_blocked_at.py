"""Track when a user blocked the bot.

Revision ID: 0011_add_user_bot_blocked_at
Revises: 0010_add_referral_rewards
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_add_user_bot_blocked_at"
down_revision: Union[str, Sequence[str], None] = "0010_add_referral_rewards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("bot_blocked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_bot_blocked_at", "users", ["bot_blocked_at"])


def downgrade() -> None:
    op.drop_index("ix_users_bot_blocked_at", table_name="users")
    op.drop_column("users", "bot_blocked_at")
