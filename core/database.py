from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url, echo=True)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

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
            await self._migrate_users(connection)
            await self._migrate_support_tickets(connection)

    async def _migrate_users(self, connection) -> None:
        """Small compatibility migration for the existing users table."""
        result = await connection.execute(text("SHOW COLUMNS FROM users"))
        columns = {row[0] for row in result}
        if "telegram_name" not in columns:
            await connection.execute(text("ALTER TABLE users ADD COLUMN telegram_name VARCHAR(100) NOT NULL DEFAULT ''"))
        if "username" not in columns:
            await connection.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100) NULL"))
        if "registration_status" not in columns:
            await connection.execute(text("ALTER TABLE users ADD COLUMN registration_status VARCHAR(20) NOT NULL DEFAULT 'unregistered'"))
            await connection.execute(text("UPDATE users SET registration_status = 'registered'"))
        if "first_seen_at" not in columns:
            await connection.execute(text("ALTER TABLE users ADD COLUMN first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        if "last_seen_at" not in columns:
            await connection.execute(text("ALTER TABLE users ADD COLUMN last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        await connection.execute(text("ALTER TABLE users MODIFY COLUMN name VARCHAR(100) NULL"))
        await connection.execute(text("ALTER TABLE users MODIFY COLUMN age INTEGER NULL"))

    async def _migrate_support_tickets(self, connection) -> None:
        """Migration for support_tickets table to add created_at column."""
        result = await connection.execute(text("SHOW COLUMNS FROM support_tickets"))
        columns = {row[0] for row in result}
        if "created_at" not in columns:
            await connection.execute(
                text("ALTER TABLE support_tickets ADD COLUMN created_at DATETIME NULL")
            )
            await connection.execute(
                text(
                    "UPDATE support_tickets SET created_at = CURRENT_TIMESTAMP "
                    "WHERE created_at IS NULL"
                )
            )

    async def dispose(self) -> None:
        await self.engine.dispose()
