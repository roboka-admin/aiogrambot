from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.force_subscription import check_force_subscription_handler
from keyboards.force_subscription import CHECK_CALLBACK, force_subscription_keyboard
from models.force_subscription import ForceSubscriptionTarget, ForceSubscriptionTargetType
from services.force_subscription import (
    MembershipCheckResult,
    MembershipStatus,
    TargetMembershipResult,
)


def make_target(
    chat_id: int,
    title: str,
    *,
    username: str | None = None,
    invite_link: str | None = None,
):
    return ForceSubscriptionTarget(
        chat_id=chat_id,
        title=title,
        target_type=ForceSubscriptionTargetType.CHANNEL,
        username=username,
        invite_link=invite_link,
    )


def test_keyboard_has_join_buttons_and_check_button() -> None:
    first = make_target(-1001, "News", username="news_channel")
    second = make_target(-1002, "Private", invite_link="https://t.me/+abc")

    keyboard = force_subscription_keyboard([first, second])

    assert keyboard.inline_keyboard[-1][0].callback_data == CHECK_CALLBACK
    assert keyboard.inline_keyboard[0][0].text == "📢 News"
    assert keyboard.inline_keyboard[0][0].url == "https://t.me/news_channel"
    assert keyboard.inline_keyboard[1][0].text == "📢 Private"
    assert keyboard.inline_keyboard[1][0].url == "https://t.me/+abc"


def test_keyboard_does_not_create_fake_link_when_target_has_no_link() -> None:
    target = make_target(-1001, "Private channel")

    keyboard = force_subscription_keyboard([target])

    assert len(keyboard.inline_keyboard) == 1
    assert keyboard.inline_keyboard[0][0].callback_data == CHECK_CALLBACK


@pytest.mark.asyncio
async def test_check_handler_deletes_requirement_message_after_success() -> None:
    callback = MagicMock()
    callback.from_user = MagicMock(id=10)
    callback.message = MagicMock()
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()

    service = MagicMock()
    service.check_membership = AsyncMock(
        return_value=MembershipCheckResult(is_allowed=True, targets=())
    )
    service.record_successful_membership_check = AsyncMock()

    await check_force_subscription_handler(callback, service)

    service.check_membership.assert_awaited_once_with(user_telegram_id=10)
    service.record_successful_membership_check.assert_awaited_once_with(
        user_telegram_id=10,
        result=MembershipCheckResult(is_allowed=True, targets=()),
    )
    callback.message.delete.assert_awaited_once()
    callback.answer.assert_awaited_once_with(
        "✅ عضویت شما تأیید شد. حالا می‌توانید از ربات استفاده کنید."
    )


@pytest.mark.asyncio
async def test_check_handler_keeps_message_when_membership_is_missing() -> None:
    missing = make_target(-1001, "News", username="news_channel")
    callback = MagicMock()
    callback.from_user = MagicMock(id=10)
    callback.message = MagicMock()
    callback.message.delete = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()

    service = MagicMock()
    service.check_membership = AsyncMock(
        return_value=MembershipCheckResult(
            is_allowed=False,
            targets=(TargetMembershipResult(missing, MembershipStatus.LEFT),),
        )
    )

    await check_force_subscription_handler(callback, service)

    callback.message.delete.assert_not_called()
    callback.answer.assert_awaited_once_with(
        "❌ هنوز در همه موارد موردنیاز عضو نشده‌اید.",
        show_alert=True,
    )
    callback.message.edit_reply_markup.assert_awaited_once()
