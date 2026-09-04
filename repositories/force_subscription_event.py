from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.force_subscription_event import ForceSubscriptionMembershipEvent
from models.force_subscription_db import ForceSubscriptionMembershipEventRecord
from repositories.interfaces.force_subscription_event import IForceSubscriptionEventRepository


class ForceSubscriptionEventRepository(IForceSubscriptionEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, event: ForceSubscriptionMembershipEvent
    ) -> ForceSubscriptionMembershipEvent:
        record = ForceSubscriptionMembershipEventRecord(
            user_telegram_id=event.user_telegram_id,
            target_chat_id=event.target_chat_id,
            created_at=event.created_at,
        )
        self._session.add(record)
        await self._session.flush()
        return ForceSubscriptionMembershipEvent(
            id=record.id,
            user_telegram_id=record.user_telegram_id,
            target_chat_id=record.target_chat_id,
            created_at=record.created_at,
        )

    async def count_total(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(ForceSubscriptionMembershipEventRecord)
        )
        return result.scalar_one()

    async def count_since(self, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ForceSubscriptionMembershipEventRecord)
            .where(ForceSubscriptionMembershipEventRecord.created_at >= since)
        )
        return result.scalar_one()

    async def count_target_total(self, target_chat_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ForceSubscriptionMembershipEventRecord)
            .where(ForceSubscriptionMembershipEventRecord.target_chat_id == target_chat_id)
        )
        return result.scalar_one()

    async def count_target_since(self, target_chat_id: int, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ForceSubscriptionMembershipEventRecord)
            .where(
                ForceSubscriptionMembershipEventRecord.target_chat_id == target_chat_id,
                ForceSubscriptionMembershipEventRecord.created_at >= since,
            )
        )
        return result.scalar_one()
