import pytest
from sqlalchemy import BigInteger

from models.user import RegistrationStatus, User
from models.user_db import UserRecord
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
        user.referral_pending_code = None
        return True

    async def mark_referral_processed(self, telegram_id: int, processed_at) -> bool:
        user = self.users[telegram_id]
        if user.referral_processed_at is not None:
            return False
        user.referral_processed_at = processed_at
        user.referral_pending_code = None
        return True

    async def get_pending_referral_code(self, telegram_id: int) -> str | None:
        user = self.users.get(telegram_id)
        return user.referral_pending_code if user else None

    async def save_pending_referral_code(self, telegram_id: int, code: str) -> bool:
        user = self.users[telegram_id]
        if (
            user.referred_by_user_id is not None
            or user.referral_processed_at is not None
            or user.referral_pending_code is not None
        ):
            return False
        user.referral_pending_code = code
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

    async def count_referrals_total(self) -> int:
        return sum(user.referred_by_user_id is not None for user in self.users.values())

    async def count_referred_registered(self) -> int:
        return sum(
            user.referred_by_user_id is not None
            and user.registration_status is RegistrationStatus.REGISTERED
            for user in self.users.values()
        )

    async def count_users_with_referral_code(self) -> int:
        return sum(user.referral_code is not None for user in self.users.values())

    async def count_referrals_since(self, since) -> int:
        return sum(
            user.referred_by_user_id is not None
            and user.referral_processed_at is not None
            and user.referral_processed_at >= since
            for user in self.users.values()
        )

    async def top_referrers(self, *, limit: int) -> list[tuple[User, int]]:
        counts: dict[int, int] = {}
        for user in self.users.values():
            if user.referred_by_user_id is not None:
                counts[user.referred_by_user_id] = (
                    counts.get(user.referred_by_user_id, 0) + 1
                )
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        return [(self.users[referrer_id], count) for referrer_id, count in ranked]


