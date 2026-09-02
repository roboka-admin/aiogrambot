from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from config import ADMIN_IDS
from services.bot_settings import BotSettingsService


class MaintenanceMiddleware(BaseMiddleware):
    """Block non-admin updates while the bot is disabled or under maintenance."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        user = event.event.from_user if event.event is not None else None
        if user is None or user.id in ADMIN_IDS:
            return await handler(event, data)

        bot_settings_service: BotSettingsService = data["bot_settings_service"]
        settings = await bot_settings_service.get_settings()

        if not settings.bot_enabled:
            await self._notify_blocked(event, settings.offline_message)
            return None

        if settings.maintenance_mode:
            await self._notify_blocked(event, settings.maintenance_message)
            return None

        return await handler(event, data)

    @staticmethod
    async def _notify_blocked(event: Update, text: str) -> None:
        if event.message is not None:
            await event.message.answer(text)
            return

        if event.callback_query is not None:
            await event.callback_query.answer(text, show_alert=True)
