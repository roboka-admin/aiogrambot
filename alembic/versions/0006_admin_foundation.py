"""Create administrator and dynamic permission tables.

Revision ID: 0006_admin_foundation
Revises: 0005_membership_events
Create Date: 2026-09-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_admin_foundation"
down_revision: Union[str, Sequence[str], None] = "0005_membership_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="admin"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("telegram_id"),
    )

    op.create_table(
        "admin_permissions",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "admin_permission_assignments",
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_key", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_telegram_id"], ["admins.telegram_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["permission_key"], ["admin_permissions.key"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("admin_telegram_id", "permission_key"),
    )


def downgrade() -> None:
    op.drop_table("admin_permission_assignments")
    op.drop_table("admin_permissions")
    op.drop_table("admins")
