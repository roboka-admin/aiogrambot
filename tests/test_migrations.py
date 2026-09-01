import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from models.base import Base


@pytest.mark.asyncio
async def test_initial_migration_builds_test_database_from_empty_schema() -> None:
    """Verify the real Alembic migration can build the dedicated test DB from scratch."""
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

        assert "Running upgrade  -> 0001_initial_schema" in result.stdout

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

        assert {
            "users",
            "support_tickets",
            "broadcast_records",
            "antispam_events",
            "alembic_version",
        }.issubset(tables)
        assert revision == "0001_initial_schema"
    finally:
        await engine.dispose()
