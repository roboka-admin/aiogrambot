from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.antispam import AntiSpamEvent, AntiSpamEventType
from models.antispam_db import AntiSpamEventRecord
from repositories.interfaces.antispam import IAntiSpamRepository


class AntiSpamRepository(IAntiSpamRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, event: AntiSpamEvent) -> AntiSpamEvent:
        record = AntiSpamEventRecord(
            user_telegram_id=event.user_telegram_id,
            event_type=event.event_type,
            created_at=event.created_at,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def count_total_warnings(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(AntiSpamEventRecord)
            .where(AntiSpamEventRecord.event_type == AntiSpamEventType.WARNING)
        )
        return result.scalar_one()

    async def count_total_blocks(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(AntiSpamEventRecord)
            .where(AntiSpamEventRecord.event_type == AntiSpamEventType.BLOCK)
        )
        return result.scalar_one()

    async def count_today(self, today_start: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(AntiSpamEventRecord)
            .where(AntiSpamEventRecord.created_at >= today_start)
        )
        return result.scalar_one()

    async def count_last_7_days(self, seven_days_ago: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(AntiSpamEventRecord)
            .where(AntiSpamEventRecord.created_at >= seven_days_ago)
        )
        return result.scalar_one()

    async def count_last_30_days(self, thirty_days_ago: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(AntiSpamEventRecord)
            .where(AntiSpamEventRecord.created_at >= thirty_days_ago)
        )
        return result.scalar_one()

    @staticmethod
    def _to_domain(record: AntiSpamEventRecord) -> AntiSpamEvent:
        return AntiSpamEvent(
            id=record.id,
            user_telegram_id=record.user_telegram_id,
            event_type=AntiSpamEventType(record.event_type),
            created_at=record.created_at,
        )
