from models.support import SupportStatus, SupportTicket, SupportUserSummary
from repositories.interfaces.support import ISupportRepository


class SupportService:
    def __init__(self, *, support_repository: ISupportRepository) -> None:
        self._support_repository = support_repository

    async def create_ticket(self, *, user_telegram_id: int, message: str) -> SupportTicket:
        message = message.strip()
        if not message:
            raise ValueError("Support message cannot be empty")
        return await self._support_repository.create(SupportTicket(id=None, user_telegram_id=user_telegram_id, message=message))

    async def get_ticket(self, ticket_id: int) -> SupportTicket | None:
        return await self._support_repository.get_by_id(ticket_id)

    async def get_user_tickets(self, telegram_id: int) -> list[SupportTicket]:
        return await self._support_repository.list_by_user(telegram_id)

    async def get_user_tickets_by_status(self, telegram_id: int, status: SupportStatus) -> list[SupportTicket]:
        return await self._support_repository.list_by_user_and_status(telegram_id, status)

    async def get_tickets_by_status(self, status: SupportStatus) -> list[SupportTicket]:
        return await self._support_repository.list_by_status(status)

    async def get_support_users_by_status(self, status: SupportStatus) -> list[SupportUserSummary]:
        return await self._support_repository.list_user_summaries_by_status(status)

    async def close_ticket(self, ticket_id: int) -> SupportTicket | None:
        ticket = await self._support_repository.get_by_id(ticket_id)
        if ticket is None:
            return None
        ticket.status = SupportStatus.CLOSED
        return await self._support_repository.update(ticket)
