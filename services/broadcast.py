import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)

from core.timezone import tehran_now
from models.broadcast import BroadcastRecord
from repositories.interfaces.broadcast import IBroadcastRepository
from repositories.interfaces.user import IUserRepository

logger = logging.getLogger(__name__)

_SEND_DELAY_SECONDS = 0.05
_MAX_RETRY_AFTER_ATTEMPTS = 3
ProgressCallback = Callable[["BroadcastProgress"], Awaitable[None]]
BroadcastRepositoryFactory = Callable[
    [],
    AbstractAsyncContextManager[tuple[IUserRepository, IBroadcastRepository]],
]


@dataclass(slots=True, frozen=True)
class BroadcastProgress:
    processed: int
    total: int
    success: int
    failed: int
    elapsed_seconds: float

    @property
    def percent(self) -> int:
        if self.total == 0:
            return 100
        return int(self.processed / self.total * 100)

    @property
    def eta_seconds(self) -> int | None:
        if self.processed == 0:
            return None
        average_per_user = self.elapsed_seconds / self.processed
        remaining = self.total - self.processed
        return round(average_per_user * remaining)


@dataclass(slots=True, frozen=True)
class BroadcastResult:
    total: int
    success: int
    failed: int
    duration_seconds: int


class BroadcastService:
    """Coordinates safe delivery of an admin message to active users."""

    def __init__(
        self,
        *,
        user_repository: IUserRepository,
        broadcast_repository: IBroadcastRepository,
        bot: Bot,
        repository_factory: BroadcastRepositoryFactory | None = None,
    ) -> None:
        self._user_repository = user_repository
        self._broadcast_repository = broadcast_repository
        self._repository_factory = repository_factory
        self._bot = bot

    @asynccontextmanager
    async def _repositories(
        self,
    ) -> AsyncIterator[tuple[IUserRepository, IBroadcastRepository]]:
        if self._repository_factory is not None:
            async with self._repository_factory() as repositories:
                yield repositories
            return

        yield self._user_repository, self._broadcast_repository

    async def count_recipients(self) -> int:
        async with self._repositories() as (user_repository, _):
            return len(await user_repository.list_active_telegram_ids())

    async def get_broadcast_statistics(self) -> dict[str, int | float | str | None]:
        now = tehran_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=7)
        thirty_days_ago = today_start - timedelta(days=30)

        async with self._repositories() as (_, broadcast_repository):
            total_broadcasts = await broadcast_repository.count_total()
            today_count = await broadcast_repository.count_today(today_start)
            last_7_days = await broadcast_repository.count_last_7_days(seven_days_ago)
            last_30_days = await broadcast_repository.count_last_30_days(thirty_days_ago)
            latest = await broadcast_repository.get_latest()

        if latest is None:
            return {
                "total_broadcasts": total_broadcasts,
                "today": today_count,
                "last_7_days": last_7_days,
                "last_30_days": last_30_days,
                "latest_total_recipients": None,
                "latest_success": None,
                "latest_failed": None,
                "latest_duration_seconds": None,
                "latest_success_rate": None,
                "latest_created_at": None,
            }

        success_rate = 0.0
        if latest.total_recipients > 0:
            success_rate = (latest.success_count / latest.total_recipients) * 100

        return {
            "total_broadcasts": total_broadcasts,
            "today": today_count,
            "last_7_days": last_7_days,
            "last_30_days": last_30_days,
            "latest_total_recipients": latest.total_recipients,
            "latest_success": latest.success_count,
            "latest_failed": latest.failed_count,
            "latest_duration_seconds": latest.duration_seconds,
            "latest_success_rate": success_rate,
            "latest_created_at": latest.created_at,
        }

    async def broadcast(
        self,
        *,
        from_chat_id: int,
        message_id: int,
        progress_callback: ProgressCallback | None = None,
        progress_interval: int = 10,
    ) -> BroadcastResult:
        if progress_interval < 1:
            raise ValueError("progress_interval must be at least 1")

        async with self._repositories() as (user_repository, _):
            telegram_ids = await user_repository.list_active_telegram_ids()

        total = len(telegram_ids)
        success = 0
        failed = 0
        started_at = time.monotonic()

        for processed, telegram_id in enumerate(telegram_ids, start=1):
            try:
                await self._copy_with_retry(
                    chat_id=telegram_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                )
                success += 1
            except (TelegramForbiddenError, TelegramNotFound) as exc:
                failed += 1
                logger.info("Broadcast unavailable for user %s: %s", telegram_id, exc)
            except TelegramAPIError as exc:
                failed += 1
                logger.warning("Broadcast failed for user %s: %s", telegram_id, exc)
            except Exception:
                failed += 1
                logger.exception("Unexpected broadcast error for user %s", telegram_id)

            if progress_callback and (
                processed % progress_interval == 0 or processed == total
            ):
                await progress_callback(
                    BroadcastProgress(
                        processed=processed,
                        total=total,
                        success=success,
                        failed=failed,
                        elapsed_seconds=time.monotonic() - started_at,
                    )
                )

            if processed < total:
                await asyncio.sleep(_SEND_DELAY_SECONDS)

        result = BroadcastResult(
            total=total,
            success=success,
            failed=failed,
            duration_seconds=round(time.monotonic() - started_at),
        )

        async with self._repositories() as (_, broadcast_repository):
            await broadcast_repository.create(
                BroadcastRecord(
                    id=None,
                    total_recipients=result.total,
                    success_count=result.success,
                    failed_count=result.failed,
                    duration_seconds=result.duration_seconds,
                    created_at=tehran_now(),
                )
            )

        return result

    async def _copy_with_retry(
        self,
        *,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
    ) -> None:
        for attempt in range(1, _MAX_RETRY_AFTER_ATTEMPTS + 1):
            try:
                await self._bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                )
                return
            except TelegramRetryAfter as exc:
                if attempt == _MAX_RETRY_AFTER_ATTEMPTS:
                    raise

                logger.warning(
                    "Broadcast rate limited for user %s; retrying in %s seconds (attempt %s/%s)",
                    chat_id,
                    exc.retry_after,
                    attempt,
                    _MAX_RETRY_AFTER_ATTEMPTS,
                )
                await asyncio.sleep(exc.retry_after)
