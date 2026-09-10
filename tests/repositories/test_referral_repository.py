from datetime import datetime

import pytest

from core.timezone import tehran_now
from models.user import RegistrationStatus, User
from repositories.referral import ReferralRepository
from repositories.user import UserRepository


def make_user(telegram_id: int, referral_code: str | None = None) -> User:
    return User(
        telegram_id=telegram_id,
        telegram_name=f"User {telegram_id}",
        referral_code=referral_code,
    )


def make_processed_at() -> datetime:
    """Return a timestamp the referral column can store unchanged.

    ``referral_processed_at`` is a MySQL ``DATETIME`` column: it has no
    fractional-second precision and no time zone. MySQL rounds fractional
    seconds away on insert and SQLAlchemy reads the value back naive, so an
    aware, microsecond-precision datetime never survives the round trip
    unchanged. Passing a whole-second, timezone-naive value keeps the exact
    equality assertions meaningful and driver-independent.
    """
    return tehran_now().replace(microsecond=0, tzinfo=None)


@pytest.mark.asyncio
async def test_repository_finds_referrer_by_unique_code(session):
    user_repository = UserRepository(session)
    referral_repository = ReferralRepository(session)
    await user_repository.create(make_user(1, "ref_owner"))

    found = await referral_repository.find_user_by_referral_code("ref_owner")

    assert found is not None
    assert found.telegram_id == 1


@pytest.mark.asyncio
async def test_repository_claims_referral_atomically_and_only_once(session):
    user_repository = UserRepository(session)
    referral_repository = ReferralRepository(session)
    await user_repository.create(make_user(1, "ref_owner"))
    await user_repository.create(make_user(2))

    processed_at = make_processed_at()
    assert await referral_repository.claim_referral(2, 1, processed_at) is True
    assert await referral_repository.claim_referral(2, 1, processed_at) is False

    user = await user_repository.get_by_telegram_id(2)
    assert user is not None
    assert user.referred_by_user_id == 1
    assert user.referral_processed_at == processed_at


@pytest.mark.asyncio
async def test_repository_can_lock_invalid_referral_without_assignment(session):
    user_repository = UserRepository(session)
    referral_repository = ReferralRepository(session)
    await user_repository.create(make_user(2))

    processed_at = make_processed_at()
    assert await referral_repository.mark_referral_processed(2, processed_at) is True
    assert await referral_repository.mark_referral_processed(2, processed_at) is False

    user = await user_repository.get_by_telegram_id(2)
    assert user is not None
    assert user.referred_by_user_id is None
    assert user.referral_processed_at == processed_at


@pytest.mark.asyncio
async def test_repository_counts_and_lists_referrals(session):
    user_repository = UserRepository(session)
    referral_repository = ReferralRepository(session)
    await user_repository.create(make_user(1, "ref_owner"))
    for telegram_id in (2, 3, 4):
        user = make_user(telegram_id)
        user.referred_by_user_id = 1
        await user_repository.create(user)

    assert await referral_repository.count_referrals(1) == 3
    users = await referral_repository.list_referrals(1, offset=1, limit=1)
    assert [user.telegram_id for user in users] == [3]


@pytest.mark.asyncio
async def test_repository_referral_statistics_counts_and_ranks_top_referrers(session):
    user_repository = UserRepository(session)
    referral_repository = ReferralRepository(session)
    await user_repository.create(make_user(1, "ref_owner"))
    await user_repository.create(make_user(2, "ref_second"))
    await user_repository.create(make_user(5))

    processed_at = make_processed_at()
    for telegram_id, referrer_id in ((3, 1), (4, 1), (6, 2)):
        user = make_user(telegram_id)
        user.referred_by_user_id = referrer_id
        user.referral_processed_at = processed_at
        await user_repository.create(user)

    # Referred user 3 completes registration; users 4 and 6 do not.
    registered = await user_repository.get_by_telegram_id(3)
    assert registered is not None
    registered.registration_status = RegistrationStatus.REGISTERED
    await user_repository.update(registered)

    assert await referral_repository.count_referrals_total() == 3
    assert await referral_repository.count_referred_registered() == 1
    assert await referral_repository.count_users_with_referral_code() == 2
    assert await referral_repository.count_referrals_since(processed_at) == 3

    top_referrers = await referral_repository.top_referrers(limit=5)
    assert [(user.telegram_id, count) for user, count in top_referrers] == [
        (1, 2),
        (2, 1),
    ]

    # A user processed without a referral claim must stay out of every window.
    orphan = make_user(7)
    orphan.referral_processed_at = processed_at
    await user_repository.create(orphan)
    assert await referral_repository.count_referrals_total() == 3
    assert await referral_repository.count_referrals_since(processed_at) == 3
