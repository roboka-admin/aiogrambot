"""Add referral tracking fields to users.

Revision ID: 0007_add_referrals
Revises: 0006_admin_foundation
Create Date: 2026-09-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_add_referrals"
down_revision: Union[str, Sequence[str], None] = "0006_admin_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("referral_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("referred_by_user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("referral_processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_users_referral_code",
        "users",
        ["referral_code"],
        unique=True,
    )
    op.create_foreign_key(
        "fk_users_referred_by_user_id",
        "users",
        "users",
        ["referred_by_user_id"],
        ["telegram_id"],
        ondelete="SET NULL",
    )

    # Users that already existed before referral support must not become
    # retroactively eligible for a referral claim. A first /start after the
    # migration therefore cannot attach a referrer to an old account.
    op.execute(
        sa.text(
            "UPDATE users "
            "SET referral_processed_at = first_seen_at "
            "WHERE referral_processed_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_referred_by_user_id", "users", type_="foreignkey")
    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_column("users", "referral_processed_at")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")
