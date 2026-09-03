from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from filters.admin import AdminFilter
from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from services.force_subscription import ForceSubscriptionService
from states.admin import AdminForceSubscriptionStates
from keyboards.admin_force_subscription import admin_force_subscription_keyboard, admin_force_subscription_list_keyboard

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.message(F.text == "📢 عضویت اجباری")
async def force_subscription_menu_handler(
    message: Message,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    targets = await force_subscription_service.list_all_targets()
    await message.answer(
        _management_text(targets),
        reply_markup=admin_force_subscription_list_keyboard(targets),
    )


@router.callback_query(F.data == "admin_force_subscription_manage")
async def manage_force_subscription_handler(
    callback: CallbackQuery,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    await _show_management(callback, force_subscription_service)


@router.callback_query(F.data == "admin_force_subscription_add")
async def add_force_subscription_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminForceSubscriptionStates.waiting_for_chat)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            "➕ افزودن کانال یا گروه\n\n"
            "آیدی یا نام کاربری عمومی کانال/گروه را ارسال کنید.\n"
            "مثال: @my_channel یا -1001234567890\n\n"
            "⚠️ ربات باید داخل کانال/گروه حضور داشته باشد."
        )


@router.message(AdminForceSubscriptionStates.waiting_for_chat)
async def receive_force_subscription_chat(
    message: Message,
    state: FSMContext,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("❌ لطفاً آیدی یا نام کاربری معتبر ارسال کنید.")
        return

    try:
        target = await force_subscription_service.resolve_target(value)
        await force_subscription_service.add_target(target)
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.clear()
    await message.answer(
        f"✅ «{target.title}» به فهرست عضویت اجباری اضافه شد.",
        reply_markup=admin_force_subscription_keyboard(),
    )


@router.callback_query(F.data == "admin_force_subscription_list")
async def list_force_subscription_handler(
    callback: CallbackQuery,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    await _show_management(callback, force_subscription_service)


@router.callback_query(F.data.startswith("admin_force_subscription_delete:"))
async def delete_force_subscription_handler(
    callback: CallbackQuery,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    deleted = await force_subscription_service.delete_target(chat_id)
    await callback.answer("✅ حذف شد." if deleted else "⚠️ مورد پیدا نشد.")
    await _show_management(callback, force_subscription_service)


@router.callback_query(F.data.startswith("admin_force_subscription_toggle:"))
async def toggle_force_subscription_target_handler(
    callback: CallbackQuery,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    target = await force_subscription_service.toggle_target(chat_id)
    await callback.answer("وضعیت مقصد تغییر کرد." if target else "⚠️ مورد پیدا نشد.")
    await _show_management(callback, force_subscription_service)


async def _show_management(callback: CallbackQuery, service: ForceSubscriptionService) -> None:
    targets = await service.list_all_targets()
    text = _management_text(targets)
    keyboard = admin_force_subscription_list_keyboard(targets)
    if callback.message is not None:
        if callback.message.text != text or callback.message.reply_markup != keyboard:
            await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


def _management_text(targets: list[ForceSubscriptionTarget]) -> str:
    lines = ["📢 مدیریت عضویت اجباری", ""]
    if not targets:
        lines.append("هنوز هیچ کانال یا گروهی اضافه نشده است.")
    else:
        lines.append("مقصدها:")
        for index, target in enumerate(targets, 1):
            status = "🟢 فعال" if target.is_active else "⚪ غیرفعال"
            kind = "کانال" if target.target_type is ForceSubscriptionTargetType.CHANNEL else "گروه"
            lines.append(f"{index}. {kind} — {target.title} — {status}")
    lines.extend(["", "عضویت اجباری فقط برای مقصدهای فعال اعمال می‌شود."])
    return "\n".join(lines)
