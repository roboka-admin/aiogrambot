from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import AdminReferralRewardCallback
from models.bot_settings import BotSettings


# (coins, invites) one-tap presets shown under the steppers.
REWARD_PRESETS: tuple[tuple[int, int], ...] = ((1, 1), (5, 3), (10, 5))


def admin_referral_reward_keyboard(settings: BotSettings) -> InlineKeyboardMarkup:
    """Stepper-style editor: every tap saves immediately and redraws in place.

    Callback literals are written inline (not via a helper) so the
    button-contract test can resolve each ``action`` to its handler.
    """
    coins = settings.referral_reward_coins
    invites = settings.referral_reward_per_invites

    # "➖" is hidden at 1 instead of disabled: Telegram has no disabled
    # buttons, and a no-op tap would just look broken.
    coins_row: list[InlineKeyboardButton] = []
    if coins > 1:
        coins_row.append(
            InlineKeyboardButton(
                text="➖",
                callback_data=AdminReferralRewardCallback(action="coins", delta=-1).pack(),
            )
        )
    coins_row.append(InlineKeyboardButton(text=f"🪙 {coins} سکه", callback_data="noop"))
    coins_row.append(
        InlineKeyboardButton(
            text="➕",
            callback_data=AdminReferralRewardCallback(action="coins", delta=1).pack(),
        )
    )

    invites_row: list[InlineKeyboardButton] = []
    if invites > 1:
        invites_row.append(
            InlineKeyboardButton(
                text="➖",
                callback_data=AdminReferralRewardCallback(action="invites", delta=-1).pack(),
            )
        )
    invites_row.append(
        InlineKeyboardButton(text=f"👥 هر {invites} دعوت", callback_data="noop")
    )
    invites_row.append(
        InlineKeyboardButton(
            text="➕",
            callback_data=AdminReferralRewardCallback(action="invites", delta=1).pack(),
        )
    )

    preset_row = [
        InlineKeyboardButton(
            text=("✅ " if (c, n) == (coins, invites) else "") + f"{c} سکه / {n} دعوت",
            callback_data=AdminReferralRewardCallback(
                action="preset", delta=c, value=n
            ).pack(),
        )
        for c, n in REWARD_PRESETS
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            coins_row,
            invites_row,
            preset_row,
            [
                InlineKeyboardButton(
                    text="✏️ ورود دستی",
                    callback_data=AdminReferralRewardCallback(action="manual").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 آخرین پاداش‌ها",
                    callback_data=AdminReferralRewardCallback(action="history").pack(),
                ),
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data=AdminReferralRewardCallback(action="back").pack(),
                ),
            ],
        ]
    )


def admin_referral_reward_history_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data=AdminReferralRewardCallback(action="open").pack(),
                )
            ],
        ]
    )


def admin_referral_reward_manual_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ لغو",
                    callback_data=AdminReferralRewardCallback(action="open").pack(),
                )
            ],
        ]
    )
