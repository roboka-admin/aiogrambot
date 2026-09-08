from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
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
            .values(referral_processed_at=processed_at)
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
        from models.user import RegistrationStatus, UserStatus

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
        )
