"""Add global bot settings.

Revision ID: 0002_add_bot_settings
Revises: 0001_initial_schema
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_bot_settings"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OFFLINE_MESSAGE = "⛔️ ربات در حال حاضر غیرفعال است. لطفاً بعداً دوباره تلاش کنید."
_MAINTENANCE_MESSAGE = "🛠 ربات در حال بروزرسانی و نگهداری است. لطفاً کمی بعد دوباره تلاش کنید."


def upgrade() -> None:
    table = op.create_table(
        "bot_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("bot_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("offline_message", sa.String(length=1000), nullable=False),
        sa.Column("maintenance_message", sa.String(length=1000), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.bulk_insert(
        table,
        [
            {
                "id": 1,
                "bot_enabled": True,
                "maintenance_mode": False,
                "offline_message": _OFFLINE_MESSAGE,
                "maintenance_message": _MAINTENANCE_MESSAGE,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("bot_settings")
