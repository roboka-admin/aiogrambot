from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from models.user import User, UserStatus
from services.user import UserService


class UserMiddleware(BaseMiddleware):
    """Track every Telegram user, inject the domain user, and block banned users."""

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        user_service: UserService = data["user_service"]
        telegram_user = data.get("event_from_user")

        user: User | None = None
        if telegram_user is not None:
            user = await user_service.get_or_create_telegram_user(
                telegram_id=telegram_user.id,
                telegram_name=telegram_user.full_name,
                username=telegram_user.username,
            )
            if user.status == UserStatus.BLOCKED:
                return None

        data["user"] = user
        return await handler(event, data)
