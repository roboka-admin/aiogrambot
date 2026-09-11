from datetime import timedelta

import pytest

from core.timezone import tehran_now
from models.referral_reward import ReferralRewardEntry
from models.user import User
from repositories.referral_reward import ReferralRewardRepository
from repositories.user import UserRepository


def make_entry(referrer_id: int, *, coins: int, invites: int, triggered_by: int = 99):
    return ReferralRewardEntry(
        id=None,
        referrer_id=referrer_id,
        triggered_by_user_id=triggered_by,
        coins=coins,
        invites_consumed=invites,
        created_at=tehran_now().replace(microsecond=0, tzinfo=None),
    )


@pytest.mark.asyncio
async def test_referral_reward_repository_sums_and_counts(session):
    repository = ReferralRewardRepository(session)

    assert await repository.sum_invites_consumed(1) == 0
    assert await repository.sum_coins(1) == 0
    assert await repository.sum_coins_total() == 0
    assert await repository.count_total() == 0

    created = await repository.create(make_entry(1, coins=5, invites=3, triggered_by=10))
    await repository.create(make_entry(1, coins=5, invites=3, triggered_by=11))
    await repository.create(make_entry(2, coins=1, invites=1, triggered_by=12))

    assert created.id is not None
    assert await repository.sum_invites_consumed(1) == 6
    assert await repository.sum_coins(1) == 10
    assert await repository.sum_invites_consumed(2) == 1
    assert await repository.sum_coins_total() == 11
    assert await repository.count_total() == 3
    assert await repository.count_since(tehran_now() - timedelta(minutes=1)) == 3
    assert await repository.count_since(tehran_now() + timedelta(days=1)) == 0


@pytest.mark.asyncio
async def test_referral_reward_repository_lists_most_recent_first(session):
    repository = ReferralRewardRepository(session)
    for triggered_by in (10, 11, 12):
        await repository.create(make_entry(1, coins=1, invites=1, triggered_by=triggered_by))

    recent = await repository.list_recent(limit=2)

    assert [entry.triggered_by_user_id for entry in recent] == [12, 11]


@pytest.mark.asyncio
async def test_referral_reward_repository_history_resolves_names_and_tolerates_missing_users(
    session,
):
    users = UserRepository(session)
    # Referrer has a registered name; the triggered user only has a Telegram name.
    await users.create(User(telegram_id=1, telegram_name="Referrer TG", name="Ali"))
    await users.create(User(telegram_id=10, telegram_name="Sara TG"))
    repository = ReferralRewardRepository(session)
    await repository.create(make_entry(1, coins=5, invites=3, triggered_by=10))
    # Payout for a user that no longer exists in the users table.
    await repository.create(make_entry(999, coins=1, invites=1, triggered_by=998))

    history = await repository.list_recent_with_names(limit=10)

    assert len(history) == 2
    orphan, named = history  # most recent first
    assert orphan.entry.referrer_id == 999
    assert (orphan.referrer_name, orphan.triggered_by_name) == (None, None)
    assert named.referrer_name == "Ali"
    assert named.triggered_by_name == "Sara TG"
