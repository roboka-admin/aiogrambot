import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler,
        event: TelegramObject,
        data: dict
    ):
        logger.info(
            "Update received: %s",
            type(event).__name__
        )

        try:
            result = await handler(event, data)
            return result

        except Exception as error:
            logger.exception(
                "Error while handling update: %s",
                error
            )
            raise