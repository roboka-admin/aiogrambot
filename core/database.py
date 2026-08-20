from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(
        self,
        database_url: str,
    ) -> None:
        self.engine = create_async_engine(
            database_url,
            echo=True,
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            yield session

    async def create_tables(self) -> None:
        from models.base import Base
        from models.support_db import SupportTicketRecord
        from models.user_db import UserRecord

        _ = UserRecord, SupportTicketRecord

        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()
