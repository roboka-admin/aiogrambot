from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    """Own the database engine and create request-scoped sessions."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
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

    async def get_db_stats(self) -> tuple[int, int | None]:
        """Get database table count and total row count."""
        async with self.engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE()"
                )
            )
            table_count = result.scalar_one()

            try:
                result = await connection.execute(
                    text(
                        "SELECT SUM(table_rows) "
                        "FROM information_schema.tables "
                        "WHERE table_schema = DATABASE()"
                    )
                )
                row_count = result.scalar_one()
            except Exception:
                row_count = None

            return table_count or 0, row_count

    async def dispose(self) -> None:
        await self.engine.dispose()
