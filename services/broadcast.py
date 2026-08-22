import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)

from repositories.interfaces.user import IUserRepository

logger = logging.getLogger(__name__)

_SEND_DELAY_SECONDS = 0.05
ProgressCallback = Callable[[int, int, int, int], Awaitable[None]]


@dataclass(slots=True, frozen=True)
class BroadcastResult:
    total: int
    success: int
    failed: int
    duration_seconds: int


class BroadcastService:
    """Coordinates safe delivery of an admin message to active users."""

    def __init__(self, *, user_repository: IUserRepository, bot: Bot) -> None:
        self._user_repository = user_repository
        self._bot = bot

    async def count_recipients(self) -> int:
        return len(await self._user_repository.list_active_telegram_ids())

    async def broadcast(
        self,
        *,
        from_chat_id: int,
        message_id: int,
        progress_callback: ProgressCallback | None = None,
        progress_interval: int = 10,
    ) -> BroadcastResult:
        telegram_ids = await self._user_repository.list_active_telegram_ids()
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
                await progress_callback(processed, total, success, failed)

            if processed < total:
                await asyncio.sleep(_SEND_DELAY_SECONDS)

        return BroadcastResult(
            total=total,
            success=success,
            failed=failed,
            duration_seconds=round(time.monotonic() - started_at),
        )

    async def _copy_with_retry(
        self,
        *,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
    ) -> None:
        while True:
            try:
                await self._bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                )
                return
            except TelegramRetryAfter as exc:
                logger.warning(
                    "Broadcast rate limited for user %s; retrying after %s seconds",
                    chat_id,
                    exc.retry_after,
                )
                await asyncio.sleep(exc.retry_after)
