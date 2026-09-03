"""Add anti-spam enabled setting.

Revision ID: 0003_add_antispam_enabled
Revises: 0002_add_bot_settings
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_add_antispam_enabled"
down_revision: Union[str, Sequence[str], None] = "0002_add_bot_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_settings",
        sa.Column(
            "antispam_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("bot_settings", "antispam_enabled")
