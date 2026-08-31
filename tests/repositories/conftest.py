import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with factory() as session:
            async with session.begin():
                yield session
    finally:
        await engine.dispose()
