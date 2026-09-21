from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.timezone import tehran_now
from models.event_counter_db import EventCounterRecord
from repositories.interfaces.event_counter import IEventCounterRepository


class EventCounterRepository(IEventCounterRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, kind: str, amount: int) -> None:
        if amount <= 0:
            return
        statement = insert(EventCounterRecord).values(
            kind=kind, archived_count=amount, updated_at=tehran_now()
        )
        statement = statement.on_duplicate_key_update(
            archived_count=EventCounterRecord.archived_count + amount,
            updated_at=statement.inserted.updated_at,
        )
        await self._session.execute(statement)

    async def get(self, kind: str) -> int:
        result = await self._session.execute(
            select(EventCounterRecord.archived_count).where(EventCounterRecord.kind == kind)
        )
        return int(result.scalar_one_or_none() or 0)
