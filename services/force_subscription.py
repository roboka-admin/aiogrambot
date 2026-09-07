from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from core.timezone import tehran_now
from core.transaction import NullTransactionManager, TransactionManager, transactional
from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from models.force_subscription_event import ForceSubscriptionMembershipEvent
from repositories.interfaces.force_subscription import IForceSubscriptionRepository
from repositories.interfaces.force_subscription_event import IForceSubscriptionEventRepository
from services.telegram import TelegramGateway, TelegramGatewayError, TelegramRateLimitError


class MembershipStatus(str, Enum):
    MEMBER = "member"
    ADMINISTRATOR = "administrator"
    CREATOR = "creator"
    NOT_MEMBER = "not_member"
    RESTRICTED = "restricted"
    LEFT = "left"
    KICKED = "kicked"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass(frozen=True)
class TargetMembershipResult:
    target: ForceSubscriptionTarget
    status: MembershipStatus

    @property
    def is_satisfied(self) -> bool:
        return self.status in {
            MembershipStatus.MEMBER,
            MembershipStatus.ADMINISTRATOR,
            MembershipStatus.CREATOR,
        }


@dataclass(frozen=True)
class MembershipCheckResult:
    is_allowed: bool
    targets: tuple[TargetMembershipResult, ...]

    @property
    def missing_targets(self) -> tuple[ForceSubscriptionTarget, ...]:
        return tuple(item.target for item in self.targets if not item.is_satisfied)


class ForceSubscriptionService:
    def __init__(
        self,
        *,
        telegram_gateway: TelegramGateway,
        repository: IForceSubscriptionRepository,
        event_repository: IForceSubscriptionEventRepository | None = None,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        self._telegram_gateway = telegram_gateway
        self._repository = repository
        self._event_repository = event_repository
        self._transaction_manager = transaction_manager or NullTransactionManager()

    @transactional
    async def get_active_targets(self) -> list[ForceSubscriptionTarget]:
        return await self._repository.list_active()

    @transactional
    async def list_all_targets(self) -> list[ForceSubscriptionTarget]:
        return await self._repository.list_all()

    @transactional
    async def get_target(self, chat_id: int) -> ForceSubscriptionTarget | None:
        return await self._repository.get(chat_id)

    async def resolve_target(self, value: str) -> ForceSubscriptionTarget:
        query: int | str
        try:
            query = int(value)
        except ValueError:
            query = value if value.startswith("@") else f"@{value}"

        try:
            chat = await self._telegram_gateway.get_chat(chat_id=query)
        except TelegramRateLimitError:
            raise
        except TelegramGatewayError as exc:
            raise ValueError("کانال یا گروه پیدا نشد یا ربات به آن دسترسی ندارد.") from exc

        if chat.type not in {"channel", "supergroup"}:
            raise ValueError("فقط کانال و سوپرگروه قابل افزودن هستند.")

        if not chat.username and not chat.invite_link:
            raise ValueError("این مقصد لینک عمومی یا دعوت قابل استفاده ندارد.")

        target_type = (
            ForceSubscriptionTargetType.CHANNEL
            if chat.type == "channel"
            else ForceSubscriptionTargetType.SUPERGROUP
        )
        now = tehran_now()
        return ForceSubscriptionTarget(
            chat_id=chat.id,
            title=chat.title or str(chat.id),
            target_type=target_type,
            username=chat.username,
            invite_link=chat.invite_link,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    @transactional
    async def add_target(self, target: ForceSubscriptionTarget) -> ForceSubscriptionTarget:
        existing = await self._repository.get(target.chat_id)
        if existing is not None:
            raise ValueError("این کانال یا گروه قبلاً اضافه شده است.")
        return await self._repository.create(target)

    @transactional
    async def delete_target(self, chat_id: int) -> bool:
        return await self._repository.delete(chat_id)

    @transactional
    async def toggle_target(self, chat_id: int) -> ForceSubscriptionTarget | None:
        target = await self._repository.get(chat_id)
        if target is None:
            return None
        target.is_active = not target.is_active
        target.updated_at = tehran_now()
        return await self._repository.update(target)

    async def check_target_membership(
        self,
        *,
        user_telegram_id: int,
        target: ForceSubscriptionTarget,
    ) -> TargetMembershipResult:
        try:
            status = await self._telegram_gateway.get_chat_member(
                chat_id=target.chat_id,
                user_id=user_telegram_id,
            )
        except TelegramRateLimitError:
            raise
        except TelegramGatewayError:
            return TargetMembershipResult(target, MembershipStatus.ERROR)

        membership_status = (
            MembershipStatus(status)
            if status in MembershipStatus._value2member_map_
            else MembershipStatus.UNKNOWN
        )
        return TargetMembershipResult(target, membership_status)

    async def check_membership(self, *, user_telegram_id: int) -> MembershipCheckResult:
        # get_active_targets owns and closes its DB transaction before any
        # Telegram API request is made. Membership checks can therefore be
        # slow without holding a database transaction open.
        targets = await self.get_active_targets()
        if not targets:
            return MembershipCheckResult(True, ())

        results: list[TargetMembershipResult] = []
        for target in targets:
            results.append(
                await self.check_target_membership(
                    user_telegram_id=user_telegram_id,
                    target=target,
                )
            )

        results_tuple = tuple(results)
        return MembershipCheckResult(
            is_allowed=all(result.is_satisfied for result in results_tuple),
            targets=results_tuple,
        )

    @transactional
    async def record_successful_membership_check(
        self,
        *,
        user_telegram_id: int,
        result: MembershipCheckResult,
    ) -> None:
        if self._event_repository is None or not result.is_allowed:
            return
        for item in result.targets:
            await self._event_repository.create(
                ForceSubscriptionMembershipEvent(
                    id=None,
                    user_telegram_id=user_telegram_id,
                    target_chat_id=item.target.chat_id,
                )
            )

    @transactional
    async def get_membership_statistics(self) -> dict[str, int]:
        if self._event_repository is None:
            return {"total": 0, "today": 0, "last_7_days": 0, "last_30_days": 0}

        today = tehran_now().replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            "total": await self._event_repository.count_total(),
            "today": await self._event_repository.count_since(today),
            "last_7_days": await self._event_repository.count_since(today - timedelta(days=7)),
            "last_30_days": await self._event_repository.count_since(today - timedelta(days=30)),
        }

    @transactional
    async def get_target_membership_statistics(
        self, target_chat_id: int
    ) -> dict[str, int]:
        if self._event_repository is None:
            return {"total": 0, "today": 0, "last_7_days": 0, "last_30_days": 0}

        today = tehran_now().replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            "total": await self._event_repository.count_target_total(target_chat_id),
            "today": await self._event_repository.count_target_since(target_chat_id, today),
            "last_7_days": await self._event_repository.count_target_since(
                target_chat_id, today - timedelta(days=7)
            ),
            "last_30_days": await self._event_repository.count_target_since(
                target_chat_id, today - timedelta(days=30)
            ),
        }
