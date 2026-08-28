from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks.admin import AdminStatsCallback, AdminStatsRefreshCallback


def stats_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Main statistics dashboard with a balanced multi-column layout."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 آمار کاربران",
                    callback_data=AdminStatsCallback(section="users").pack(),
                ),
                InlineKeyboardButton(
                    text="🆘 آمار پشتیبانی",
                    callback_data=AdminStatsCallback(section="support").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 آمار همگانی",
                    callback_data=AdminStatsCallback(section="broadcast").pack(),
                ),
                InlineKeyboardButton(
                    text="🛡️ آمار ضداسپم",
                    callback_data=AdminStatsCallback(section="antispam").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🖥️ وضعیت سیستم",
                    callback_data=AdminStatsCallback(section="system").pack(),
                ),
            ],
        ]
    )


def _stats_page_keyboard(section: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 بروزرسانی",
                    callback_data=AdminStatsRefreshCallback(section=section).pack(),
                ),
                InlineKeyboardButton(
                    text="⬅️ آمار و وضعیت",
                    callback_data=AdminStatsCallback(section="dashboard").pack(),
                ),
            ],
        ]
    )


def user_stats_keyboard() -> InlineKeyboardMarkup:
    return _stats_page_keyboard("users")


def support_stats_keyboard() -> InlineKeyboardMarkup:
    return _stats_page_keyboard("support")


def broadcast_stats_keyboard() -> InlineKeyboardMarkup:
    return _stats_page_keyboard("broadcast")


def antispam_stats_keyboard() -> InlineKeyboardMarkup:
    return _stats_page_keyboard("antispam")


def placeholder_stats_keyboard(section: str) -> InlineKeyboardMarkup:
    """Keyboard for statistics sections that are not implemented yet."""
    return _stats_page_keyboard(section)
