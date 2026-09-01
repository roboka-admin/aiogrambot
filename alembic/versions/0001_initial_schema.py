"""Create initial application schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("telegram_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("coins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("registration_status", sa.String(length=20), nullable=False, server_default="unregistered"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_tickets_user_telegram_id", "support_tickets", ["user_telegram_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])

    op.create_table(
        "broadcast_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("total_recipients", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "antispam_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Enum("WARNING", "BLOCK", name="antispameventtype"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_antispam_events_user_telegram_id", "antispam_events", ["user_telegram_id"])
    op.create_index("ix_antispam_events_event_type", "antispam_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_antispam_events_event_type", table_name="antispam_events")
    op.drop_index("ix_antispam_events_user_telegram_id", table_name="antispam_events")
    op.drop_table("antispam_events")
    op.drop_table("broadcast_records")
    op.drop_index("ix_support_tickets_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_user_telegram_id", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_table("users")
