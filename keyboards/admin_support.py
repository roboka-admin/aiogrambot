from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks.admin_support import AdminSupportBackCallback, AdminSupportListCallback, AdminSupportUserCallback
from models.support import SupportStatus, SupportUserSummary


def support_overview_keyboard(*, open_count: int, closed_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🟢 باز ({open_count})", callback_data=AdminSupportListCallback(status=SupportStatus.OPEN.value, page=0).pack()), InlineKeyboardButton(text=f"⚪ بسته ({closed_count})", callback_data=AdminSupportListCallback(status=SupportStatus.CLOSED.value, page=0).pack())]])


def support_users_keyboard(*, users: list[SupportUserSummary], status: SupportStatus, page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for summary in users:
        builder.button(text=f"👤 {summary.user_telegram_id} | 📩 {summary.ticket_count}", callback_data=AdminSupportUserCallback(telegram_id=summary.user_telegram_id, status=status.value, page=page).pack())
    builder.adjust(1)
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=AdminSupportListCallback(status=status.value, page=page - 1).pack()))
    if page < total_pages - 1:
        navigation.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=AdminSupportListCallback(status=status.value, page=page + 1).pack()))
    if navigation:
        builder.row(*navigation)
    builder.button(text="⬅️ بازگشت", callback_data=AdminSupportBackCallback().pack())
    return builder.as_markup()


def support_user_messages_keyboard(*, status: SupportStatus, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ بازگشت به کاربران", callback_data=AdminSupportListCallback(status=status.value, page=page).pack())]])
