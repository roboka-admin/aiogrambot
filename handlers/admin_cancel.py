from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from filters.admin import AdminFilter
from handlers.admin import _show_blocked_users_page, _show_user_management, _show_users_page
from services.user import UserService

router = Router()
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel_handler(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
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
    else:
        await _show_user_management(message=callback.message, edit=True)

    await callback.answer("لغو شد.")


@router.callback_query(F.data == "noop")
async def noop_callback_handler(callback: CallbackQuery) -> None:
    """Acknowledge non-action pagination indicators without changing the message."""
    await callback.answer()
