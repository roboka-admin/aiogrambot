"""AI monitoring: provider registry, report history, settings flags.

Revision ID: 0012_add_ai_monitoring
Revises: 0011_add_user_bot_blocked_at
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_add_ai_monitoring"
down_revision: Union[str, Sequence[str], None] = "0011_add_user_bot_blocked_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    providers = op.create_table(
        "ai_providers",
        sa.Column("key", sa.String(length=50), primary_key=True),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("api_key_env", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ready"),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_token_budget", sa.Integer(), nullable=True),
        sa.Column("tokens_in_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_today_date", sa.String(length=10), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "ai_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("provider_key", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("anomaly_keys", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_reports_created_at", "ai_reports", ["created_at"])

    op.add_column(
        "bot_settings",
        sa.Column("ai_monitoring_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "bot_settings",
        sa.Column(
            "ai_digest_interval_hours", sa.Integer(), nullable=False, server_default="24"
        ),
    )

    # Seed the two providers agreed for this project. Keys come from env
    # vars; a provider whose env var is missing is simply skipped by the
    # router, so seeding them enabled is safe.
    op.bulk_insert(
        providers,
        [
            {
                "key": "gemini",
                "display_name": "Google Gemini",
                "kind": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "model": "gemini-2.5-flash-lite",
                "api_key_env": "GEMINI_API_KEY",
                "enabled": True,
                "priority": 10,
                "daily_token_budget": 200000,
            },
            {
                "key": "mistral",
                "display_name": "Mistral",
                "kind": "openai_compatible",
                "base_url": "https://api.mistral.ai/v1",
                "model": "mistral-small-latest",
                "api_key_env": "MISTRAL_API_KEY",
                "enabled": True,
                "priority": 20,
                "daily_token_budget": 200000,
            },
        ],
    )


def downgrade() -> None:
    op.drop_column("bot_settings", "ai_digest_interval_hours")
    op.drop_column("bot_settings", "ai_monitoring_enabled")
    op.drop_index("ix_ai_reports_created_at", table_name="ai_reports")
    op.drop_table("ai_reports")
    op.drop_table("ai_providers")
