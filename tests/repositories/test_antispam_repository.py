from datetime import timedelta

import pytest

from core.timezone import tehran_now
from models.antispam import AntiSpamEvent, AntiSpamEventType
from repositories.antispam import AntiSpamRepository


@pytest.mark.asyncio
async def test_antispam_repository_create_and_counts(session):
    repository = AntiSpamRepository(session)
    now = tehran_now()

    warning_today = await repository.create(
        AntiSpamEvent(
            id=None,
            user_telegram_id=1,
            event_type=AntiSpamEventType.WARNING,
            created_at=now,
        )
    )
    await repository.create(
        AntiSpamEvent(
            id=None,
            user_telegram_id=2,
            event_type=AntiSpamEventType.WARNING,
            created_at=now - timedelta(days=2),
        )
    )
    block_old = await repository.create(
        AntiSpamEvent(
            id=None,
            user_telegram_id=1,
            event_type=AntiSpamEventType.BLOCK,
            created_at=now - timedelta(days=40),
        )
    )

    assert warning_today.id is not None
    assert warning_today.event_type == AntiSpamEventType.WARNING
    assert block_old.event_type == AntiSpamEventType.BLOCK
    assert await repository.count_total_warnings() == 2
    assert await repository.count_total_blocks() == 1

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    assert await repository.count_today(today_start) == 1
    assert await repository.count_last_7_days(today_start - timedelta(days=7)) == 2
    assert await repository.count_last_30_days(today_start - timedelta(days=30)) == 2


@pytest.mark.asyncio
async def test_antispam_repository_empty_counts_are_zero(session):
    repository = AntiSpamRepository(session)
    now = tehran_now()
    assert await repository.count_total_warnings() == 0
    assert await repository.count_total_blocks() == 0
    assert await repository.count_today(now) == 0
