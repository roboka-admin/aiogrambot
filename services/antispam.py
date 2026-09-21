from datetime import timedelta

from core.timezone import tehran_now
from core.transaction import NullTransactionManager, TransactionManager, transactional
from models import event_counter as counters
from models.antispam import AntiSpamEvent, AntiSpamEventType
from repositories.interfaces.antispam import IAntiSpamRepository
from repositories.interfaces.event_counter import IEventCounterRepository


class AntiSpamService:
    def __init__(
        self,
        *,
        antispam_repository: IAntiSpamRepository,
        transaction_manager: TransactionManager | None = None,
        counter_repository: IEventCounterRepository | None = None,
    ) -> None:
        self._antispam_repository = antispam_repository
        # Lifetime totals = rows archived by retention + rows still present.
        self._counter_repository = counter_repository
        self._transaction_manager = transaction_manager or NullTransactionManager()

    @transactional
    async def record_warning(self, user_telegram_id: int) -> AntiSpamEvent:
        return await self._antispam_repository.create(
            AntiSpamEvent(
                id=None,
                user_telegram_id=user_telegram_id,
                event_type=AntiSpamEventType.WARNING,
            )
        )

    @transactional
    async def record_block(self, user_telegram_id: int) -> AntiSpamEvent:
        return await self._antispam_repository.create(
            AntiSpamEvent(
                id=None,
                user_telegram_id=user_telegram_id,
                event_type=AntiSpamEventType.BLOCK,
            )
        )

    @transactional
    async def get_antispam_statistics(self) -> dict[str, int]:
        now = tehran_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=7)
        thirty_days_ago = today_start - timedelta(days=30)

        archived_warnings = archived_blocks = 0
        if self._counter_repository is not None:
            archived_warnings = await self._counter_repository.get(counters.ANTISPAM_WARNINGS)
            archived_blocks = await self._counter_repository.get(counters.ANTISPAM_BLOCKS)

        return {
            "total_warnings": archived_warnings
            + await self._antispam_repository.count_total_warnings(),
            "total_blocks": archived_blocks + await self._antispam_repository.count_total_blocks(),
            "today": await self._antispam_repository.count_today(today_start),
            "last_7_days": await self._antispam_repository.count_last_7_days(seven_days_ago),
            "last_30_days": await self._antispam_repository.count_last_30_days(thirty_days_ago),
        }