VALID_REFERRAL_CODE = "ref_" + "b" * 32
OTHER_REFERRAL_CODE = "ref_" + "c" * 32
SELF_REFERRAL_CODE = "ref_" + "d" * 32


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
    repository.users[1] = make_user(1, VALID_REFERRAL_CODE)
    repository.codes[VALID_REFERRAL_CODE] = 1
    repository.users[2] = make_user(2)

    assert await service.process_start(
        telegram_id=2, referral_code=VALID_REFERRAL_CODE
    ) == 1
    assert repository.users[2].referred_by_user_id == 1
    assert repository.users[2].referral_processed_at is not None
    assert await service.process_start(
        telegram_id=2, referral_code=VALID_REFERRAL_CODE
    ) is None
    assert await service.process_start(
        telegram_id=2, referral_code=OTHER_REFERRAL_CODE
    ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("referral_code", [None, "", "ref_missing", "ref_owner"])
async def test_invalid_or_missing_referral_is_consumed_without_assignment(
    service_and_repository, referral_code
):
    service, repository = service_and_repository
    repository.users[2] = make_user(2)

    assert await service.process_start(telegram_id=2, referral_code=referral_code) is None
    assert repository.users[2].referred_by_user_id is None
    assert repository.users[2].referral_processed_at is not None
    assert await service.process_start(
        telegram_id=2, referral_code=VALID_REFERRAL_CODE
    ) is None


@pytest.mark.asyncio
async def test_self_referral_is_rejected_and_locked(service_and_repository):
    service, repository = service_and_repository
    repository.users[1] = make_user(1, SELF_REFERRAL_CODE)
    repository.codes[SELF_REFERRAL_CODE] = 1

    assert await service.process_start(
        telegram_id=1, referral_code=SELF_REFERRAL_CODE
    ) is None
    assert repository.users[1].referred_by_user_id is None
    assert repository.users[1].referral_processed_at is not None


@pytest.mark.asyncio
async def test_pending_referral_is_claimed_only_after_membership(service_and_repository):
    service, repository = service_and_repository
    repository.users[1] = make_user(1, VALID_REFERRAL_CODE)
    repository.codes[VALID_REFERRAL_CODE] = 1
    repository.users[2] = make_user(2)

    # A blocked /start only stashes the invite; nothing is attributed yet.
    assert await service.save_pending_referral(
        telegram_id=2, referral_code=VALID_REFERRAL_CODE
    ) is True
    assert repository.users[2].referred_by_user_id is None
    assert repository.users[2].referral_processed_at is None

    # First invite wins: a second payload must not replace the pending one.
    assert await service.save_pending_referral(
        telegram_id=2, referral_code=OTHER_REFERRAL_CODE
    ) is False
    assert repository.users[2].referral_pending_code == VALID_REFERRAL_CODE

    # Membership verification claims the stashed invite.
    assert await service.claim_pending_referral(telegram_id=2) == 1
    assert repository.users[2].referred_by_user_id == 1
    assert repository.users[2].referral_processed_at is not None
    assert repository.users[2].referral_pending_code is None
    assert await service.claim_pending_referral(telegram_id=2) is None


@pytest.mark.asyncio
async def test_claim_pending_without_stash_leaves_future_start_eligible(
    service_and_repository,
):
    service, repository = service_and_repository
    repository.users[1] = make_user(1, VALID_REFERRAL_CODE)
    repository.codes[VALID_REFERRAL_CODE] = 1
    repository.users[2] = make_user(2)

    assert await service.claim_pending_referral(telegram_id=2) is None
    assert repository.users[2].referral_processed_at is None

    # A later /start with an invite can still claim.
    assert await service.process_start(
        telegram_id=2, referral_code=VALID_REFERRAL_CODE
    ) == 1


@pytest.mark.asyncio
async def test_process_start_prefers_pending_over_new_payload(service_and_repository):
    service, repository = service_and_repository
    repository.users[1] = make_user(1, VALID_REFERRAL_CODE)
    repository.codes[VALID_REFERRAL_CODE] = 1
    repository.users[5] = make_user(5, OTHER_REFERRAL_CODE)
    repository.codes[OTHER_REFERRAL_CODE] = 5
    repository.users[2] = make_user(2)
    repository.users[2].referral_pending_code = VALID_REFERRAL_CODE

    # A re-sent /start after joining must claim the original invite.
    assert await service.process_start(
        telegram_id=2, referral_code=OTHER_REFERRAL_CODE
    ) == 1
    assert repository.users[2].referred_by_user_id == 1


@pytest.mark.asyncio
async def test_save_pending_rejects_malformed_codes(service_and_repository):
    service, repository = service_and_repository
    repository.users[2] = make_user(2)

    for bad_code in (None, "", "ref_owner", "not-a-code"):
        assert await service.save_pending_referral(
            telegram_id=2, referral_code=bad_code
        ) is False
    assert repository.users[2].referral_pending_code is None


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


@pytest.mark.asyncio
async def test_get_referral_statistics_aggregates_funnel_and_top_referrers(
    service_and_repository,
):
    service, repository = service_and_repository
    repository.users[1] = make_user(1, VALID_REFERRAL_CODE)
    repository.codes[VALID_REFERRAL_CODE] = 1
    repository.users[2] = make_user(2, OTHER_REFERRAL_CODE)
    repository.codes[OTHER_REFERRAL_CODE] = 2
    repository.users[3] = make_user(3)
    repository.users[4] = make_user(4)

    # User 1 refers users 3 and 4; only user 3 goes on to register.
    assert await service.process_start(telegram_id=3, referral_code=VALID_REFERRAL_CODE)
    assert await service.process_start(telegram_id=4, referral_code=VALID_REFERRAL_CODE)
    repository.users[3].registration_status = RegistrationStatus.REGISTERED

    stats = await service.get_referral_statistics()

    assert stats["total"] == 2
    assert stats["registered"] == 1
    assert stats["unregistered"] == 1
    assert stats["users_with_code"] == 2
    assert stats["today"] == 2
    assert stats["last_7_days"] == 2
    assert stats["last_30_days"] == 2
    assert stats["top_referrers"] == [(repository.users[1], 2)]


@pytest.mark.asyncio
async def test_get_referral_statistics_returns_zeroes_when_nothing_happened(
    service_and_repository,
):
    service, repository = service_and_repository
    repository.users[1] = make_user(1)

    stats = await service.get_referral_statistics()

    assert stats["total"] == 0
    assert stats["registered"] == 0
    assert stats["unregistered"] == 0
    assert stats["users_with_code"] == 0
    assert stats["today"] == 0
    assert stats["last_7_days"] == 0
    assert stats["last_30_days"] == 0
    assert stats["top_referrers"] == []


def test_user_record_referral_fk_matches_telegram_id_type():
    """MySQL rejects FK when INTEGER PK is paired with BIGINT referrer id."""
    telegram_id_type = UserRecord.__table__.c.telegram_id.type
    referred_by_type = UserRecord.__table__.c.referred_by_user_id.type
    assert isinstance(telegram_id_type, BigInteger)
    assert isinstance(referred_by_type, BigInteger)
