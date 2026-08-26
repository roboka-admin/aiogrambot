from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from models.user import RegistrationStatus, User


class RegistrationRequiredMiddleware(BaseMiddleware):
    """Block protected features until registration is completed."""

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("user")
        if user is not None and user.registration_status == RegistrationStatus.REGISTERED:
            return await handler(event, data)
        if isinstance(event, Message):
            await event.answer("برای استفاده از امکانات ربات ابتدا ثبت نام کنید.")
        elif isinstance(event, CallbackQuery):
            await event.answer("ابتدا باید ثبت نام کنید.", show_alert=True)
        return None
