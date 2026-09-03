from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from config import ADMIN_IDS
from models.user import User, UserStatus
from services.bot_settings import BotSettingsService
from services.force_subscription import ForceSubscriptionService
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

            if telegram_user.id not in ADMIN_IDS:
                settings_service: BotSettingsService = data["bot_settings_service"]
                settings = await settings_service.get_settings()
                if settings.force_subscription_enabled:
                    force_subscription_service: ForceSubscriptionService = data[
                        "force_subscription_service"
                    ]
                    result = await force_subscription_service.check_membership(
                        user_telegram_id=telegram_user.id,
                    )
                    if not result.is_allowed:
                        data["force_subscription_result"] = result
                        if event.message is not None:
                            await event.message.answer(
                                "🔐 برای استفاده از ربات ابتدا باید در کانال‌ها و گروه‌های موردنیاز عضو شوید."
                            )
                        elif event.callback_query is not None:
                            await event.callback_query.answer(
                                "🔐 ابتدا باید در موارد موردنیاز عضو شوید.",
                                show_alert=True,
                            )
                        return None

        data["user"] = user
        return await handler(event, data)
