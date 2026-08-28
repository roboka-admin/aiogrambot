from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import AdminStatsCallback, AdminStatsRefreshCallback


def stats_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Main statistics dashboard with 5 buttons in multi-column layout."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 آمار کاربران", callback_data=AdminStatsCallback(section="users").pack()),
            InlineKeyboardButton(text="🆘 آمار پشتیبانی", callback_data=AdminStatsCallback(section="support").pack()),
        ],
        [
            InlineKeyboardButton(text="📢 آمار همگانی", callback_data=AdminStatsCallback(section="broadcast").pack()),
            InlineKeyboardButton(text="🛡️ آمار ضداسپم", callback_data=AdminStatsCallback(section="antispam").pack()),
        ],
        [
            InlineKeyboardButton(text="🖥️ وضعیت سیستم", callback_data=AdminStatsCallback(section="system").pack()),
        ]
    ])


def user_stats_keyboard() -> InlineKeyboardMarkup:
    """User statistics keyboard with refresh and back buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 بروزرسانی", callback_data=AdminStatsRefreshCallback(section="users").pack()),
            InlineKeyboardButton(text="⬅️ آمار و وضعیت", callback_data=AdminStatsCallback(section="dashboard").pack()),
        ],
    ])


def support_stats_keyboard() -> InlineKeyboardMarkup:
    """Support statistics keyboard with refresh and back buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 بروزرسانی", callback_data=AdminStatsRefreshCallback(section="support").pack()),
            InlineKeyboardButton(text="⬅️ آمار و وضعیت", callback_data=AdminStatsCallback(section="dashboard").pack()),
        ],
    ])


def placeholder_stats_keyboard(section: str) -> InlineKeyboardMarkup:
    """Placeholder keyboard for unimplemented statistics sections."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 بروزرسانی", callback_data=AdminStatsRefreshCallback(section=section).pack()),
            InlineKeyboardButton(text="⬅️ آمار و وضعیت", callback_data=AdminStatsCallback(section="dashboard").pack()),
        ],
    ])