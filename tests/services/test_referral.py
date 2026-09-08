import pytest

from models.user import User
from services.referral import ReferralService


class FakeReferralRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}
        self.codes: dict[str, int] = {}

    async def get_referral_code(self, telegram_id: int) -> str | None:
        user = self.users.get(telegram_id)
        return user.referral_code if user else None

    async def set_referral_code_if_missing(self, telegram_id: int, code: str) -> bool:
        user = self.users[telegram_id]
        if user.referral_code is not None:
            return False
        user.referral_code = code
        self.codes[code] = telegram_id
        return True

    async def find_user_by_referral_code(self, code: str) -> User | None:
        telegram_id = self.codes.get(code)
        return self.users.get(telegram_id) if telegram_id is not None else None

    async def claim_referral(self, telegram_id: int, referrer_id: int, processed_at) -> bool:
        user = self.users[telegram_id]
        if user.referral_processed_at is not None or user.referred_by_user_id is not None:
            return False
        if telegram_id == referrer_id:
            return False
        user.referred_by_user_id = referrer_id
        user.referral_processed_at = processed_at
        return True

    async def mark_referral_processed(self, telegram_id: int, processed_at) -> bool:
        user = self.users[telegram_id]
        if user.referral_processed_at is not None:
            return False
        user.referral_processed_at = processed_at
        return True

    async def count_referrals(self, telegram_id: int) -> int:
        return sum(
            user.referred_by_user_id == telegram_id for user in self.users.values()
        )

    async def list_referrals(
        self, telegram_id: int, *, offset: int, limit: int
    ) -> list[User]:
        users = [
            user
            for user in self.users.values()
            if user.referred_by_user_id == telegram_id
        ]
        return users[offset : offset + limit]


def make_user(telegram_id: int, code: str | None = None) -> User:
    return User(
        telegram_id=telegram_id,
        telegram_name=f"User {telegram_id}",
        referral_code=code,
    )


@pytest.fixture
def service_and_repository() -> tuple[ReferralService, FakeReferralRepository]:
    repository = FakeReferralRepository()
    return ReferralService(referral_repository=repository), repository


@pytest.mark.asyncio
async def test_ensure_referral_code_generates_opaque_code(service_and_repository, monkeypatch):
    service, repository = service_and_repository
    repository.users[42] = make_user(42)
    monkeypatch.setattr("services.referral.secrets.token_hex", lambda _: "a" * 32)

    code = await service.ensure_referral_code(42)

    assert code == "ref_" + "a" * 32
    assert repository.users[42].referral_code == code
    assert code in repository.codes


@pytest.mark.asyncio
async def test_start_referral_claims_only_new_user_once(service_and_repository):
    service, repository = service_and_repository
    repository.users[1] = make_user(1, "ref_owner")
    repository.codes["ref_owner"] = 1
    repository.users[2] = make_user(2)

    assert await service.process_start(telegram_id=2, referral_code="ref_owner") is True
    assert repository.users[2].referred_by_user_id == 1
    assert repository.users[2].referral_processed_at is not None
    assert await service.process_start(telegram_id=2, referral_code="ref_owner") is False
    assert await service.process_start(telegram_id=2, referral_code="ref_other") is False


@pytest.mark.asyncio
@pytest.mark.parametrize("referral_code", [None, "", "ref_missing"])
async def test_invalid_or_missing_referral_is_consumed_without_assignment(
    service_and_repository, referral_code
):
    service, repository = service_and_repository
    repository.users[2] = make_user(2)

    assert await service.process_start(telegram_id=2, referral_code=referral_code) is False
    assert repository.users[2].referred_by_user_id is None
    assert repository.users[2].referral_processed_at is not None
    assert await service.process_start(telegram_id=2, referral_code="ref_owner") is False


@pytest.mark.asyncio
async def test_self_referral_is_rejected_and_locked(service_and_repository):
    service, repository = service_and_repository
    repository.users[1] = make_user(1, "ref_self")
    repository.codes["ref_self"] = 1

    assert await service.process_start(telegram_id=1, referral_code="ref_self") is False
    assert repository.users[1].referred_by_user_id is None
    assert repository.users[1].referral_processed_at is not None


@pytest.mark.asyncio
async def test_referral_statistics_are_paginated(service_and_repository):
    service, repository = service_and_repository
    repository.users[1] = make_user(1)
    for telegram_id in (2, 3, 4):
        user = make_user(telegram_id)
        user.referred_by_user_id = 1
        repository.users[telegram_id] = user

    assert await service.get_referral_count(1) == 3
    users, total, page = await service.get_referrals_page(
        telegram_id=1, page=99, page_size=2
    )
    assert total == 3
    assert page == 2
    assert [user.telegram_id for user in users] == [4]
