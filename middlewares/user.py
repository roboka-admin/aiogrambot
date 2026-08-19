from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from exceptions.user import UserNotFoundError
from models.user import User, UserStatus
from services.user import UserService


class UserMiddleware(BaseMiddleware):
    """Load the current user, block banned users, and inject the user."""

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_service: UserService = data["user_service"]
        telegram_user = data.get("event_from_user")

        user: User | None = None

        if telegram_user is not None:
            try:
                user = await user_service.get_user(telegram_user.id)
            except UserNotFoundError:
                pass
            else:
                if user.status == UserStatus.BLOCKED:
                    return None

        data["user"] = user

        return await handler(event, data)
