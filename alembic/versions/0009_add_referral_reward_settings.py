"""Add admin-configurable referral reward (coins per N registered invites).

Revision ID: 0009_add_referral_reward_settings
Revises: 0008_add_referral_pending_code
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_add_referral_reward_settings"
down_revision: Union[str, Sequence[str], None] = "0008_add_referral_pending_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Defaults mirror models.bot_settings: 1 coin for every 1 registered invite.
    op.add_column(
        "bot_settings",
        sa.Column(
            "referral_reward_coins",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "bot_settings",
        sa.Column(
            "referral_reward_per_invites",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("bot_settings", "referral_reward_per_invites")
    op.drop_column("bot_settings", "referral_reward_coins")
