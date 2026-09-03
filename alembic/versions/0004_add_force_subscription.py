"""Add force subscription settings and targets.

Revision ID: 0004_add_force_subscription
Revises: 0003_add_antispam_enabled
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_add_force_subscription"
down_revision: Union[str, Sequence[str], None] = "0003_add_antispam_enabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_settings",
        sa.Column(
            "force_subscription_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "force_subscription_targets",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("invite_link", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("chat_id"),
    )


def downgrade() -> None:
    op.drop_table("force_subscription_targets")
    op.drop_column("bot_settings", "force_subscription_enabled")
