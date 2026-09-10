from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.referral_reward import ReferralRewardEntry
from models.referral_reward_db import ReferralRewardRecord
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
