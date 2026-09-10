from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from keyboards.force_subscription import CHECK_CALLBACK, force_subscription_keyboard
from services.admin import AdminService
from services.bot_settings import BotSettingsService
from services.force_subscription import ForceSubscriptionService
from services.referral import ReferralService


def _extract_start_payload(text: str) -> str | None:
    """Return the /start argument (invite code) when the text is a /start."""
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return None
    command = parts[0].split("@", maxsplit=1)[0]
    if command != "/start" or len(parts) == 1:
        return None
    return parts[1].strip() or None


class ForceSubscriptionMiddleware(BaseMiddleware):
    """Require non-admin updates to satisfy all active subscription targets."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        telegram_user = data.get("event_from_user")
        if telegram_user is None:
            return await handler(event, data)

        admin_service: AdminService = data["admin_service"]
        if await admin_service.is_active_admin(telegram_user.id):
            return await handler(event, data)

        callback_query = getattr(event, "callback_query", None)
        if callback_query is not None and callback_query.data == CHECK_CALLBACK:
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
        await self._stash_blocked_start_payload(event, data)
        await self._notify_blocked(event, result.missing_targets)
        return None

    @staticmethod
    async def _stash_blocked_start_payload(
        event: Update, data: dict[str, Any]
    ) -> None:
        """Keep a blocked /start invite so it can be claimed after joining.

        A blocked /start never reaches its handler, so without this the
        invitation would be lost. The payload is only stashed; attribution
        and the referrer notification happen after membership is verified.
        """
        message = getattr(event, "message", None)
        if message is None or not message.text:
            return
        payload = _extract_start_payload(message.text)
        if payload is None:
            return
        referral_service: ReferralService | None = data.get("referral_service")
        telegram_user = data.get("event_from_user")
        if referral_service is None or telegram_user is None:
            return
        await referral_service.save_pending_referral(
            telegram_id=telegram_user.id,
            referral_code=payload,
        )

    @staticmethod
    async def _notify_blocked(event: Update, targets) -> None:
        text = (
            "🔐 برای استفاده از ربات ابتدا باید عضو کانال‌ها و گروه‌های زیر شوید.\n\n"
            "بعد از عضویت، روی «🔄 بررسی عضویت» بزنید."
        )
        keyboard = force_subscription_keyboard(list(targets))
        message = getattr(event, "message", None)
        if message is not None:
            await message.answer(text, reply_markup=keyboard)
            return
        callback_query = getattr(event, "callback_query", None)
        if callback_query is not None:
            await callback_query.answer(
                "❌ هنوز عضویت شما تأیید نشده است.",
                show_alert=True,
            )
