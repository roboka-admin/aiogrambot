from html import escape
from math import ceil

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.deep_linking import create_start_link

from callbacks.referral import ReferralListCallback
from core.telegram import edit_message_if_changed
from keyboards.referral import referral_keyboard, referral_list_keyboard
from middlewares.registration import RegistrationRequiredMiddleware
from models.user import RegistrationStatus, User
from services.referral import ReferralService


_REFERRAL_PAGE_SIZE = 10

router = Router()
router.message.middleware(RegistrationRequiredMiddleware())
router.callback_query.middleware(RegistrationRequiredMiddleware())


def _referral_screen_text(*, referral_link: str, count: int) -> str:
    """Build the main referral screen.

    The link is wrapped in <code> so Telegram clients offer tap-to-copy,
    and every dynamic value is HTML-escaped before being interpolated.
    """
    return (
        "👥 <b>دعوت دوستان</b>\n\n"
        "🔗 لینک اختصاصی شما:\n"
        f"<code>{escape(referral_link)}</code>\n\n"
        f"📊 دعوت‌های موفق شما: <b>{count}</b>\n\n"
        "💡 لینک را برای دوستانتان بفرستید؛ با شروع ربات از طریق این لینک،"
        " دعوت شما ثبت می‌شود."
    )


async def _referral_screen_data(
    bot: Bot, user: User, referral_service: ReferralService
) -> tuple[str, int]:
    """Fetch everything the main referral screen needs (link + count)."""
    code = await referral_service.ensure_referral_code(user.telegram_id)
    count = await referral_service.get_referral_count(user.telegram_id)
    referral_link = await create_start_link(bot, code)
    return referral_link, count


@router.message(F.text == "👥 دعوت دوستان")
async def referral_handler(
    message: Message,
    user: User,
    referral_service: ReferralService,
) -> None:
    referral_link, count = await _referral_screen_data(
        message.bot, user, referral_service
    )

    await message.answer(
        _referral_screen_text(referral_link=referral_link, count=count),
        reply_markup=referral_keyboard(
            referral_link=referral_link,
            has_referrals=count > 0,
        ),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "referral_back")
async def referral_back_handler(
    callback: CallbackQuery,
    user: User,
    referral_service: ReferralService,
) -> None:
    """Return from the referral list to the main referral screen."""
    referral_link, count = await _referral_screen_data(
        callback.bot, user, referral_service
    )

    if callback.message:
        await edit_message_if_changed(
            message=callback.message,
            text=_referral_screen_text(referral_link=referral_link, count=count),
            reply_markup=referral_keyboard(
                referral_link=referral_link,
                has_referrals=count > 0,
            ),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(ReferralListCallback.filter())
async def referral_list_handler(
    callback: CallbackQuery,
    callback_data: ReferralListCallback,
    user: User,
    referral_service: ReferralService,
) -> None:
    users, total, page = await referral_service.get_referrals_page(
        telegram_id=user.telegram_id,
        page=callback_data.page,
        page_size=_REFERRAL_PAGE_SIZE,
    )
    total_pages = max(1, ceil(total / _REFERRAL_PAGE_SIZE))

    lines = [f"👥 <b>دعوت‌شده‌ها</b> (مجموع: {total})", ""]
    if users:
        for index, referred_user in enumerate(
            users, start=(page - 1) * _REFERRAL_PAGE_SIZE + 1
        ):
            display_name = referred_user.name or referred_user.telegram_name or "بدون نام"
            status_icon = (
                "✅"
                if referred_user.registration_status is RegistrationStatus.REGISTERED
                else "⏳"
            )
            lines.append(f"{index}. {status_icon} {escape(display_name)}")
        lines.append("")
        lines.append("✅ ثبت‌نام شده | ⏳ در انتظار ثبت‌نام")
    else:
        lines.append("هنوز کسی با لینک شما وارد ربات نشده است.")

    if callback.message:
        await edit_message_if_changed(
            message=callback.message,
            text="\n".join(lines),
            reply_markup=referral_list_keyboard(
                page=page,
                total_pages=total_pages,
            ),
            parse_mode="HTML",
        )
    await callback.answer()
