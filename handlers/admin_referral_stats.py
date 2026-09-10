from aiogram import F, Router
from aiogram.types import CallbackQuery

from callbacks.admin import AdminStatsCallback, AdminStatsRefreshCallback
from core.telegram import edit_message_if_changed
from filters.admin import AdminPermissionFilter
from keyboards.admin_stats import referral_stats_keyboard
from models.user import User
from services.referral import ReferralService

router = Router()
router.callback_query.filter(AdminPermissionFilter("stats"))


@router.callback_query(AdminStatsCallback.filter(F.section == "referral"))
async def referral_stats_handler(
    callback: CallbackQuery,
    referral_service: ReferralService,
) -> None:
    await _show_referral_statistics(
        message=callback.message, referral_service=referral_service
    )
    await callback.answer()


@router.callback_query(AdminStatsRefreshCallback.filter(F.section == "referral"))
async def referral_stats_refresh_handler(
    callback: CallbackQuery,
    referral_service: ReferralService,
) -> None:
    await _show_referral_statistics(
        message=callback.message, referral_service=referral_service
    )
    await callback.answer("بروزرسانی شد.")


async def _show_referral_statistics(*, message, referral_service: ReferralService) -> None:
    stats = await referral_service.get_referral_statistics()
    text = _referral_stats_text(stats)
    await edit_message_if_changed(
        message=message,
        text=text,
        reply_markup=referral_stats_keyboard(),
    )


def _referral_stats_text(stats: dict[str, int | list[tuple[User, int]]]) -> str:
    total: int = stats["total"]
    registered: int = stats["registered"]
    conversion = f"{registered / total * 100:.1f}%" if total else "—"

    lines = [
        "🎁 آمار دعوت‌ها\n",
        f"👥 کل دعوت‌های موفق: {total:,}\n",
        f"✅ ثبت‌نام‌شده: {registered:,}",
        f"⏳ در انتظار ثبت‌نام: {stats['unregistered']:,}",
        f"📈 نرخ تبدیل: {conversion}\n",
        f"🔗 کاربران دارای لینک دعوت: {stats['users_with_code']:,}\n",
        "📅 فعالیت دعوت‌ها\n",
        f"📝 امروز: {stats['today']:,}",
        f"📝 ۷ روز اخیر: {stats['last_7_days']:,}",
        f"📝 ۳۰ روز اخیر: {stats['last_30_days']:,}",
    ]

    top_referrers: list[tuple[User, int]] = stats["top_referrers"]
    if top_referrers:
        lines.append("")
        lines.append("🏆 برترین دعوت‌کننده‌ها\n")
        for rank, (referrer, count) in enumerate(top_referrers, start=1):
            lines.append(f"{rank}. {_referrer_display_name(referrer)} — {count:,} دعوت")

    return "\n".join(lines)


def _referrer_display_name(referrer: User) -> str:
    if referrer.name:
        return referrer.name
    if referrer.telegram_name:
        return referrer.telegram_name
    if referrer.username:
        return f"@{referrer.username}"
    return f"ID: {referrer.telegram_id}"
