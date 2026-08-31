from datetime import timedelta

import pytest

from core.timezone import tehran_now
from models.support import SupportStatus, SupportTicket
from repositories.support import SupportRepository


@pytest.mark.asyncio
async def test_support_repository_crud_filters_and_summaries(session):
    repository = SupportRepository(session)
    first = await repository.create(SupportTicket(id=None, user_telegram_id=1, message="One"))
    second = await repository.create(SupportTicket(id=None, user_telegram_id=1, message="Two"))
    third = await repository.create(SupportTicket(id=None, user_telegram_id=2, message="Three"))

    second.status = SupportStatus.CLOSED
    await repository.update(second)

    assert (await repository.get_by_id(first.id)).message == "One"
    assert [t.id for t in await repository.list_by_user(1)] == [first.id, second.id]
    assert [t.id for t in await repository.list_by_user_and_status(1, SupportStatus.OPEN)] == [first.id]
    assert [t.id for t in await repository.list_by_status(SupportStatus.OPEN)] == [first.id, third.id]

    summaries = await repository.list_user_summaries_by_status(SupportStatus.OPEN)
    summary_map = {item.user_telegram_id: item.ticket_count for item in summaries}
    assert summary_map == {1: 1, 2: 1}


@pytest.mark.asyncio
async def test_support_repository_bulk_updates_deletes_and_counts(session):
    repository = SupportRepository(session)
    now = tehran_now()
    await repository.create(
        SupportTicket(id=None, user_telegram_id=1, message="Today", created_at=now)
    )
    await repository.create(
        SupportTicket(id=None, user_telegram_id=1, message="Old", created_at=now - timedelta(days=40))
    )
    await repository.create(
        SupportTicket(id=None, user_telegram_id=2, message="Other", created_at=now - timedelta(days=2))
    )

    assert await repository.count_total() == 3
    assert await repository.count_by_status(SupportStatus.OPEN) == 3

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    assert await repository.count_today(today_start) == 1
    assert await repository.count_last_7_days(today_start - timedelta(days=7)) == 2
    assert await repository.count_last_30_days(today_start - timedelta(days=30)) == 2

    assert await repository.update_user_status(1, SupportStatus.CLOSED) == 2
    assert await repository.count_by_status(SupportStatus.CLOSED) == 2
    assert await repository.delete_by_status(SupportStatus.CLOSED) == 2
    assert await repository.delete_all() == 1
    assert await repository.count_total() == 0


@pytest.mark.asyncio
async def test_support_repository_update_validation_and_missing_ticket(session):
    repository = SupportRepository(session)

    with pytest.raises(ValueError):
        await repository.update(SupportTicket(id=None, user_telegram_id=1, message="No id"))

    missing = SupportTicket(id=999, user_telegram_id=1, message="Missing")
    assert await repository.update(missing) is None
    assert await repository.get_by_id(999) is None
