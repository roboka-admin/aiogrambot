from urllib.parse import quote

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.referral import ReferralListCallback


# Message friends receive when the user taps the share button. It is sent
# from the sharer's own account, so first-person phrasing reads as a genuine
# personal invitation rather than bot-generated spam.
_SHARE_TEXT = "سلام! من از این ربات استفاده می‌کنم 👋 تو هم با این لینک شروع کن:"


def referral_keyboard(*, referral_link: str, has_referrals: bool) -> InlineKeyboardMarkup:
    share_url = (
        "https://t.me/share/url?url="
        f"{quote(referral_link, safe='')}"
        f"&text={quote(_SHARE_TEXT, safe='')}"
    )
    rows = [
        [
            InlineKeyboardButton(
                text="🔗 اشتراک‌گذاری لینک",
                url=share_url,
            )
        ]
    ]
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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            navigation,
            [
                # Raw string on purpose: mirrors the existing "noop"/"admin_cancel"
                # pattern for payload-less buttons, and the button-contract test
                # only resolves string literals in F.data == filters.
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="referral_back",
                )
            ],
        ]
    )
