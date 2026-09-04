from aiogram.types import InlineKeyboardButton

from callbacks.admin import (
    AdminForceSubscriptionStatsTargetCallback,
    AdminForceSubscriptionStatsTargetRefreshCallback,
    AdminStatsCallback,
)
from keyboards.admin_stats import force_subscription_stats_keyboard
from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType


def _target(chat_id: int, title: str, active: bool = True) -> ForceSubscriptionTarget:
    return ForceSubscriptionTarget(
        chat_id=chat_id,
        title=title,
        target_type=ForceSubscriptionTargetType.CHANNEL,
        username=title.lower().replace(" ", "_"),
        is_active=active,
    )


def _button_data(keyboard_button: InlineKeyboardButton) -> str:
    assert keyboard_button.callback_data is not None
    return keyboard_button.callback_data


def test_force_subscription_stats_keyboard_lists_targets_and_navigation() -> None:
    keyboard = force_subscription_stats_keyboard(
        [_target(-1001, "Main Channel"), _target(-1002, "Old Channel", active=False)]
    )

    assert len(keyboard.inline_keyboard) == 3
    assert _button_data(keyboard.inline_keyboard[0][0]) == (
        AdminForceSubscriptionStatsTargetCallback(chat_id=-1001).pack()
    )
    assert _button_data(keyboard.inline_keyboard[1][0]) == (
        AdminForceSubscriptionStatsTargetCallback(chat_id=-1002).pack()
    )
    assert _button_data(keyboard.inline_keyboard[2][0]) == (
        AdminStatsCallback(section="force_subscription").pack()
    ) or _button_data(keyboard.inline_keyboard[2][1]) == (
        AdminStatsCallback(section="dashboard").pack()
    )


def test_target_refresh_callback_contains_target_chat_id() -> None:
    callback_data = AdminForceSubscriptionStatsTargetRefreshCallback(chat_id=-1001).pack()
    assert callback_data == "admin_force_subscription_stats_target_refresh:-1001"
