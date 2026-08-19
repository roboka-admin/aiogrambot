from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject

from core.database import Database
from repositories.user import UserRepository
from services.notification import NotificationService
from services.register import RegisterService
from services.user import UserService


class ServicesMiddleware(BaseMiddleware):
    """Create request-scoped application services."""

    def __init__(self, *, database: Database, bot: Bot) -> None:
        self._database = database
        self._notification_service = NotificationService(bot)

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
                register_service = RegisterService(
                    user_repository=user_repository,
                )
                user_service = UserService(
                    user_repository=user_repository,
                )

                data["register_service"] = register_service
                data["user_service"] = user_service
                data["notification_service"] = self._notification_service

                return await handler(event, data)
