from datetime import timedelta

from core.timezone import tehran_now
from models.antispam import AntiSpamEvent, AntiSpamEventType
from repositories.interfaces.antispam import IAntiSpamRepository


class AntiSpamService:
    def __init__(self, *, antispam_repository: IAntiSpamRepository) -> None:
        self._antispam_repository = antispam_repository

    async def record_warning(self, user_telegram_id: int) -> AntiSpamEvent:
        return await self._antispam_repository.create(
            AntiSpamEvent(
                id=None,
                user_telegram_id=user_telegram_id,
                event_type=AntiSpamEventType.WARNING,
            )
        )

    async def record_block(self, user_telegram_id: int) -> AntiSpamEvent:
        return await self._antispam_repository.create(
            AntiSpamEvent(
                id=None,
                user_telegram_id=user_telegram_id,
                event_type=AntiSpamEventType.BLOCK,
            )
        )

    async def get_antispam_statistics(self) -> dict[str, int]:
        now = tehran_now()
        today_start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        seven_days_ago = today_start - timedelta(days=7)
        thirty_days_ago = today_start - timedelta(days=30)

        return {
            "total_warnings": await self._antispam_repository.count_total_warnings(),
            "total_blocks": await self._antispam_repository.count_total_blocks(),
            "today": await self._antispam_repository.count_today(today_start),
            "last_7_days": await self._antispam_repository.count_last_7_days(seven_days_ago),
            "last_30_days": await self._antispam_repository.count_last_30_days(thirty_days_ago),
        }