from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserStatus
from models.user_db import UserRecord
from repositories.interfaces.user import IUserRepository


class UserRepository(IUserRepository):
    """SQLAlchemy repository for user persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        record = UserRecord(
            telegram_id=user.telegram_id,
            name=user.name,
            age=user.age,
            coins=user.coins,
            warnings=user.warnings,
            status=user.status.value,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def exists(self, telegram_id: int) -> bool:
        result = await self._session.execute(
            select(UserRecord.telegram_id).where(
                UserRecord.telegram_id == telegram_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(UserRecord).where(UserRecord.telegram_id == telegram_id)
        )
        record = result.scalar_one_or_none()
        return None if record is None else self._to_domain(record)

    async def update(self, user: User) -> User | None:
        record = await self._session.get(UserRecord, user.telegram_id)
        if record is None:
            return None

        record.name = user.name
        record.age = user.age
        record.coins = user.coins
        record.warnings = user.warnings
        record.status = user.status.value
        await self._session.flush()
        return self._to_domain(record)

    async def delete(self, telegram_id: int) -> bool:
        result = await self._session.execute(
            sql_delete(UserRecord).where(UserRecord.telegram_id == telegram_id)
        )
        await self._session.flush()
        return result.rowcount > 0

    async def list_all(self) -> list[User]:
        result = await self._session.execute(
            select(UserRecord).order_by(UserRecord.telegram_id)
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def list_page(self, *, offset: int, limit: int) -> list[User]:
        result = await self._session.execute(
            select(UserRecord)
            .order_by(UserRecord.telegram_id)
            .offset(offset)
            .limit(limit)
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(UserRecord)
        )
        return result.scalar_one()

    async def list_active_telegram_ids(self) -> list[int]:
        result = await self._session.execute(
            select(UserRecord.telegram_id).where(
                UserRecord.status == UserStatus.ACTIVE.value
            )
        )
        return list(result.scalars())

    async def list_blocked_page(self, *, offset: int, limit: int) -> list[User]:
        result = await self._session.execute(
            select(UserRecord)
            .where(UserRecord.status == UserStatus.BLOCKED.value)
            .order_by(UserRecord.telegram_id)
            .offset(offset)
            .limit(limit)
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def count_blocked(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(UserRecord).where(
                UserRecord.status == UserStatus.BLOCKED.value
            )
        )
        return result.scalar_one()

    @staticmethod
    def _to_domain(record: UserRecord) -> User:
        return User(
            telegram_id=record.telegram_id,
            name=record.name,
            age=record.age,
            coins=record.coins,
            warnings=record.warnings,
            status=UserStatus(record.status),
        )
