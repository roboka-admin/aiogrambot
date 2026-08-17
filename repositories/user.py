from sqlalchemy import delete as sql_delete
from sqlalchemy import select
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

    async def get_by_telegram_id(
        self,
        telegram_id: int,
    ) -> User | None:
        result = await self._session.execute(
            select(UserRecord).where(UserRecord.telegram_id == telegram_id)
        )
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._to_domain(record)

    async def update(self, user: User) -> User:
        record = await self._session.get(UserRecord, user.telegram_id)

        if record is None:
            record = UserRecord(telegram_id=user.telegram_id)
            self._session.add(record)

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
