from dataclasses import dataclass
from enum import Enum

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from core.timezone import tehran_now
from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from repositories.interfaces.force_subscription import IForceSubscriptionRepository


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
    def __init__(self, *, bot: Bot, repository: IForceSubscriptionRepository) -> None:
        self._bot = bot
        self._repository = repository

    async def get_active_targets(self) -> list[ForceSubscriptionTarget]:
        return await self._repository.list_active()

    async def list_all_targets(self) -> list[ForceSubscriptionTarget]:
        return await self._repository.list_all()

    async def resolve_target(self, value: str) -> ForceSubscriptionTarget:
        query: int | str
        try:
            query = int(value)
        except ValueError:
            query = value if value.startswith("@") else f"@{value}"

        try:
            chat = await self._bot.get_chat(chat_id=query)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            raise ValueError("کانال یا گروه پیدا نشد یا ربات به آن دسترسی ندارد.") from exc

        if chat.type not in {"channel", "supergroup"}:
            raise ValueError("فقط کانال و سوپرگروه قابل افزودن هستند.")

        username = getattr(chat, "username", None)
        invite_link = getattr(chat, "invite_link", None)
        if not username and not invite_link:
            raise ValueError("این مقصد لینک عمومی یا دعوت قابل استفاده ندارد.")

        target_type = (
            ForceSubscriptionTargetType.CHANNEL
            if chat.type == "channel"
            else ForceSubscriptionTargetType.SUPERGROUP
        )
        return ForceSubscriptionTarget(
            chat_id=chat.id,
            title=chat.title or str(chat.id),
            target_type=target_type,
            username=username,
            invite_link=invite_link,
            is_active=True,
            created_at=tehran_now(),
            updated_at=tehran_now(),
        )

    async def add_target(self, target: ForceSubscriptionTarget) -> ForceSubscriptionTarget:
        existing = await self._repository.get(target.chat_id)
        if existing is not None:
            raise ValueError("این کانال یا گروه قبلاً اضافه شده است.")
        return await self._repository.create(target)

    async def delete_target(self, chat_id: int) -> bool:
        return await self._repository.delete(chat_id)

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
            member = await self._bot.get_chat_member(
                chat_id=target.chat_id,
                user_id=user_telegram_id,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            return TargetMembershipResult(target, MembershipStatus.ERROR)

        status = (
            MembershipStatus(member.status)
            if member.status in MembershipStatus._value2member_map_
            else MembershipStatus.UNKNOWN
        )
        return TargetMembershipResult(target, status)

    async def check_membership(self, *, user_telegram_id: int) -> MembershipCheckResult:
        targets = await self.get_active_targets()
        if not targets:
            return MembershipCheckResult(True, ())

        # This must be a normal async loop: awaiting inside a generator expression
        # produces an async generator, which cannot be consumed by tuple().
        results = tuple(
            await self.check_target_membership(
                user_telegram_id=user_telegram_id,
                target=target,
            )
            for target in targets
        )
        return MembershipCheckResult(
            is_allowed=all(result.is_satisfied for result in results),
            targets=results,
        )
