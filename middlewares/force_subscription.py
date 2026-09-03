from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from config import ADMIN_IDS
from services.bot_settings import BotSettingsService
from services.force_subscription import ForceSubscriptionService


class ForceSubscriptionMiddleware(BaseMiddleware):
    """Require non-admin users to satisfy all active subscription targets."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        telegram_user = data.get("event_from_user")
        if telegram_user is None or telegram_user.id in ADMIN_IDS:
            return await handler(event, data)

        settings_service: BotSettingsService = data["bot_settings_service"]
        settings = await settings_service.get_settings()
        if not settings.force_subscription_enabled:
            return await handler(event, data)

        force_subscription_service: ForceSubscriptionService = data[
            "force_subscription_service"
        ]
        result = await force_subscription_service.check_membership(
            user_telegram_id=telegram_user.id,
        )
        if result.is_allowed:
            return await handler(event, data)

        data["force_subscription_result"] = result
        await self._notify_blocked(event)
        return None

    @staticmethod
    async def _notify_blocked(event: Update) -> None:
        text = "🔐 برای استفاده از ربات ابتدا باید در کانال‌ها و گروه‌های موردنیاز عضو شوید."
        if event.message is not None:
            await event.message.answer(text)
            return
        if event.callback_query is not None:
            await event.callback_query.answer(text, show_alert=True)
