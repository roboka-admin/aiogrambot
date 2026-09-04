from aiogram import F, Router
from aiogram.types import CallbackQuery

from keyboards.force_subscription import force_subscription_keyboard
from services.force_subscription import ForceSubscriptionService

router = Router()


@router.callback_query(F.data == "force_subscription_check")
async def check_force_subscription_handler(
    callback: CallbackQuery,
    force_subscription_service: ForceSubscriptionService,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    result = await force_subscription_service.check_membership(
        user_telegram_id=callback.from_user.id,
    )

    if result.is_allowed:
        await force_subscription_service.record_successful_membership_check(
            user_telegram_id=callback.from_user.id,
            result=result,
        )
        await callback.answer("✅ عضویت شما تأیید شد. حالا می‌توانید از ربات استفاده کنید.")
        if callback.message is not None:
            await callback.message.delete()
        return

    await callback.answer(
        "❌ هنوز در همه موارد موردنیاز عضو نشده‌اید.",
        show_alert=True,
    )

    if callback.message is not None:
        await callback.message.edit_reply_markup(
            reply_markup=force_subscription_keyboard(
                list(result.missing_targets)
            )
        )
