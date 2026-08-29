import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from services.system import SystemService

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    def __init__(self, *, system_service: SystemService | None = None) -> None:
        self._system_service = system_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        logger.info("Update received: %s", type(event).__name__)
        if self._system_service:
            self._system_service.record_update()

        try:
            return await handler(event, data)
        except Exception as error:
            if self._system_service:
                self._system_service.record_error()
            logger.exception("Error while handling update: %s", error)
            raise
