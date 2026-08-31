from datetime import timedelta

import pytest

from core.timezone import tehran_now
from models.user import RegistrationStatus, User, UserStatus
from repositories.user import UserRepository


@pytest.mark.asyncio
async def test_user_repository_crud_and_counts(session):
    repository = UserRepository(session)
    now = tehran_now()

    created = await repository.create(
        User(
            telegram_id=1,
            telegram_name="One",
            username="one",
            registration_status=RegistrationStatus.REGISTERED,
            last_seen_at=now,
        )
    )
    await repository.create(
        User(
            telegram_id=2,
            telegram_name="Two",
            status=UserStatus.BLOCKED,
            last_seen_at=now - timedelta(days=40),
        )
    )
    await repository.create(
        User(
            telegram_id=3,
            telegram_name="Three",
            last_seen_at=now - timedelta(days=2),
        )
    )

    assert created.telegram_id == 1
    assert await repository.exists(1) is True
    assert await repository.exists(999) is False
    assert (await repository.get_by_telegram_id(1)).username == "one"
    assert await repository.count() == 3
    assert await repository.count_registered() == 1
    assert await repository.count_unregistered() == 2
    assert await repository.count_blocked() == 1
    assert await repository.count_active() == 2

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    assert await repository.count_active_today(today_start) == 1
    assert await repository.count_active_last_7_days(today_start - timedelta(days=7)) == 2
    assert await repository.count_inactive_30_days(today_start - timedelta(days=30)) == 1


@pytest.mark.asyncio
async def test_user_repository_update_lists_filters_and_delete(session):
    repository = UserRepository(session)
    for telegram_id in (10, 20, 30):
        await repository.create(User(telegram_id=telegram_id, telegram_name=str(telegram_id)))

    user = await repository.get_by_telegram_id(20)
    assert user is not None
    user.name = "Updated"
    user.coins = 7
    user.status = UserStatus.BLOCKED
    updated = await repository.update(user)

    assert updated is not None
    assert updated.name == "Updated"
    assert updated.coins == 7
    assert [u.telegram_id for u in await repository.list_all()] == [10, 20, 30]
    assert [u.telegram_id for u in await repository.list_page(offset=1, limit=1)] == [20]
    assert await repository.list_active_telegram_ids() == [10, 30]
    assert [u.telegram_id for u in await repository.list_blocked_page(offset=0, limit=10)] == [20]

    assert await repository.delete(20) is True
    assert await repository.delete(20) is False
    assert await repository.get_by_telegram_id(20) is None


@pytest.mark.asyncio
async def test_user_repository_registered_only_filter_and_missing_update(session):
    repository = UserRepository(session)
    await repository.create(
        User(
            telegram_id=1,
            telegram_name="Registered",
            registration_status=RegistrationStatus.REGISTERED,
        )
    )
    await repository.create(User(telegram_id=2, telegram_name="Unregistered"))

    assert await repository.list_active_telegram_ids(registered_only=True) == [1]
    assert await repository.update(User(telegram_id=999, telegram_name="Missing")) is None
