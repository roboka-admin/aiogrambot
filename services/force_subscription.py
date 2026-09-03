from dataclasses import dataclass
from enum import Enum

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from models.force_subscription import ForceSubscriptionTarget
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
    def __init__(
        self,
        *,
        bot: Bot,
        repository: IForceSubscriptionRepository,
    ) -> None:
        self._bot = bot
        self._repository = repository

    async def get_active_targets(self) -> list[ForceSubscriptionTarget]:
        return await self._repository.list_active()

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

        status = MembershipStatus(member.status) if member.status in MembershipStatus._value2member_map_ else MembershipStatus.UNKNOWN
        return TargetMembershipResult(target, status)

    async def check_membership(self, *, user_telegram_id: int) -> MembershipCheckResult:
        targets = await self.get_active_targets()
        if not targets:
            return MembershipCheckResult(True, ())

        results = tuple(
            [
                await self.check_target_membership(
                    user_telegram_id=user_telegram_id,
                    target=target,
                )
                for target in targets
            ]
        )
        return MembershipCheckResult(
            is_allowed=all(result.is_satisfied for result in results),
            targets=results,
        )
