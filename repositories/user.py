from datetime import datetime

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import RegistrationStatus, User, UserStatus
from models.user_db import UserRecord
from repositories.interfaces.user import IUserRepository


class UserRepository(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        record = UserRecord(
            telegram_id=user.telegram_id,
            telegram_name=user.telegram_name,
            username=user.username,
            name=user.name,
            age=user.age,
            coins=user.coins,
            warnings=user.warnings,
            status=user.status.value,
            registration_status=user.registration_status.value,
            first_seen_at=user.first_seen_at,
            last_seen_at=user.last_seen_at,
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
        record = await self._session.get(UserRecord, telegram_id)
        return None if record is None else self._to_domain(record)

    async def update(self, user: User) -> User | None:
        record = await self._session.get(UserRecord, user.telegram_id)
        if record is None:
            return None

        record.telegram_name = user.telegram_name
        record.username = user.username
        record.name = user.name
        record.age = user.age
        record.coins = user.coins
        record.warnings = user.warnings
        record.status = user.status.value
        record.registration_status = user.registration_status.value
        record.first_seen_at = user.first_seen_at
        record.last_seen_at = user.last_seen_at
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
        return await self._count_where()

    async def count_registered(self) -> int:
        return await self._count_where(
            UserRecord.registration_status == RegistrationStatus.REGISTERED.value
        )

    async def count_unregistered(self) -> int:
        return await self._count_where(
            UserRecord.registration_status == RegistrationStatus.UNREGISTERED.value
        )

    async def count_active(self) -> int:
        return await self._count_where(
            UserRecord.status == UserStatus.ACTIVE.value
        )

    async def count_active_today(self, today_start: datetime) -> int:
        return await self._count_where(
            UserRecord.last_seen_at.is_not(None),
            UserRecord.last_seen_at >= today_start,
        )

    async def count_active_last_7_days(self, seven_days_ago: datetime) -> int:
        return await self._count_where(
            UserRecord.last_seen_at.is_not(None),
            UserRecord.last_seen_at >= seven_days_ago,
        )

    async def count_inactive_30_days(self, thirty_days_ago: datetime) -> int:
        return await self._count_where(
            or_(
                UserRecord.last_seen_at.is_(None),
                UserRecord.last_seen_at < thirty_days_ago,
            )
        )

    async def _count_where(self, *conditions) -> int:
        statement = select(func.count()).select_from(UserRecord)
        for condition in conditions:
            statement = statement.where(condition)
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def list_active_telegram_ids(
        self, *, registered_only: bool = False
    ) -> list[int]:
        statement = select(UserRecord.telegram_id).where(
            UserRecord.status == UserStatus.ACTIVE.value
        )
        if registered_only:
            statement = statement.where(
                UserRecord.registration_status
                == RegistrationStatus.REGISTERED.value
            )
        result = await self._session.execute(statement)
        return list(result.scalars())

    async def list_blocked_page(
        self, *, offset: int, limit: int
    ) -> list[User]:
        result = await self._session.execute(
            select(UserRecord)
            .where(UserRecord.status == UserStatus.BLOCKED.value)
            .order_by(UserRecord.telegram_id)
            .offset(offset)
            .limit(limit)
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def count_blocked(self) -> int:
        return await self._count_where(
            UserRecord.status == UserStatus.BLOCKED.value
        )

    @staticmethod
    def _to_domain(record: UserRecord) -> User:
        return User(
            telegram_id=record.telegram_id,
            telegram_name=record.telegram_name,
            username=record.username,
            name=record.name,
            age=record.age,
            coins=record.coins,
            warnings=record.warnings,
            status=UserStatus(record.status),
            registration_status=RegistrationStatus(record.registration_status),
            first_seen_at=record.first_seen_at,
            last_seen_at=record.last_seen_at,
        )
