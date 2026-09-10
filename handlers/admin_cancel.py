from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from core.telegram import edit_message_if_changed
from filters.admin import AdminFilter
from handlers.admin import _show_blocked_users_page, _show_user_management, _show_users_page
from handlers.admin_settings import _settings_text
from keyboards.admin_settings import admin_settings_keyboard
from services.bot_settings import BotSettingsService
from services.user import UserService

router = Router()
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel_handler(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
    bot_settings_service: BotSettingsService,
) -> None:
    data = await state.get_data()
    source = data.get("source", "management")
    page = data.get("page", 0)

    await state.clear()

    if source == "blocked":
        await _show_blocked_users_page(
            message=callback.message,
            user_service=user_service,
            page=page,
            edit=True,
        )
    elif source == "users":
        await _show_users_page(
            message=callback.message,
            user_service=user_service,
            page=page,
            edit=True,
        )
    elif source == "settings":
        settings = await bot_settings_service.get_settings()
        await edit_message_if_changed(
            message=callback.message,
            text=_settings_text(settings),
            reply_markup=admin_settings_keyboard(settings),
        )
    else:
        await _show_user_management(message=callback.message, edit=True)

    await callback.answer("لغو شد.")
