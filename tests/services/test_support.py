import asyncio

from models.support import SupportStatus
from services.support import SupportService


class FakeSupportRepository:
    def __init__(self) -> None:
        self.tickets = {}
        self.next_id = 1

    async def create(self, ticket):
        ticket.id = self.next_id
        self.next_id += 1
        self.tickets[ticket.id] = ticket
        return ticket

    async def get_by_id(self, ticket_id):
        return self.tickets.get(ticket_id)

    async def list_by_user(self, telegram_id):
        return [t for t in self.tickets.values() if t.user_telegram_id == telegram_id]

    async def list_by_user_and_status(self, telegram_id, status):
        return [t for t in await self.list_by_user(telegram_id) if t.status == status]

    async def list_by_status(self, status):
        return [t for t in self.tickets.values() if t.status == status]

    async def list_user_summaries_by_status(self, status):
        return []

    async def update(self, ticket):
        self.tickets[ticket.id] = ticket
        return ticket

    async def update_user_status(self, telegram_id, status):
        count = 0
        for ticket in self.tickets.values():
            if ticket.user_telegram_id == telegram_id and ticket.status != status:
                ticket.status = status
                count += 1
        return count

    async def delete_by_status(self, status):
        ids = [i for i, t in self.tickets.items() if t.status == status]
        for i in ids:
            del self.tickets[i]
        return len(ids)

    async def delete_all(self):
        count = len(self.tickets)
        self.tickets.clear()
        return count

    async def count_total(self):
        return len(self.tickets)

    async def count_by_status(self, status):
        return sum(t.status == status for t in self.tickets.values())

    async def count_today(self, today_start):
        return sum(t.created_at >= today_start for t in self.tickets.values())

    async def count_last_7_days(self, start):
        return sum(t.created_at >= start for t in self.tickets.values())

    async def count_last_30_days(self, start):
        return sum(t.created_at >= start for t in self.tickets.values())


def make_service() -> SupportService:
    return SupportService(support_repository=FakeSupportRepository())


def test_create_ticket_rejects_empty_message():
    async def scenario() -> None:
        service = make_service()
        try:
            await service.create_ticket(user_telegram_id=1, message="   ")
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError")

    asyncio.run(scenario())


def test_create_and_close_ticket():
    async def scenario() -> None:
        service = make_service()
        ticket = await service.create_ticket(user_telegram_id=1, message="  Help me  ")
        assert ticket.message == "Help me"
        assert ticket.status == SupportStatus.OPEN

        closed = await service.close_ticket(ticket.id)
        assert closed is not None
        assert closed.status == SupportStatus.CLOSED

    asyncio.run(scenario())
