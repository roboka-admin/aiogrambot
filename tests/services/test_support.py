from datetime import timedelta

import pytest

from core.timezone import tehran_now
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


@pytest.fixture
def service_and_repository() -> tuple[SupportService, FakeSupportRepository]:
    repository = FakeSupportRepository()
    return SupportService(support_repository=repository), repository


@pytest.mark.asyncio
async def test_create_ticket_rejects_empty_message(service_and_repository):
    service, _ = service_and_repository
    with pytest.raises(ValueError):
        await service.create_ticket(user_telegram_id=1, message="   ")


@pytest.mark.asyncio
async def test_create_get_and_filter_tickets(service_and_repository):
    service, _ = service_and_repository
    first = await service.create_ticket(user_telegram_id=1, message="  Help me  ")
    second = await service.create_ticket(user_telegram_id=1, message="Second")
    third = await service.create_ticket(user_telegram_id=2, message="Other")
    await service.close_ticket(second.id)

    assert first.message == "Help me"
    assert await service.get_ticket(first.id) is first
    assert [t.id for t in await service.get_user_tickets(1)] == [first.id, second.id]
    assert [t.id for t in await service.get_user_tickets_by_status(1, SupportStatus.OPEN)] == [first.id]
    assert [t.id for t in await service.get_tickets_by_status(SupportStatus.OPEN)] == [first.id, third.id]


@pytest.mark.asyncio
async def test_close_missing_ticket_returns_none(service_and_repository):
    service, _ = service_and_repository
    assert await service.close_ticket(999) is None


@pytest.mark.asyncio
async def test_close_and_reopen_user_conversation(service_and_repository):
    service, _ = service_and_repository
    await service.create_ticket(user_telegram_id=1, message="One")
    await service.create_ticket(user_telegram_id=1, message="Two")

    assert await service.close_user_conversation(1) == 2
    assert len(await service.get_user_tickets_by_status(1, SupportStatus.CLOSED)) == 2
    assert await service.reopen_user_conversation(1) == 2
    assert len(await service.get_user_tickets_by_status(1, SupportStatus.OPEN)) == 2


@pytest.mark.asyncio
async def test_delete_closed_and_all_tickets(service_and_repository):
    service, repository = service_and_repository
    first = await service.create_ticket(user_telegram_id=1, message="One")
    await service.create_ticket(user_telegram_id=1, message="Two")
    await service.close_ticket(first.id)

    assert await service.delete_closed_tickets() == 1
    assert len(repository.tickets) == 1
    assert await service.delete_all_tickets() == 1
    assert repository.tickets == {}


@pytest.mark.asyncio
async def test_support_statistics_count_status_and_time_windows(service_and_repository):
    service, _ = service_and_repository
    today = await service.create_ticket(user_telegram_id=1, message="Today")
    old = await service.create_ticket(user_telegram_id=2, message="Old")
    old.created_at = tehran_now() - timedelta(days=40)
    await service.close_ticket(today.id)

    stats = await service.get_support_statistics()

    assert stats["total"] == 2
    assert stats["open"] == 1
    assert stats["closed"] == 1
    assert stats["today"] == 1
    assert stats["last_7_days"] == 1
    assert stats["last_30_days"] == 1
