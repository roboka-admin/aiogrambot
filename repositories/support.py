from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.support import SupportStatus, SupportTicket
from models.support_db import SupportTicketRecord
from repositories.interfaces.support import ISupportRepository


class SupportRepository(ISupportRepository):
    """SQLAlchemy repository for support ticket persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, ticket: SupportTicket) -> SupportTicket:
        record = SupportTicketRecord(
            user_telegram_id=ticket.user_telegram_id,
            message=ticket.message,
            status=ticket.status.value,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def get_by_id(self, ticket_id: int) -> SupportTicket | None:
        record = await self._session.get(SupportTicketRecord, ticket_id)
        return None if record is None else self._to_domain(record)

    async def list_by_user(
        self,
        telegram_id: int,
    ) -> list[SupportTicket]:
        result = await self._session.execute(
            select(SupportTicketRecord)
            .where(SupportTicketRecord.user_telegram_id == telegram_id)
            .order_by(SupportTicketRecord.id.desc())
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def list_by_status(
        self,
        status: SupportStatus,
    ) -> list[SupportTicket]:
        result = await self._session.execute(
            select(SupportTicketRecord)
            .where(SupportTicketRecord.status == status.value)
            .order_by(SupportTicketRecord.id.asc())
        )
        return [self._to_domain(record) for record in result.scalars()]

    async def update(self, ticket: SupportTicket) -> SupportTicket | None:
        if ticket.id is None:
            raise ValueError("Ticket id is required for update")

        record = await self._session.get(SupportTicketRecord, ticket.id)
        if record is None:
            return None

        record.message = ticket.message
        record.status = ticket.status.value
        await self._session.flush()
        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: SupportTicketRecord) -> SupportTicket:
        return SupportTicket(
            id=record.id,
            user_telegram_id=record.user_telegram_id,
            message=record.message,
            status=SupportStatus(record.status),
        )
