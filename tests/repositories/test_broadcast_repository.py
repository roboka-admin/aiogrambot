from datetime import timedelta

import pytest

from core.timezone import tehran_now
from models.broadcast import BroadcastRecord
from repositories.broadcast import BroadcastRepository


@pytest.mark.asyncio
async def test_broadcast_repository_create_latest_and_counts(session):
    repository = BroadcastRepository(session)
    now = tehran_now()

    old = await repository.create(
        BroadcastRecord(
            id=None,
            total_recipients=10,
            success_count=9,
            failed_count=1,
            duration_seconds=3,
            created_at=now - timedelta(days=40),
        )
    )
    recent = await repository.create(
        BroadcastRecord(
            id=None,
            total_recipients=20,
            success_count=18,
            failed_count=2,
            duration_seconds=5,
            created_at=now - timedelta(days=2),
        )
    )
    latest = await repository.create(
        BroadcastRecord(
            id=None,
            total_recipients=30,
            success_count=30,
            failed_count=0,
            duration_seconds=7,
            created_at=now,
        )
    )

    assert old.id is not None
    assert recent.id is not None
    assert latest.id is not None
    assert (await repository.get_latest()).id == latest.id
    assert await repository.count_total() == 3

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    assert await repository.count_today(today_start) == 1
    assert await repository.count_last_7_days(today_start - timedelta(days=7)) == 2
    assert await repository.count_last_30_days(today_start - timedelta(days=30)) == 2


@pytest.mark.asyncio
async def test_broadcast_repository_latest_is_none_when_empty(session):
    repository = BroadcastRepository(session)
    assert await repository.get_latest() is None
    assert await repository.count_total() == 0
