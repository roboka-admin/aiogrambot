from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models.force_subscription import ForceSubscriptionTarget

CHECK_CALLBACK = "force_subscription_check"


def force_subscription_keyboard(
    targets: list[ForceSubscriptionTarget],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for target in targets:
        link = target.invite_link
        if not link and target.username:
            link = f"https://t.me/{target.username.lstrip('@')}"
        if link:
            rows.append(
                [InlineKeyboardButton(text=f"📢 {target.title}", url=link)]
            )

    rows.append(
        [InlineKeyboardButton(text="🔄 بررسی عضویت", callback_data=CHECK_CALLBACK)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
