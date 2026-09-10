import pytest
from sqlalchemy import BigInteger

from models.bot_settings import BotSettings
from models.referral_reward import ReferralRewardEntry
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

    async def count_registered_referrals(self, telegram_id: int) -> int:
        return sum(
            user.referred_by_user_id == telegram_id
            and user.registration_status is RegistrationStatus.REGISTERED
            for user in self.users.values()
        )

    async def add_coins(self, telegram_id: int, amount: int) -> int | None:
        user = self.users.get(telegram_id)
        if user is None:
            return None
        user.coins += amount
        return user.coins

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


class FakeBotSettingsRepository:
    def __init__(self, settings: BotSettings | None = None) -> None:
        self.settings = settings

    async def get(self) -> BotSettings | None:
        return self.settings


class FakeReferralRewardRepository:
    def __init__(self) -> None:
        self.entries: list[ReferralRewardEntry] = []

    async def create(self, entry: ReferralRewardEntry) -> ReferralRewardEntry:
        entry.id = len(self.entries) + 1
        self.entries.append(entry)
        return entry

    async def sum_invites_consumed(self, referrer_id: int) -> int:
        return sum(e.invites_consumed for e in self.entries if e.referrer_id == referrer_id)

    async def sum_coins(self, referrer_id: int) -> int:
        return sum(e.coins for e in self.entries if e.referrer_id == referrer_id)

    async def sum_coins_total(self) -> int:
        return sum(e.coins for e in self.entries)

    async def count_total(self) -> int:
        return len(self.entries)

    async def count_since(self, since) -> int:
        return sum(e.created_at >= since for e in self.entries)

    async def list_recent(self, *, limit: int) -> list[ReferralRewardEntry]:
        return list(reversed(self.entries))[:limit]


@pytest.fixture
def service_and_repository() -> tuple[ReferralService, FakeReferralRepository]:
    repository = FakeReferralRepository()
    service = ReferralService(
        referral_repository=repository,
        referral_reward_repository=FakeReferralRewardRepository(),
        bot_settings_repository=FakeBotSettingsRepository(),
    )
    return service, repository


def make_reward_service(
    repository: FakeReferralRepository,
    *,
    coins: int,
    per_invites: int,
    ledger: FakeReferralRewardRepository | None = None,
    settings_repository: FakeBotSettingsRepository | None = None,
) -> ReferralService:
    return ReferralService(
        referral_repository=repository,
        referral_reward_repository=ledger or FakeReferralRewardRepository(),
        bot_settings_repository=settings_repository
        or FakeBotSettingsRepository(
            BotSettings(
                referral_reward_coins=coins,
                referral_reward_per_invites=per_invites,
            )
        ),
    )


def make_registered_referral(telegram_id: int, referrer_id: int) -> User:
    return User(
        telegram_id=telegram_id,
        telegram_name=f"User {telegram_id}",
        referred_by_user_id=referrer_id,
        registration_status=RegistrationStatus.REGISTERED,
    )


@pytest.mark.asyncio
async def test_reward_defaults_to_one_coin_per_registered_invite(
    service_and_repository,
) -> None:
    # No settings row yet -> BotSettings() defaults (1 coin / 1 invite).
    service, repository = service_and_repository
    repository.users[1] = make_user(1)
    repository.users[2] = make_registered_referral(2, referrer_id=1)

    reward = await service.reward_referrer_for_registration(
        registered_user=repository.users[2]
    )

    assert reward is not None
    assert (reward.referrer_id, reward.coins, reward.balance) == (1, 1, 1)
    assert reward.registered_referrals == 1
    assert repository.users[1].coins == 1


@pytest.mark.asyncio
async def test_reward_is_granted_only_when_registered_count_hits_threshold() -> None:
    repository = FakeReferralRepository()
    repository.users[1] = make_user(1)
    service = make_reward_service(repository, coins=5, per_invites=3)

    rewards = []
    for telegram_id in (2, 3, 4, 5, 6, 7):
        repository.users[telegram_id] = make_registered_referral(
            telegram_id, referrer_id=1
        )
        rewards.append(
            await service.reward_referrer_for_registration(
                registered_user=repository.users[telegram_id]
            )
        )

    # 6 registered invites at 3-per-reward -> rewards on the 3rd and 6th only.
    assert [reward is not None for reward in rewards] == [
        False, False, True, False, False, True
    ]
    assert rewards[2].registered_referrals == 3
    assert rewards[5].registered_referrals == 6
    assert repository.users[1].coins == 10


