from aiogram import F, Router
from aiogram.types import CallbackQuery

from core.telegram import edit_reply_markup_if_changed
from handlers.start import send_welcome
from keyboards.force_subscription import force_subscription_keyboard
from models.user import User
from services.force_subscription import ForceSubscriptionService
from services.notification import NotificationService
from services.referral import ReferralService

router = Router()


@router.callback_query(F.data == "force_subscription_check")
async def check_force_subscription_handler(
    callback: CallbackQuery,
    user: User,
    force_subscription_service: ForceSubscriptionService,
    referral_service: ReferralService,
    notification_service: NotificationService,
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
        # The invite stashed while this user was blocked is only attributed
        # now that membership is verified.
        referrer_id = await referral_service.claim_pending_referral(
            telegram_id=callback.from_user.id,
        )
        if referrer_id is not None:
            total = await referral_service.get_referral_count(referrer_id)
            await notification_service.referral_joined(
                referrer_id, callback.from_user.first_name, total
            )
        await callback.answer("✅ عضویت شما تأیید شد. حالا می‌توانید از ربات استفاده کنید.")
        if callback.message is not None:
            # The blocked /start never reached its handler, so the welcome
            # (with the register button or the main menu) is re-sent here
            # instead of leaving the user with an empty chat.
            await callback.message.delete()
            await send_welcome(
                callback.message, user, callback.from_user.first_name
            )
        return

    await callback.answer(
        "❌ هنوز در همه موارد موردنیاز عضو نشده‌اید.",
        show_alert=True,
    )

    # The keyboard is only refreshed when the missing targets actually
    # changed; re-tapping the button with identical markup used to raise
    # "message is not modified" from Telegram.
    await edit_reply_markup_if_changed(
        message=callback.message,
        reply_markup=force_subscription_keyboard(
            list(result.missing_targets)
        ),
    )
