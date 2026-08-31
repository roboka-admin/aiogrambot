import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.antispam_db import AntiSpamEventRecord
from models.base import Base
from models.broadcast_db import BroadcastRecordRecord
from models.support_db import SupportTicketRecord
from models.user_db import UserRecord

_ = UserRecord, SupportTicketRecord, BroadcastRecordRecord, AntiSpamEventRecord


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
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

    await engine.dispose()
