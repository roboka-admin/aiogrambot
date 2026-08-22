from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks.admin_support import (
    AdminSupportActionCallback,
    AdminSupportBackCallback,
    AdminSupportCleanupCallback,
    AdminSupportCleanupCancelCallback,
    AdminSupportCleanupConfirmCallback,
    AdminSupportListCallback,
    AdminSupportSettingsBackCallback,
    AdminSupportSettingsCallback,
    AdminSupportTicketCallback,
    AdminSupportUserCallback,
    CleanupAction,
)
from models.support import SupportStatus, SupportTicket, SupportUserSummary


def support_overview_keyboard(*, open_count: int, closed_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 باز ({open_count})",
                    callback_data=AdminSupportListCallback(
                        status=SupportStatus.OPEN.value,
                        page=0,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=f"⚪ بسته ({closed_count})",
                    callback_data=AdminSupportListCallback(
                        status=SupportStatus.CLOSED.value,
                        page=0,
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ تنظیمات پشتیبانی",
                    callback_data=AdminSupportSettingsCallback().pack(),
                )
            ],
        ]
    )


def support_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 حذف تیکت‌های بسته",
                    callback_data=AdminSupportCleanupCallback(
                        action=CleanupAction.DELETE_CLOSED,
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚠️ حذف همه تیکت‌ها",
                    callback_data=AdminSupportCleanupCallback(
                        action=CleanupAction.DELETE_ALL,
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ بازگشت",
                    callback_data=AdminSupportSettingsBackCallback().pack(),
                )
            ],
        ]
    )


def support_users_keyboard(*, users: list[SupportUserSummary], status: SupportStatus, page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for summary in users:
        builder.button(
            text=f"👤 {summary.user_telegram_id} | 📩 {summary.ticket_count}",
            callback_data=AdminSupportUserCallback(
                telegram_id=summary.user_telegram_id,
                status=status.value,
                page=page,
            ).pack(),
        )
    builder.adjust(1)
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ قبلی",
                callback_data=AdminSupportListCallback(
                    status=status.value,
                    page=page - 1,
                ).pack(),
            )
        )
    if page < total_pages - 1:
        navigation.append(
            InlineKeyboardButton(
                text="بعدی ➡️",
                callback_data=AdminSupportListCallback(
                    status=status.value,
                    page=page + 1,
                ).pack(),
            )
        )
    if navigation:
        builder.row(*navigation)
    builder.button(text="⬅️ بازگشت", callback_data=AdminSupportBackCallback().pack())
    return builder.as_markup()


def support_user_messages_keyboard(*, telegram_id: int, status: SupportStatus, page: int, tickets: list[SupportTicket]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ticket in tickets:
        if ticket.id is None:
            continue
        builder.button(
            text=f"🎫 #{ticket.id}",
            callback_data=AdminSupportTicketCallback(
                ticket_id=ticket.id,
                telegram_id=telegram_id,
                status=status.value,
                page=page,
            ).pack(),
        )
    builder.adjust(3)

    action = "reopen" if status is SupportStatus.CLOSED else "close"
    action_text = "🟢 باز کردن گفتگو" if status is SupportStatus.CLOSED else "🔒 بستن گفتگو"

    builder.row(
        InlineKeyboardButton(
            text="✉️ پاسخ به کاربر",
            callback_data=AdminSupportActionCallback(
                action="reply",
                telegram_id=telegram_id,
                status=status.value,
                page=page,
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=action_text,
            callback_data=AdminSupportActionCallback(
                action=action,
                telegram_id=telegram_id,
                status=status.value,
                page=page,
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ بازگشت به کاربران",
            callback_data=AdminSupportListCallback(
                status=status.value,
                page=page,
            ).pack(),
        )
    )
    return builder.as_markup()


def support_ticket_reply_keyboard(*, telegram_id: int, status: SupportStatus, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✉️ پاسخ",
                callback_data=AdminSupportActionCallback(
                    action="reply",
                    telegram_id=telegram_id,
                    status=status.value,
                    page=page,
                ).pack(),
            )
        ]]
    )


def admin_support_reply_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ لغو")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def support_notification_reply_keyboard(*, telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✉️ پاسخ",
                callback_data=AdminSupportActionCallback(
                    action="reply",
                    telegram_id=telegram_id,
                    status=SupportStatus.OPEN.value,
                    page=0,
                ).pack(),
            )
        ]]
    )


def support_cleanup_confirm_keyboard(*, action: CleanupAction) -> InlineKeyboardMarkup:
    confirm_text = (
        "🗑 بله، حذف تیکت‌های بسته"
        if action is CleanupAction.DELETE_CLOSED
        else "⚠️ بله، حذف همه تیکت‌ها"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=confirm_text,
                callback_data=AdminSupportCleanupConfirmCallback(action=action).pack(),
            ),
            InlineKeyboardButton(
                text="❌ لغو",
                callback_data=AdminSupportCleanupCancelCallback().pack(),
            ),
        ]]
    )
