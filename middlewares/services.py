from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from services.register import RegisterService


class ServicesMiddleware(BaseMiddleware):
    """
    Inject application services into aiogram handlers.

    This middleware does NOT create services.
    It only passes already-created service instances
    from main.py to handlers.
    """

    def __init__(
        self,
        *,
        register_service: RegisterService,
    ) -> None:
        self._register_service = register_service

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:

        data["register_service"] = self._register_service

        return await handler(event, data)