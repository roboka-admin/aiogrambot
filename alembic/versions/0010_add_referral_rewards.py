"""Add referral reward ledger.

Revision ID: 0010_add_referral_rewards
Revises: 0009_add_referral_reward
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_add_referral_rewards"
down_revision: Union[str, Sequence[str], None] = "0009_add_referral_reward"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referrer_id", sa.BigInteger(), nullable=False),
        sa.Column("triggered_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("coins", sa.Integer(), nullable=False),
        sa.Column("invites_consumed", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_referral_rewards_referrer_id",
        "referral_rewards",
        ["referrer_id"],
    )
    op.create_index(
        "ix_referral_rewards_created_at",
        "referral_rewards",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_referral_rewards_created_at", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_referrer_id", table_name="referral_rewards")
    op.drop_table("referral_rewards")
