import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from models.admin_db import (
    AdminPermissionAssignmentRecord,
    AdminPermissionRecord,
    AdminRecord,
)
from models.antispam_db import AntiSpamEventRecord
from models.base import Base
from models.bot_settings_db import BotSettingsRecord
from models.broadcast_db import BroadcastRecordRecord
from models.force_subscription_db import ForceSubscriptionMembershipEventRecord
from models.force_subscription_db import ForceSubscriptionTargetRecord
from models.support_db import SupportTicketRecord
from models.user_db import UserRecord

_ = (
    UserRecord,
    SupportTicketRecord,
    BroadcastRecordRecord,
    AntiSpamEventRecord,
    BotSettingsRecord,
    ForceSubscriptionTargetRecord,
    ForceSubscriptionMembershipEventRecord,
    AdminRecord,
    AdminPermissionRecord,
    AdminPermissionAssignmentRecord,
)


async def _reset_test_database(connection) -> None:
    """Remove every user table so the migration chain always starts from zero."""
    tables = set((await connection.execute(text("SHOW TABLES"))).scalars())
    if not tables:
        return

    await connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    try:
        for table in tables:
            await connection.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
    finally:
        await connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


def _run_alembic_upgrade(revision: str) -> str:
    """Upgrade the dedicated test database and return Alembic's combined output."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", "database=test", "upgrade", revision],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def _get_test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is not configured")

    if not database_url.startswith("mysql+asyncmy://"):
        raise RuntimeError("TEST_DATABASE_URL must use mysql+asyncmy://")

    return database_url


@pytest.mark.asyncio
async def test_initial_migration_builds_test_database_from_empty_schema() -> None:
    """Verify the real Alembic migration chain can build the dedicated test DB from scratch."""
    engine = create_async_engine(_get_test_database_url(), pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await _reset_test_database(connection)

        output = _run_alembic_upgrade("head")
        assert "Running upgrade  -> 0001_initial_schema" in output
        assert "0001_initial_schema -> 0002_add_bot_settings" in output
        assert "0002_add_bot_settings -> 0003_add_antispam_enabled" in output
        assert "0003_add_antispam_enabled -> 0004_add_force_subscription" in output
        assert "0004_add_force_subscription -> 0005_membership_events" in output
        assert "0005_membership_events -> 0006_admin_foundation" in output
        assert "0006_admin_foundation -> 0007_add_referrals" in output
        assert "0007_add_referrals -> 0008_add_referral_pending_code" in output
        assert (
            "0008_add_referral_pending_code -> 0009_add_referral_reward_settings"
            in output
        )

        async with AsyncSession(engine, expire_on_commit=False) as session:
            tables = set((await session.execute(text("SHOW TABLES"))).scalars())
            revision = (
                await session.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
            user_columns = {
                row[0]
                for row in (
                    await session.execute(text("SHOW COLUMNS FROM users"))
                ).all()
            }
            settings_count = (
                await session.execute(text("SELECT COUNT(*) FROM bot_settings WHERE id = 1"))
            ).scalar_one()
            (
                antispam_enabled,
                force_subscription_enabled,
                referral_reward_coins,
                referral_reward_per_invites,
            ) = (
                await session.execute(
                    text(
                        "SELECT antispam_enabled, force_subscription_enabled, "
                        "referral_reward_coins, referral_reward_per_invites "
                        "FROM bot_settings WHERE id = 1"
                    )
                )
            ).one()

        assert {
            "users",
            "support_tickets",
            "broadcast_records",
            "antispam_events",
            "bot_settings",
            "force_subscription_targets",
            "force_subscription_membership_events",
            "admins",
            "admin_permissions",
            "admin_permission_assignments",
            "alembic_version",
        }.issubset(tables)
        assert {
            "referral_code",
            "referred_by_user_id",
            "referral_processed_at",
            "referral_pending_code",
        }.issubset(user_columns)
        assert revision == "0009_add_referral_reward_settings"
        assert settings_count == 1
        assert antispam_enabled == 1
        assert force_subscription_enabled == 0
        assert referral_reward_coins == 1
        assert referral_reward_per_invites == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_referral_migration_widens_legacy_int_telegram_id() -> None:
    """Databases created with an INT users.telegram_id must still reach 0007.

    MySQL rejects a foreign key between INT and BIGINT columns, so without the
    widening step 0007 used to fail on the referrer FK and leave the schema
    half-migrated.
    """
    engine = create_async_engine(_get_test_database_url(), pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await _reset_test_database(connection)

        _run_alembic_upgrade("0006_admin_foundation")

        async with engine.begin() as connection:
            await connection.execute(
                text("ALTER TABLE users MODIFY telegram_id INT NOT NULL")
            )

        output = _run_alembic_upgrade("head")
        assert "0006_admin_foundation -> 0007_add_referrals" in output

        async with AsyncSession(engine, expire_on_commit=False) as session:
            telegram_id_type = (
                await session.execute(
                    text(
                        "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' "
                        "AND COLUMN_NAME = 'telegram_id'"
                    )
                )
            ).scalar_one()
            foreign_keys = set(
                (
                    await session.execute(
                        text(
                            "SELECT CONSTRAINT_NAME "
                            "FROM information_schema.TABLE_CONSTRAINTS "
                            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' "
                            "AND CONSTRAINT_TYPE = 'FOREIGN KEY'"
                        )
                    )
                ).scalars()
            )
            revision = (
                await session.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()

        assert telegram_id_type.lower() == "bigint"
        assert "fk_users_referred_by_user_id" in foreign_keys
        assert revision == "0009_add_referral_reward_settings"
    finally:
        await engine.dispose()
