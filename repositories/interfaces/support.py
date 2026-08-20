from typing import Protocol

from models.support import SupportStatus, SupportTicket


class ISupportRepository(Protocol):
    """Abstraction for support ticket persistence."""

    async def create(self, ticket: SupportTicket) -> SupportTicket:
        ...

    async def get_by_id(self, ticket_id: int) -> SupportTicket | None:
        ...

    async def list_by_user(
        self,
        telegram_id: int,
    ) -> list[SupportTicket]:
        ...

    async def list_by_status(
        self,
        status: SupportStatus,
    ) -> list[SupportTicket]:
        ...

    async def update(self, ticket: SupportTicket) -> SupportTicket | None:
        ...
