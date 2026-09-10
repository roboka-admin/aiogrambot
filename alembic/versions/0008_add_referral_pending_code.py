"""Add pending referral payload for deferred force-subscription attribution.

Revision ID: 0008_add_referral_pending_code
Revises: 0007_add_referrals
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_add_referral_pending_code"
down_revision: Union[str, Sequence[str], None] = "0007_add_referrals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("referral_pending_code", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "referral_pending_code")
