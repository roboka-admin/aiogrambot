import logging

from services.telegram import TelegramGateway, TelegramGatewayError


class NotificationService:
    """Centralized user notification policy, independent of Telegram/aiogram."""

    def __init__(self, telegram_gateway: TelegramGateway) -> None:
        self._telegram_gateway = telegram_gateway
        self._logger = logging.getLogger(__name__)

    async def warning_added(
        self,
        telegram_id: int,
        warnings: int,
    ) -> None:
        await self._send(
            telegram_id,
            "⚠️ یک اخطار توسط مدیریت برای شما ثبت شد.\n"
            f"تعداد اخطار فعلی: {warnings} از 3",
        )

    async def user_blocked(self, telegram_id: int) -> None:
        await self._send(
            telegram_id,
            "🚫 حساب شما توسط مدیریت مسدود شد.",
        )

    async def user_auto_blocked(self, telegram_id: int) -> None:
        await self._send(
            telegram_id,
            "⚠️ شما 3 اخطار دریافت کرده‌اید و حساب شما مسدود شد.",
        )

    async def user_unblocked(self, telegram_id: int) -> None:
        await self._send(
            telegram_id,
            "✅ حساب شما توسط مدیریت رفع مسدودیت شد.\n"
            "تعداد اخطارهای شما به 0 بازنشانی شد.",
        )

    async def coins_added(
        self,
        telegram_id: int,
        amount: int,
        balance: int,
    ) -> None:
        await self._send(
            telegram_id,
            f"🪙 {amount} سکه به حساب شما اضافه شد.\n"
            f"موجودی فعلی: {balance} سکه",
        )

    async def coins_removed(
        self,
        telegram_id: int,
        amount: int,
        balance: int,
    ) -> None:
        await self._send(
            telegram_id,
            f"🪙 {amount} سکه از حساب شما کم شد.\n"
            f"موجودی فعلی: {balance} سکه",
        )

    async def _send(self, telegram_id: int, text: str) -> None:
        try:
            await self._telegram_gateway.send_message(telegram_id, text)
        except TelegramGatewayError:
            self._logger.warning(
                "Could not deliver notification to user %s",
                telegram_id,
            )
