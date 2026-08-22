from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject

from core.database import Database
from repositories.support import SupportRepository
from repositories.user import UserRepository
from services.broadcast import BroadcastService
from services.register import RegisterService
from services.support import SupportService
from services.user import UserService


class ServicesMiddleware(BaseMiddleware):
    """Create request-scoped repository and services."""

    def __init__(self, *, database: Database, bot: Bot) -> None:
        self._database = database
        self._bot = bot

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._database.get_session() as session:
            async with session.begin():
                user_repository = UserRepository(session)
                support_repository = SupportRepository(session)

                register_service = RegisterService(
                    user_repository=user_repository,
                )
                user_service = UserService(
                    user_repository=user_repository,
                )
                support_service = SupportService(
                    support_repository=support_repository,
                )
                broadcast_service = BroadcastService(
                    user_repository=user_repository,
                    bot=self._bot,
                )

                data["register_service"] = register_service
                data["user_service"] = user_service
                data["support_service"] = support_service
                data["broadcast_service"] = broadcast_service

                return await handler(event, data)
