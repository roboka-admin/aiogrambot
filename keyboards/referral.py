from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.referral import ReferralListCallback


def referral_keyboard(*, referral_link: str, has_referrals: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🔗 اشتراک‌گذاری لینک دعوت", url=referral_link)]]
    if has_referrals:
        rows.append(
            [
                InlineKeyboardButton(
                    text="👥 لیست دعوت‌شده‌ها",
                    callback_data=ReferralListCallback(page=1).pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def referral_list_keyboard(*, page: int, total_pages: int) -> InlineKeyboardMarkup:
    navigation: list[InlineKeyboardButton] = []
    if page > 1:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ قبلی",
                callback_data=ReferralListCallback(page=page - 1).pack(),
            )
        )
    navigation.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop")
    )
    if page < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="بعدی ➡️",
                callback_data=ReferralListCallback(page=page + 1).pack(),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[navigation])
