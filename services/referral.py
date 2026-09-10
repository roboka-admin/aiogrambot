import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from math import ceil

from core.timezone import tehran_now
from core.transaction import NullTransactionManager, TransactionManager, transactional
from exceptions.user import UserNotFoundError
from models.bot_settings import BotSettings
from models.referral_reward import ReferralRewardEntry
from models.user import User, UserStatus
from repositories.interfaces.bot_settings import IBotSettingsRepository
from repositories.interfaces.referral import IReferralRepository
from repositories.interfaces.referral_reward import IReferralRewardRepository


_REFERRAL_CODE_PATTERN = re.compile(r"^ref_[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class ReferralReward:
    """Coins credited to a referrer after one of their invites registered."""

    referrer_id: int
    coins: int
    balance: int
    registered_referrals: int


@dataclass(frozen=True, slots=True)
class ReferralRewardProgress:
    """What a referrer has earned so far and how close the next payout is."""

    registered_referrals: int
    total_coins_earned: int
    invites_until_next_reward: int
    reward_coins: int
    reward_per_invites: int


class ReferralService:
    """Own referral-code lifecycle, attribution, rewards, and statistics."""

    def __init__(
        self,
        *,
        referral_repository: IReferralRepository,
        referral_reward_repository: IReferralRewardRepository,
        bot_settings_repository: IBotSettingsRepository,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        self._referral_repository = referral_repository
        self._referral_reward_repository = referral_reward_repository
        self._bot_settings_repository = bot_settings_repository
        self._transaction_manager = transaction_manager or NullTransactionManager()

    @transactional
    async def ensure_referral_code(self, telegram_id: int) -> str:
        current_code = await self._referral_repository.get_referral_code(telegram_id)
        if current_code is not None:
            return current_code

        code = f"ref_{secrets.token_hex(16)}"
        if not await self._referral_repository.set_referral_code_if_missing(
            telegram_id, code
        ):
            current_code = await self._referral_repository.get_referral_code(telegram_id)
            if current_code is not None:
                return current_code
            raise UserNotFoundError(telegram_id)
        return code

    @transactional
    async def process_start(
        self, *, telegram_id: int, referral_code: str | None
    ) -> int | None:
        """Attribute a /start to its referrer and return the referrer id.

        When force-subscription blocked an earlier /start, its payload waits
        in ``referral_pending_code``. The pending code wins over a new payload
        (first invite wins) so a re-sent /start after joining cannot lose or
        replace the original invitation.
        """
        pending_code = await self._referral_repository.get_pending_referral_code(
            telegram_id
        )
        effective_code = pending_code or referral_code
        return await self._claim_code(
            telegram_id=telegram_id,
            referral_code=effective_code,
        )

    @transactional
    async def save_pending_referral(
        self, *, telegram_id: int, referral_code: str | None
    ) -> bool:
        """Stash a blocked /start payload until membership is verified.

        Only well-formed codes are stored; validation of the referrer itself
        (existence, self-invite, active status) happens at claim time because
        the referrer may change between the block and the join.
        """
        if referral_code is None or not _REFERRAL_CODE_PATTERN.fullmatch(
            referral_code.strip()
        ):
            return False
        return await self._referral_repository.save_pending_referral_code(
            telegram_id, referral_code.strip()
        )

    @transactional
    async def claim_pending_referral(self, *, telegram_id: int) -> int | None:
        """Claim the stashed invite after membership is verified.

        Returns the referrer id on success, None otherwise. When nothing is
        pending the referral decision is left untouched so a future /start
        with an invite link can still claim.
        """
        pending_code = await self._referral_repository.get_pending_referral_code(
            telegram_id
        )
        if pending_code is None:
            return None
        return await self._claim_code(
            telegram_id=telegram_id,
            referral_code=pending_code,
        )

    async def _claim_code(
        self, *, telegram_id: int, referral_code: str | None
    ) -> int | None:
        processed_at = tehran_now()
        if referral_code is None or not _REFERRAL_CODE_PATTERN.fullmatch(referral_code):
            await self._referral_repository.mark_referral_processed(
                telegram_id, processed_at
            )
            return None

        referrer = await self._referral_repository.find_user_by_referral_code(
            referral_code
        )
        if referrer is None or referrer.telegram_id == telegram_id:
            await self._referral_repository.mark_referral_processed(
                telegram_id, processed_at
            )
            return None

        if referrer.status is not UserStatus.ACTIVE:
            await self._referral_repository.mark_referral_processed(
                telegram_id, processed_at
            )
            return None

        claimed = await self._referral_repository.claim_referral(
            telegram_id,
            referrer.telegram_id,
            processed_at,
        )
        return referrer.telegram_id if claimed else None

    @transactional
    async def reward_referrer_for_registration(
        self, *, registered_user: User
    ) -> ReferralReward | None:
        """Credit the referrer once ``registered_user`` completed registration.

        Ledger based: every payout records how many registered invites it
        consumed, so only *unrewarded* invites count toward the next
        threshold. This keeps leftover credit when the admin changes the
        rule mid-way and makes double payouts impossible. Registered (not
        merely /start-ed) invites are counted so throwaway accounts that
        never register cannot generate coins. Returns None when nothing
        was credited.
        """
        referrer_id = registered_user.referred_by_user_id
        if referrer_id is None:
            return None

        settings = await self._bot_settings_repository.get() or BotSettings()
        per_invites = settings.referral_reward_per_invites
        coins = settings.referral_reward_coins
        if per_invites <= 0 or coins <= 0:
            return None

        registered = await self._referral_repository.count_registered_referrals(
            referrer_id
        )
        consumed = await self._referral_reward_repository.sum_invites_consumed(
            referrer_id
        )
        if registered - consumed < per_invites:
            return None

        balance = await self._referral_repository.add_coins(referrer_id, coins)
        if balance is None:
            return None
        await self._referral_reward_repository.create(
            ReferralRewardEntry(
                id=None,
                referrer_id=referrer_id,
                triggered_by_user_id=registered_user.telegram_id,
                coins=coins,
                invites_consumed=per_invites,
                created_at=tehran_now(),
            )
        )
        return ReferralReward(
            referrer_id=referrer_id,
            coins=coins,
            balance=balance,
            registered_referrals=registered,
        )

    @transactional
    async def get_reward_progress(self, telegram_id: int) -> ReferralRewardProgress:
        """Summarize earned rewards and distance to the next payout for the user screen."""
        settings = await self._bot_settings_repository.get() or BotSettings()
        registered = await self._referral_repository.count_registered_referrals(
            telegram_id
        )
        consumed = await self._referral_reward_repository.sum_invites_consumed(
            telegram_id
        )
        earned = await self._referral_reward_repository.sum_coins(telegram_id)
        per_invites = max(1, settings.referral_reward_per_invites)
        return ReferralRewardProgress(
            registered_referrals=registered,
            total_coins_earned=earned,
            invites_until_next_reward=max(0, per_invites - (registered - consumed)),
            reward_coins=settings.referral_reward_coins,
            reward_per_invites=per_invites,
        )

    @transactional
    async def get_recent_rewards(self, *, limit: int = 10) -> list[ReferralRewardEntry]:
        return await self._referral_reward_repository.list_recent(limit=limit)

    @transactional
    async def get_referral_count(self, telegram_id: int) -> int:
        return await self._referral_repository.count_referrals(telegram_id)

    @transactional
    async def get_referrals_page(
        self, *, telegram_id: int, page: int = 1, page_size: int = 10
    ) -> tuple[list[User], int, int]:
        if page_size <= 0:
            raise ValueError("page_size must be positive")

        total = await self._referral_repository.count_referrals(telegram_id)
        total_pages = max(1, ceil(total / page_size))
        page = min(max(1, page), total_pages)
        offset = (page - 1) * page_size
        users = await self._referral_repository.list_referrals(
            telegram_id,
            offset=offset,
            limit=page_size,
        )
        return users, total, page

    @transactional
    async def get_referral_statistics(
        self, *, top_referrers_limit: int = 5
    ) -> dict[str, int | list[tuple[User, int]]]:
        now = tehran_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=7)
        thirty_days_ago = today_start - timedelta(days=30)

        total = await self._referral_repository.count_referrals_total()
        registered = await self._referral_repository.count_referred_registered()
        return {
            "total": total,
            # Referred users are either registered or not, so the pending
            # count is the complement and needs no query of its own.
            "unregistered": total - registered,
            "registered": registered,
            "users_with_code": (
                await self._referral_repository.count_users_with_referral_code()
            ),
            "today": await self._referral_repository.count_referrals_since(
                today_start
            ),
            "last_7_days": await self._referral_repository.count_referrals_since(
                seven_days_ago
            ),
            "last_30_days": await self._referral_repository.count_referrals_since(
                thirty_days_ago
            ),
            "top_referrers": await self._referral_repository.top_referrers(
                limit=top_referrers_limit
            ),
            "rewards_paid": await self._referral_reward_repository.count_total(),
            "rewards_paid_today": await self._referral_reward_repository.count_since(
                today_start
            ),
            "coins_rewarded": await self._referral_reward_repository.sum_coins_total(),
        }
