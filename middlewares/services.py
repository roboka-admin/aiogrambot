from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from core.database import Database
from repositories.user import UserRepository
from services.register import RegisterService
from services.user import UserService


class ServicesMiddleware(BaseMiddleware):
    """Create request-scoped repository and services."""

    def __init__(self, *, database: Database) -> None:
        self._database = database

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
            user_repository = UserRepository(session)
            register_service = RegisterService(
                user_repository=user_repository,
            )
            user_service = UserService(
                user_repository=user_repository,
            )

            data["register_service"] = register_service
            data["user_service"] = user_service

            return await handler(event, data)
