import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from models.antispam_db import AntiSpamEventRecord
from models.base import Base
from models.bot_settings_db import BotSettingsRecord
from models.broadcast_db import BroadcastRecordRecord
from models.support_db import SupportTicketRecord
from models.user_db import UserRecord

_ = (
    UserRecord,
    SupportTicketRecord,
    BroadcastRecordRecord,
    AntiSpamEventRecord,
    BotSettingsRecord,
)


@pytest.mark.asyncio
async def test_initial_migration_builds_test_database_from_empty_schema() -> None:
    """Verify the real Alembic migration chain can build the dedicated test DB from scratch."""
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is not configured")

    if not database_url.startswith("mysql+asyncmy://"):
        raise RuntimeError("TEST_DATABASE_URL must use mysql+asyncmy://")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        # This test is intentionally destructive, but only against TEST_DATABASE_URL.
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-x",
                "database=test",
                "upgrade",
                "head",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        # Alembic writes its logging output to stderr, so inspect both streams.
        output = result.stdout + result.stderr
        assert "Running upgrade  -> 0001_initial_schema" in output
        assert "0001_initial_schema -> 0002_add_bot_settings" in output

        async with AsyncSession(engine, expire_on_commit=False) as session:
            tables = set(
                (
                    await session.execute(
                        text("SHOW TABLES")
                    )
                ).scalars()
            )
            revision = (
                await session.execute(
                    text("SELECT version_num FROM alembic_version")
                )
            ).scalar_one()
            settings_count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM bot_settings WHERE id = 1")
                )
            ).scalar_one()

        assert {
            "users",
            "support_tickets",
            "broadcast_records",
            "antispam_events",
            "bot_settings",
            "alembic_version",
        }.issubset(tables)
        assert revision == "0002_add_bot_settings"
        assert settings_count == 1
    finally:
        await engine.dispose()
