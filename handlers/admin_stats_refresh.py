from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from callbacks.admin import AdminStatsRefreshCallback
from filters.admin import AdminFilter
from keyboards.admin_stats import (
    antispam_stats_keyboard,
    broadcast_stats_keyboard,
    support_stats_keyboard,
    user_stats_keyboard,
)
from services.antispam import AntiSpamService
from services.broadcast import BroadcastService
from services.support import SupportService
from services.user import UserService

router = Router()
router.callback_query.filter(AdminFilter())


async def _edit_message_if_changed(*, message, text: str, reply_markup) -> None:
    if message is None:
        return

    if message.text == text and message.reply_markup == reply_markup:
        return

    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


@router.callback_query(AdminStatsRefreshCallback.filter(F.section == "users"))
async def user_stats_refresh_handler(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    stats = await user_service.get_user_statistics()
    text = (
        "👥 آمار کاربران\n\n"
        f"👤 کل کاربران: {stats['total']:,}\n\n"
        f"✅ ثبت‌نام‌شده: {stats['registered']:,}\n"
        f"⏳ ثبت‌نام‌نشده: {stats['unregistered']:,}\n"
        f"🚫 مسدود: {stats['blocked']:,}\n"
        f"🟢 غیرمسدود: {stats['active']:,}\n\n"
        "📅 فعالیت کاربران\n\n"
        f"🟢 فعال امروز: {stats['active_today']:,}\n"
        f"🟡 فعال ۷ روز اخیر: {stats['active_7d']:,}\n"
        f"⚫ غیرفعال بیش از ۳۰ روز: {stats['inactive_30d']:,}"
    )
    await _edit_message_if_changed(
        message=callback.message,
        text=text,
        reply_markup=user_stats_keyboard(),
    )
    await callback.answer("بروزرسانی شد.")


@router.callback_query(AdminStatsRefreshCallback.filter(F.section == "support"))
async def support_stats_refresh_handler(
    callback: CallbackQuery,
    support_service: SupportService,
) -> None:
    stats = await support_service.get_support_statistics()
    text = (
        "🆘 آمار پشتیبانی\n\n"
        f"🎫 کل تیکت‌ها: {stats['total']:,}\n\n"
        f"🟢 باز: {stats['open']:,}\n"
        f"🔴 بسته: {stats['closed']:,}\n\n"
        "📅 فعالیت تیکت‌ها\n\n"
        f"📝 امروز: {stats['today']:,}\n"
        f"📝 ۷ روز اخیر: {stats['last_7_days']:,}\n"
        f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}"
    )
    await _edit_message_if_changed(
        message=callback.message,
        text=text,
        reply_markup=support_stats_keyboard(),
    )
    await callback.answer("بروزرسانی شد.")


@router.callback_query(AdminStatsRefreshCallback.filter(F.section == "broadcast"))
async def broadcast_stats_refresh_handler(
    callback: CallbackQuery,
    broadcast_service: BroadcastService,
) -> None:
    stats = await broadcast_service.get_broadcast_statistics()

    if stats["latest_total_recipients"] is None:
        text = "📢 آمار همگانی\n\nهنوز هیچ پیام همگانی ارسال نشده است."
    else:
        from core.timezone import TEHRAN_TZ

        latest_dt = stats["latest_created_at"]
        if latest_dt is not None:
            if latest_dt.tzinfo is None:
                latest_dt = latest_dt.replace(tzinfo=TEHRAN_TZ)
            latest_str = latest_dt.strftime("%Y/%m/%d - %H:%M")
        else:
            latest_str = "—"

        duration = stats["latest_duration_seconds"]
        minutes, seconds = divmod(duration, 60)
        duration_str = f"{minutes} دقیقه و {seconds} ثانیه" if minutes else f"{seconds} ثانیه"
        success_rate = stats["latest_success_rate"]

        text = (
            "📢 آمار همگانی\n\n"
            f"📨 کل ارسال‌ها: {stats['total_broadcasts']:,}\n\n"
            "📅 فعالیت ارسال‌ها\n\n"
            f"📝 امروز: {stats['today']:,}\n"
            f"📝 ۷ روز اخیر: {stats['last_7_days']:,}\n"
            f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}\n\n"
            "📊 آخرین ارسال\n\n"
            f"👥 تعداد دریافت‌کنندگان: {stats['latest_total_recipients']:,}\n"
            f"✅ موفق: {stats['latest_success']:,}\n"
            f"❌ ناموفق: {stats['latest_failed']:,}\n"
            f"📈 نرخ موفقیت: {success_rate:.1f}%\n\n"
            f"📅 زمان ارسال:\n{latest_str}\n"
            f"⏱ مدت زمان: {duration_str}"
        )

    await _edit_message_if_changed(
        message=callback.message,
        text=text,
        reply_markup=broadcast_stats_keyboard(),
    )
    await callback.answer("بروزرسانی شد.")


@router.callback_query(AdminStatsRefreshCallback.filter(F.section == "antispam"))
async def antispam_stats_refresh_handler(
    callback: CallbackQuery,
    antispam_service: AntiSpamService,
) -> None:
    stats = await antispam_service.get_antispam_statistics()
    text = (
        "🛡️ آمار ضداسپم\n\n"
        f"⚠️ کل اخطارها: {stats['total_warnings']:,}\n"
        f"🚫 کل مسدودشدگان: {stats['total_blocks']:,}\n\n"
        "📅 فعالیت ضداسپم\n\n"
        f"📝 امروز: {stats['today']:,}\n"
        f"📝 ۷ روز اخیر: {stats['last_7_days']:,}\n"
        f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}"
    )
    await _edit_message_if_changed(
        message=callback.message,
        text=text,
        reply_markup=antispam_stats_keyboard(),
    )
    await callback.answer("بروزرسانی شد.")
