from aiogram import Router
from aiogram.types import CallbackQuery

from callbacks.admin_support import (
    AdminSupportSettingsBackCallback,
    AdminSupportSettingsCallback,
)
from filters.admin import AdminPermissionFilter
from keyboards.admin_support import (
    support_overview_keyboard,
    support_settings_keyboard,
)
from models.support import SupportStatus
from services.support import SupportService


router = Router()
router.callback_query.filter(AdminPermissionFilter("support"))


@router.callback_query(AdminSupportSettingsCallback.filter())
async def support_settings_handler(
    callback: CallbackQuery,
) -> None:
    await callback.message.edit_text(
        "⚙️ تنظیمات پشتیبانی\n\n"
        "عملیات مورد نظر را انتخاب کنید:",
        reply_markup=support_settings_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminSupportSettingsBackCallback.filter())
async def support_settings_back_handler(
    callback: CallbackQuery,
    support_service: SupportService,
) -> None:
    open_users = await support_service.get_support_users_by_status(SupportStatus.OPEN)
    closed_users = await support_service.get_support_users_by_status(SupportStatus.CLOSED)

    await callback.message.edit_text(
        "📩 مدیریت پشتیبانی\n\n"
        f"🟢 کاربران با پیام باز: {len(open_users)}\n"
        f"⚪ کاربران با پیام بسته: {len(closed_users)}\n\n"
        "یک بخش را انتخاب کنید:",
        reply_markup=support_overview_keyboard(
            open_count=len(open_users),
            closed_count=len(closed_users),
        ),
    )
    await callback.answer()
