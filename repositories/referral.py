from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import RegistrationStatus, User, UserStatus
from models.user_db import UserRecord
from repositories.interfaces.referral import IReferralRepository


class ReferralRepository(IReferralRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_referral_code(self, telegram_id: int) -> str | None:
        result = await self._session.execute(
            select(UserRecord.referral_code).where(
                UserRecord.telegram_id == telegram_id
            )
        )
        return result.scalar_one_or_none()

    async def set_referral_code_if_missing(self, telegram_id: int, code: str) -> bool:
        result = await self._session.execute(
            update(UserRecord)
            .where(
                UserRecord.telegram_id == telegram_id,
                UserRecord.referral_code.is_(None),
            )
            .values(referral_code=code)
        )
        await self._session.flush()
        return result.rowcount == 1

    async def find_user_by_referral_code(self, code: str) -> User | None:
        result = await self._session.execute(
            select(UserRecord).where(UserRecord.referral_code == code)
        )
        record = result.scalar_one_or_none()
        return None if record is None else self._to_domain(record)

    async def claim_referral(
        self, telegram_id: int, referrer_id: int, processed_at: datetime
    ) -> bool:
        result = await self._session.execute(
            update(UserRecord)
            .where(
                UserRecord.telegram_id == telegram_id,
                UserRecord.telegram_id != referrer_id,
                UserRecord.referred_by_user_id.is_(None),
                UserRecord.referral_processed_at.is_(None),
            )
            .values(
                referred_by_user_id=referrer_id,
                referral_processed_at=processed_at,
                referral_pending_code=None,
            )
        )
        await self._session.flush()
        return result.rowcount == 1

    async def mark_referral_processed(
        self, telegram_id: int, processed_at: datetime
    ) -> bool:
        result = await self._session.execute(
            update(UserRecord)
            .where(
                UserRecord.telegram_id == telegram_id,
                UserRecord.referral_processed_at.is_(None),
            )
            .values(
                referral_processed_at=processed_at,
                referral_pending_code=None,
            )
        )
        await self._session.flush()
        return result.rowcount == 1

    async def get_pending_referral_code(self, telegram_id: int) -> str | None:
        result = await self._session.execute(
            select(UserRecord.referral_pending_code).where(
                UserRecord.telegram_id == telegram_id
            )
        )
        return result.scalar_one_or_none()

    async def save_pending_referral_code(
        self, telegram_id: int, code: str
    ) -> bool:
        # First invite wins: keep an existing pending code, and never store
        # anything once the referral decision for this user is final.
        result = await self._session.execute(
            update(UserRecord)
            .where(
                UserRecord.telegram_id == telegram_id,
                UserRecord.referred_by_user_id.is_(None),
                UserRecord.referral_processed_at.is_(None),
                UserRecord.referral_pending_code.is_(None),
            )
            .values(referral_pending_code=code)
        )
        await self._session.flush()
        return result.rowcount == 1

    async def count_referrals(self, telegram_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserRecord)
            .where(UserRecord.referred_by_user_id == telegram_id)
        )
        return result.scalar_one()

    async def count_registered_referrals(self, telegram_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserRecord)
            .where(
                UserRecord.referred_by_user_id == telegram_id,
                UserRecord.registration_status
                == RegistrationStatus.REGISTERED.value,
            )
        )
        return result.scalar_one()

    async def add_coins(self, telegram_id: int, amount: int) -> int | None:
        """Atomically credit coins and return the new balance (None if no such user)."""
        result = await self._session.execute(
            update(UserRecord)
            .where(UserRecord.telegram_id == telegram_id)
            .values(coins=UserRecord.coins + amount)
        )
        await self._session.flush()
        if result.rowcount != 1:
            return None
        balance = await self._session.execute(
            select(UserRecord.coins).where(UserRecord.telegram_id == telegram_id)
        )
        return balance.scalar_one()

    async def count_referrals_total(self) -> int:
        return await self._count_referred_where()

    async def count_referred_registered(self) -> int:
        return await self._count_referred_where(
            UserRecord.registration_status == RegistrationStatus.REGISTERED.value
        )

    async def count_users_with_referral_code(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserRecord)
            .where(UserRecord.referral_code.is_not(None))
        )
        return result.scalar_one()

    async def count_referrals_since(self, since: datetime) -> int:
        # referral_processed_at is set for every user's first /start, not only
        # referred ones, so the claim filter is what turns this into a
        # "referrals claimed in window" count.
        return await self._count_referred_where(
            UserRecord.referral_processed_at.is_not(None),
            UserRecord.referral_processed_at >= since,
        )

    async def top_referrers(self, *, limit: int) -> list[tuple[User, int]]:
        referral_counts = (
            select(
                UserRecord.referred_by_user_id.label("referrer_id"),
                func.count().label("referral_count"),
            )
            .where(UserRecord.referred_by_user_id.is_not(None))
            .group_by(UserRecord.referred_by_user_id)
            .order_by(func.count().desc(), UserRecord.referred_by_user_id)
            .limit(limit)
            .subquery()
        )
        result = await self._session.execute(
            select(UserRecord, referral_counts.c.referral_count)
            .join(
                referral_counts,
                UserRecord.telegram_id == referral_counts.c.referrer_id,
            )
            .order_by(
                referral_counts.c.referral_count.desc(),
                UserRecord.telegram_id,
            )
        )
        return [(self._to_domain(record), count) for record, count in result.all()]

    async def _count_referred_where(self, *conditions) -> int:
        statement = (
            select(func.count())
            .select_from(UserRecord)
            .where(UserRecord.referred_by_user_id.is_not(None))
        )
        for condition in conditions:
            statement = statement.where(condition)
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def list_referrals(
        self, telegram_id: int, *, offset: int, limit: int
    ) -> list[User]:
        result = await self._session.execute(
            select(UserRecord)
            .where(UserRecord.referred_by_user_id == telegram_id)
            .order_by(UserRecord.first_seen_at, UserRecord.telegram_id)
            .offset(offset)
            .limit(limit)
        )
        return [self._to_domain(record) for record in result.scalars()]

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
            referral_code=record.referral_code,
            referred_by_user_id=record.referred_by_user_id,
            referral_processed_at=record.referral_processed_at,
            referral_pending_code=record.referral_pending_code,
        )
