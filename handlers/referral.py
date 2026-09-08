from math import ceil

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.utils.deep_linking import create_start_link

from callbacks.referral import ReferralListCallback
from core.telegram import edit_message_if_changed
from keyboards.referral import referral_keyboard, referral_list_keyboard
from middlewares.registration import RegistrationRequiredMiddleware
from models.user import User
from services.referral import ReferralService


_REFERRAL_PAGE_SIZE = 10

router = Router()
router.message.middleware(RegistrationRequiredMiddleware())
router.callback_query.middleware(RegistrationRequiredMiddleware())


@router.message(F.text == "👥 دعوت دوستان")
async def referral_handler(
    message: Message,
    user: User,
    referral_service: ReferralService,
) -> None:
    code = await referral_service.ensure_referral_code(user.telegram_id)
    count = await referral_service.get_referral_count(user.telegram_id)
    referral_link = await create_start_link(message.bot, code)

    await message.answer(
        "👥 دعوت دوستان\n\n"
        "لینک دعوت اختصاصی شما:\n"
        f"{referral_link}\n\n"
        f"👤 تعداد دعوت‌های موفق: {count}\n\n"
        "لینک را برای دوستانتان ارسال کنید تا با شروع ربات، دعوت شما ثبت شود.",
        reply_markup=referral_keyboard(
            referral_link=referral_link,
            has_referrals=count > 0,
        ),
    )


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

    lines = ["👥 دعوت‌شده‌های شما", ""]
    if users:
        for index, referred_user in enumerate(
            users, start=(page - 1) * _REFERRAL_PAGE_SIZE + 1
        ):
            display_name = referred_user.name or referred_user.telegram_name or "بدون نام"
            lines.append(f"{index}. {display_name}")
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
        )
    await callback.answer()
