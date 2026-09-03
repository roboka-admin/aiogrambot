from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from models.force_subscription_db import ForceSubscriptionTargetRecord
from repositories.interfaces.force_subscription import IForceSubscriptionRepository


class ForceSubscriptionRepository(IForceSubscriptionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, chat_id: int) -> ForceSubscriptionTarget | None:
        result = await self._session.execute(
            select(ForceSubscriptionTargetRecord).where(
                ForceSubscriptionTargetRecord.chat_id == chat_id
            )
        )
        record = result.scalar_one_or_none()
        return None if record is None else self._to_domain(record)

    async def list_active(self) -> list[ForceSubscriptionTarget]:
        result = await self._session.execute(
            select(ForceSubscriptionTargetRecord)
            .where(ForceSubscriptionTargetRecord.is_active.is_(True))
            .order_by(ForceSubscriptionTargetRecord.created_at, ForceSubscriptionTargetRecord.chat_id)
        )
        return [self._to_domain(record) for record in result.scalars().all()]

    async def list_all(self) -> list[ForceSubscriptionTarget]:
        result = await self._session.execute(
            select(ForceSubscriptionTargetRecord).order_by(
                ForceSubscriptionTargetRecord.created_at,
                ForceSubscriptionTargetRecord.chat_id,
            )
        )
        return [self._to_domain(record) for record in result.scalars().all()]

    async def create(self, target: ForceSubscriptionTarget) -> ForceSubscriptionTarget:
        record = ForceSubscriptionTargetRecord(
            chat_id=target.chat_id,
            title=target.title,
            target_type=target.target_type.value,
            username=target.username,
            invite_link=target.invite_link,
            is_active=target.is_active,
            created_at=target.created_at,
            updated_at=target.updated_at,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def update(self, target: ForceSubscriptionTarget) -> ForceSubscriptionTarget:
        record = await self._get_record(target.chat_id)
        if record is None:
            return await self.create(target)

        record.title = target.title
        record.target_type = target.target_type.value
        record.username = target.username
        record.invite_link = target.invite_link
        record.is_active = target.is_active
        record.updated_at = target.updated_at
        await self._session.flush()
        return self._to_domain(record)

    async def delete(self, chat_id: int) -> bool:
        result = await self._session.execute(
            delete(ForceSubscriptionTargetRecord).where(
                ForceSubscriptionTargetRecord.chat_id == chat_id
            )
        )
        await self._session.flush()
        return result.rowcount > 0

    async def _get_record(self, chat_id: int) -> ForceSubscriptionTargetRecord | None:
        result = await self._session.execute(
            select(ForceSubscriptionTargetRecord).where(
                ForceSubscriptionTargetRecord.chat_id == chat_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_domain(record: ForceSubscriptionTargetRecord) -> ForceSubscriptionTarget:
        return ForceSubscriptionTarget(
            chat_id=record.chat_id,
            title=record.title,
            target_type=ForceSubscriptionTargetType(record.target_type),
            username=record.username,
            invite_link=record.invite_link,
            is_active=record.is_active,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
