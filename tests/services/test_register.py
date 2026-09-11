from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.user import UserAlreadyExistsError
from models.user import RegistrationStatus, User
from services.referral import ReferralReward
from services.register import RegisterService


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self.users.get(telegram_id)

    async def update(self, user: User) -> User | None:
        if user.telegram_id not in self.users:
            return None
        self.users[user.telegram_id] = user
        return user


def make_referral_service(reward: ReferralReward | None = None) -> MagicMock:
    service = MagicMock()
    service.reward_referrer_for_registration = AsyncMock(return_value=reward)
    return service


@pytest.mark.asyncio
async def test_register_completes_registration():
    repository = FakeUserRepository()
    repository.users[123] = User(telegram_id=123, telegram_name="Telegram User")
    service = RegisterService(
        user_repository=repository, referral_service=make_referral_service()
    )

    result = await service.register(telegram_id=123, name=" Ali ", age=28)

    assert result.user.name == "Ali"
    assert result.user.age == 28
    assert result.user.registration_status == RegistrationStatus.REGISTERED
    assert result.referral_reward is None


@pytest.mark.asyncio
async def test_register_returns_referral_reward_when_paid():
    repository = FakeUserRepository()
    repository.users[123] = User(
        telegram_id=123, telegram_name="Telegram User", referred_by_user_id=7
    )
    reward = ReferralReward(referrer_id=7, coins=5, balance=15, registered_referrals=3)
    referral_service = make_referral_service(reward)
    service = RegisterService(user_repository=repository, referral_service=referral_service)

    result = await service.register(telegram_id=123, name="Ali", age=28)

    assert result.referral_reward is reward
    referral_service.reward_referrer_for_registration.assert_awaited_once_with(
        registered_user=result.user
    )


@pytest.mark.asyncio
async def test_register_rejects_already_registered_user():
    repository = FakeUserRepository()
    repository.users[123] = User(
        telegram_id=123,
        telegram_name="Telegram User",
        registration_status=RegistrationStatus.REGISTERED,
    )
    referral_service = make_referral_service()
    service = RegisterService(user_repository=repository, referral_service=referral_service)

    with pytest.raises(UserAlreadyExistsError):
        await service.register(telegram_id=123, name="Ali", age=28)
    referral_service.reward_referrer_for_registration.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_requires_tracked_user():
    service = RegisterService(
        user_repository=FakeUserRepository(), referral_service=make_referral_service()
    )
    with pytest.raises(RuntimeError):
        await service.register(telegram_id=999, name="Ali", age=28)


class RecordingTransactionManager:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    @asynccontextmanager
    async def transaction(self):
        self.events.append("db:begin")
        try:
            yield
        finally:
            self.events.append("db:end")


@pytest.mark.asyncio
async def test_referral_reward_is_paid_inside_registration_transaction():
    """The payout must run between begin and end of the *registration* transaction.

    That is what makes registration + reward atomic: with the real
    SessionTransactionManager the nested call reuses this transaction, so a
    failure in either step rolls back both.
    """
    events: list[str] = []
    repository = FakeUserRepository()
    repository.users[123] = User(
        telegram_id=123, telegram_name="Telegram User", referred_by_user_id=7
    )

    referral_service = MagicMock()

    async def _reward(*, registered_user: User) -> None:
        events.append("reward")
        return None

    referral_service.reward_referrer_for_registration = AsyncMock(side_effect=_reward)
    service = RegisterService(
        user_repository=repository,
        referral_service=referral_service,
        transaction_manager=RecordingTransactionManager(events),
    )

    await service.register(telegram_id=123, name="Ali", age=28)

    assert events == ["db:begin", "reward", "db:end"]


@pytest.mark.asyncio
async def test_reward_failure_propagates_so_registration_rolls_back():
    """An exception from the payout must escape register() (→ rollback), not be swallowed."""
    repository = FakeUserRepository()
    repository.users[123] = User(
        telegram_id=123, telegram_name="Telegram User", referred_by_user_id=7
    )
    referral_service = MagicMock()
    referral_service.reward_referrer_for_registration = AsyncMock(
        side_effect=RuntimeError("db down")
    )
    service = RegisterService(user_repository=repository, referral_service=referral_service)

    with pytest.raises(RuntimeError, match="db down"):
        await service.register(telegram_id=123, name="Ali", age=28)
