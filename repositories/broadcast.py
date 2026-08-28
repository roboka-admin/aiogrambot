from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.broadcast import BroadcastRecord
from models.broadcast_db import BroadcastRecordRecord
from repositories.interfaces.broadcast import IBroadcastRepository


class BroadcastRepository(IBroadcastRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: BroadcastRecord) -> BroadcastRecord:
        db_record = BroadcastRecordRecord(
            total_recipients=record.total_recipients,
            success_count=record.success_count,
            failed_count=record.failed_count,
            duration_seconds=record.duration_seconds,
            created_at=record.created_at,
        )
        self._session.add(db_record)
        await self._session.flush()
        return self._to_domain(db_record)

    async def get_latest(self) -> BroadcastRecord | None:
        result = await self._session.execute(
            select(BroadcastRecordRecord)
            .order_by(
                BroadcastRecordRecord.created_at.desc(),
                BroadcastRecordRecord.id.desc(),
            )
            .limit(1)
        )
        db_record = result.scalar_one_or_none()
        return None if db_record is None else self._to_domain(db_record)

    async def count_total(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(BroadcastRecordRecord)
        )
        return result.scalar_one()

    async def count_today(self, today_start: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(BroadcastRecordRecord)
            .where(BroadcastRecordRecord.created_at >= today_start)
        )
        return result.scalar_one()

    async def count_last_7_days(self, seven_days_ago: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(BroadcastRecordRecord)
            .where(BroadcastRecordRecord.created_at >= seven_days_ago)
        )
        return result.scalar_one()

    async def count_last_30_days(self, thirty_days_ago: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(BroadcastRecordRecord)
            .where(BroadcastRecordRecord.created_at >= thirty_days_ago)
        )
        return result.scalar_one()

    @staticmethod
    def _to_domain(record: BroadcastRecordRecord) -> BroadcastRecord:
        return BroadcastRecord(
            id=record.id,
            total_recipients=record.total_recipients,
            success_count=record.success_count,
            failed_count=record.failed_count,
            duration_seconds=record.duration_seconds,
            created_at=record.created_at,
        )