@pytest.mark.asyncio
async def test_reward_ignores_unregistered_referrals() -> None:
    repository = FakeReferralRepository()
    repository.users[1] = make_user(1)
    service = make_reward_service(repository, coins=1, per_invites=2)
    # One referral that only did /start, one that actually registered.
    repository.users[2] = User(
        telegram_id=2, telegram_name="Lurker", referred_by_user_id=1
    )
    repository.users[3] = make_registered_referral(3, referrer_id=1)

    reward = await service.reward_referrer_for_registration(
        registered_user=repository.users[3]
    )

    assert reward is None
    assert repository.users[1].coins == 0


@pytest.mark.asyncio
async def test_reward_skips_users_without_referrer(service_and_repository) -> None:
    service, repository = service_and_repository
    repository.users[2] = User(
        telegram_id=2,
        telegram_name="Organic",
        registration_status=RegistrationStatus.REGISTERED,
    )

    reward = await service.reward_referrer_for_registration(
        registered_user=repository.users[2]
    )

    assert reward is None


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


@pytest.mark.asyncio
async def test_reward_writes_ledger_entry_with_consumed_invites() -> None:
    repository = FakeReferralRepository()
    ledger = FakeReferralRewardRepository()
    repository.users[1] = make_user(1)
    service = make_reward_service(repository, coins=5, per_invites=2, ledger=ledger)
    # Registrations arrive one at a time; the second one tips the 2-invite threshold.
    repository.users[2] = make_registered_referral(2, referrer_id=1)
    assert (
        await service.reward_referrer_for_registration(registered_user=repository.users[2])
        is None
    )
    repository.users[3] = make_registered_referral(3, referrer_id=1)
    reward = await service.reward_referrer_for_registration(
        registered_user=repository.users[3]
    )

    assert reward is not None
    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert (entry.referrer_id, entry.coins, entry.invites_consumed) == (1, 5, 2)
    assert entry.triggered_by_user_id == 3


@pytest.mark.asyncio
async def test_ledger_prevents_double_payout_for_same_invites() -> None:
    """Re-running the check for an already-rewarded batch must not pay again."""
    repository = FakeReferralRepository()
    ledger = FakeReferralRewardRepository()
    repository.users[1] = make_user(1)
    service = make_reward_service(repository, coins=1, per_invites=1, ledger=ledger)
    repository.users[2] = make_registered_referral(2, referrer_id=1)

    first = await service.reward_referrer_for_registration(registered_user=repository.users[2])
    second = await service.reward_referrer_for_registration(registered_user=repository.users[2])

    assert first is not None
    assert second is None
    assert repository.users[1].coins == 1
    assert len(ledger.entries) == 1


@pytest.mark.asyncio
async def test_ledger_keeps_leftover_credit_when_threshold_changes() -> None:
    """2 unrewarded invites at N=3, then admin lowers N to 2 -> paid on the next check."""
    repository = FakeReferralRepository()
    ledger = FakeReferralRewardRepository()
    settings_repository = FakeBotSettingsRepository(
        BotSettings(referral_reward_coins=4, referral_reward_per_invites=3)
    )
    repository.users[1] = make_user(1)
    service = make_reward_service(
        repository, coins=4, per_invites=3, ledger=ledger, settings_repository=settings_repository
    )
    for telegram_id in (2, 3):
        repository.users[telegram_id] = make_registered_referral(telegram_id, referrer_id=1)
        assert (
            await service.reward_referrer_for_registration(
                registered_user=repository.users[telegram_id]
            )
            is None
        )

    settings_repository.settings.referral_reward_per_invites = 2
    repository.users[4] = make_registered_referral(4, referrer_id=1)

    reward = await service.reward_referrer_for_registration(registered_user=repository.users[4])

    # 3 registered, 0 consumed, N=2 -> one payout consuming 2; 1 credit left over.
    assert reward is not None and reward.coins == 4
    assert await ledger.sum_invites_consumed(1) == 2
    progress = await service.get_reward_progress(1)
    assert progress.invites_until_next_reward == 1
    assert progress.total_coins_earned == 4


@pytest.mark.asyncio
async def test_reward_progress_for_user_without_activity(service_and_repository) -> None:
    service, repository = service_and_repository
    repository.users[1] = make_user(1)

    progress = await service.get_reward_progress(1)

    assert progress.registered_referrals == 0
    assert progress.total_coins_earned == 0
    assert progress.invites_until_next_reward == 1
    assert (progress.reward_coins, progress.reward_per_invites) == (1, 1)
