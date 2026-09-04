from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from callbacks.admin import (
    AdminForceSubscriptionStatsTargetCallback,
    AdminForceSubscriptionStatsTargetRefreshCallback,
    AdminStatsCallback,
    AdminStatsRefreshCallback,
)
from filters.admin import AdminFilter
from keyboards.admin_stats import (
    force_subscription_stats_keyboard,
    force_subscription_target_stats_keyboard,
)
from services.force_subscription import ForceSubscriptionService

router = Router()
router.callback_query.filter(AdminFilter())


@router.callback_query(AdminStatsCallback.filter(F.section == "force_subscription"))
async def force_subscription_stats_handler(
    callback: CallbackQuery,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    await _show_force_subscription_statistics(
        message=callback.message,
        force_subscription_service=force_subscription_service,
    )
    await callback.answer()


@router.callback_query(
    AdminStatsRefreshCallback.filter(F.section == "force_subscription")
)
async def force_subscription_stats_refresh_handler(
    callback: CallbackQuery,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    await _show_force_subscription_statistics(
        message=callback.message,
        force_subscription_service=force_subscription_service,
    )
    await callback.answer("بروزرسانی شد.")


@router.callback_query(AdminForceSubscriptionStatsTargetCallback.filter())
async def force_subscription_target_stats_handler(
    callback: CallbackQuery,
    callback_data: AdminForceSubscriptionStatsTargetCallback,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    await _show_target_statistics(
        message=callback.message,
        chat_id=callback_data.chat_id,
        force_subscription_service=force_subscription_service,
    )
    await callback.answer()


@router.callback_query(AdminForceSubscriptionStatsTargetRefreshCallback.filter())
async def force_subscription_target_stats_refresh_handler(
    callback: CallbackQuery,
    callback_data: AdminForceSubscriptionStatsTargetRefreshCallback,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    await _show_target_statistics(
        message=callback.message,
        chat_id=callback_data.chat_id,
        force_subscription_service=force_subscription_service,
    )
    await callback.answer("بروزرسانی شد.")


async def _edit_message_if_changed(
    *,
    message,
    text: str,
    reply_markup,
) -> None:
    """Edit a stats message only when its content or keyboard actually changed.

    Telegram rejects an edit when both are identical. The equality check avoids
    the normal case, while the narrow exception guard handles a possible race
    where another update changes the message between the check and the edit.
    """
    if message is None:
        return

    if message.text == text and message.reply_markup == reply_markup:
        return

    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _show_force_subscription_statistics(
    *,
    message,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    stats = await force_subscription_service.get_membership_statistics()
    targets = await force_subscription_service.list_all_targets()

    text = (
        "📌 آمار عضویت اجباری\n\n"
        "📊 عضویت‌های موفق\n\n"
        f"👥 کل بررسی‌های موفق: {stats['total']:,}\n"
        f"📝 امروز: {stats['today']:,}\n"
        f"📝 ۷ روز اخیر: {stats['last_7_days']:,}\n"
        f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}\n\n"
        f"🎯 تعداد مقصدها: {len(targets):,}\n"
        "برای مشاهده آمار هر مقصد، روی آن بزنید."
    )
    await _edit_message_if_changed(
        message=message,
        text=text,
        reply_markup=force_subscription_stats_keyboard(targets),
    )


async def _show_target_statistics(
    *,
    message,
    chat_id: int,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    target = await force_subscription_service.get_target(chat_id)
    if target is None:
        await _edit_message_if_changed(
            message=message,
            text="❌ این مقصد دیگر در تنظیمات عضویت اجباری وجود ندارد.",
            reply_markup=force_subscription_stats_keyboard([]),
        )
        return

    stats = await force_subscription_service.get_target_membership_statistics(chat_id)
    target_type = "کانال" if target.target_type.value == "channel" else "گروه"
    username = f"@{target.username}" if target.username else "—"

    text = (
        f"📌 آمار {target_type}\n\n"
        f"📍 مقصد: {target.title}\n"
        f"🔗 نام کاربری: {username}\n"
        f"🆔 شناسه: {target.chat_id}\n\n"
        "📊 عضویت‌های موفق\n\n"
        f"👥 کل: {stats['total']:,}\n"
        f"📝 امروز: {stats['today']:,}\n"
        f"📝 ۷ روز اخیر: {stats['last_7_days']:,}\n"
        f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}"
    )
    await _edit_message_if_changed(
        message=message,
        text=text,
        reply_markup=force_subscription_target_stats_keyboard(chat_id),
    )
