import re
import secrets
from datetime import timedelta
from math import ceil

from core.timezone import tehran_now
from core.transaction import NullTransactionManager, TransactionManager, transactional
from exceptions.user import UserNotFoundError
from models.user import User, UserStatus
from repositories.interfaces.referral import IReferralRepository


_REFERRAL_CODE_PATTERN = re.compile(r"^ref_[0-9a-f]{32}$")


class ReferralService:
    """Own referral-code lifecycle, attribution, and referral statistics."""

    def __init__(
        self,
        *,
        referral_repository: IReferralRepository,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        self._referral_repository = referral_repository
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
    ) -> bool:
        processed_at = tehran_now()
        if referral_code is None or not _REFERRAL_CODE_PATTERN.fullmatch(referral_code):
            await self._referral_repository.mark_referral_processed(
                telegram_id, processed_at
            )
            return False

        referrer = await self._referral_repository.find_user_by_referral_code(
            referral_code
        )
        if referrer is None or referrer.telegram_id == telegram_id:
            await self._referral_repository.mark_referral_processed(
                telegram_id, processed_at
            )
            return False

        if referrer.status is not UserStatus.ACTIVE:
            await self._referral_repository.mark_referral_processed(
                telegram_id, processed_at
            )
            return False

        return await self._referral_repository.claim_referral(
            telegram_id,
            referrer.telegram_id,
            processed_at,
        )

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
        }
