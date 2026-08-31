import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from models.antispam_db import AntiSpamEventRecord
from models.base import Base
from models.broadcast_db import BroadcastRecordRecord
from models.support_db import SupportTicketRecord
from models.user_db import UserRecord

_ = UserRecord, SupportTicketRecord, BroadcastRecordRecord, AntiSpamEventRecord


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set. Repository integration tests require "
            "a dedicated MySQL test database; never point it at the production database."
        )

    if not database_url.startswith("mysql+asyncmy://"):
        raise RuntimeError(
            "TEST_DATABASE_URL must use the mysql+asyncmy:// SQLAlchemy driver."
        )

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        # Each test gets a completely empty database schema. This is important
        # because repository methods flush their changes, while the fixture
        # must not commit test data and leak it into the next test.
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
    finally:
        await engine.dispose()
