from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from models.referral_reward import ReferralRewardEntry, ReferralRewardHistoryItem
from models.referral_reward_db import ReferralRewardRecord
from models.user_db import UserRecord
from repositories.interfaces.referral_reward import IReferralRewardRepository


class ReferralRewardRepository(IReferralRewardRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: ReferralRewardEntry) -> ReferralRewardEntry:
        record = ReferralRewardRecord(
            referrer_id=entry.referrer_id,
            triggered_by_user_id=entry.triggered_by_user_id,
            coins=entry.coins,
            invites_consumed=entry.invites_consumed,
            created_at=entry.created_at,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def sum_invites_consumed(self, referrer_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(ReferralRewardRecord.invites_consumed), 0))
            .where(ReferralRewardRecord.referrer_id == referrer_id)
        )
        return int(result.scalar_one())

    async def sum_coins(self, referrer_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(ReferralRewardRecord.coins), 0))
            .where(ReferralRewardRecord.referrer_id == referrer_id)
        )
        return int(result.scalar_one())

    async def sum_coins_total(self) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(ReferralRewardRecord.coins), 0))
        )
        return int(result.scalar_one())

    async def count_total(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(ReferralRewardRecord)
        )
        return result.scalar_one()

    async def count_since(self, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ReferralRewardRecord)
            .where(ReferralRewardRecord.created_at >= since)
        )
        return result.scalar_one()

    async def list_recent(self, *, limit: int) -> list[ReferralRewardEntry]:
        result = await self._session.execute(
            select(ReferralRewardRecord)
            .order_by(ReferralRewardRecord.created_at.desc(), ReferralRewardRecord.id.desc())
            .limit(limit)
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def list_recent_with_names(
        self, *, limit: int
    ) -> list[ReferralRewardHistoryItem]:
        # The ledger references users twice (who got paid, whose registration
        # triggered it), so the users table is joined under two aliases.
        # Outer joins keep the payout visible even if a user row is gone.
        referrer = aliased(UserRecord)
        triggered_by = aliased(UserRecord)
        result = await self._session.execute(
            select(
                ReferralRewardRecord,
                referrer.name,
                referrer.telegram_name,
                triggered_by.name,
                triggered_by.telegram_name,
            )
            .outerjoin(referrer, referrer.telegram_id == ReferralRewardRecord.referrer_id)
            .outerjoin(
                triggered_by,
                triggered_by.telegram_id == ReferralRewardRecord.triggered_by_user_id,
            )
            .order_by(ReferralRewardRecord.created_at.desc(), ReferralRewardRecord.id.desc())
            .limit(limit)
        )
        return [
            ReferralRewardHistoryItem(
                entry=self._to_domain(record),
                referrer_name=referrer_name or referrer_telegram_name,
                triggered_by_name=triggered_name or triggered_telegram_name,
            )
            for (
                record,
                referrer_name,
                referrer_telegram_name,
                triggered_name,
                triggered_telegram_name,
            ) in result.all()
        ]

    @staticmethod
    def _to_domain(record: ReferralRewardRecord) -> ReferralRewardEntry:
        return ReferralRewardEntry(
            id=record.id,
            referrer_id=record.referrer_id,
            triggered_by_user_id=record.triggered_by_user_id,
            coins=record.coins,
            invites_consumed=record.invites_consumed,
            created_at=record.created_at,
        )
