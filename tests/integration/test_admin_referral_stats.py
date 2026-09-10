from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.admin_referral_stats import referral_stats_handler
from models.user import User


def _make_callback() -> MagicMock:
    callback = MagicMock()
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.text = "📊 آمار و وضعیت"
    callback.message.edit_text = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_referral_stats_handler_renders_funnel_activity_and_leaderboard():
    callback = _make_callback()
    referral_service = MagicMock()
    referral_service.get_referral_statistics = AsyncMock(
        return_value={
            "total": 42,
            "registered": 30,
            "unregistered": 12,
            "users_with_code": 25,
            "today": 3,
            "last_7_days": 9,
            "last_30_days": 21,
            "top_referrers": [
                (User(telegram_id=1, telegram_name="Ali"), 12),
                (User(telegram_id=2, telegram_name="Sara"), 7),
            ],
            "rewards_paid": 5,
            "rewards_paid_today": 1,
            "coins_rewarded": 25,
        }
    )

    await referral_stats_handler(callback, referral_service)

    text = callback.message.edit_text.await_args.args[0]
    assert "💸 پرداخت‌ها: 5 (امروز: 1)" in text
    assert "مجموع سکه پرداخت‌شده: 25" in text
    assert "🎁 آمار دعوت‌ها" in text
    assert "کل دعوت‌های موفق: 42" in text
    assert "ثبت‌نام‌شده: 30" in text
    assert "در انتظار ثبت‌نام: 12" in text
    assert "نرخ تبدیل: 71.4%" in text
    assert "کاربران دارای لینک دعوت: 25" in text
    assert "امروز: 3" in text
    assert "۷ روز اخیر: 9" in text
    assert "۳۰ روز اخیر: 21" in text
    assert "🏆 برترین دعوت‌کننده‌ها" in text
    assert "Ali — 12 دعوت" in text
    assert "Sara — 7 دعوت" in text
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_referral_stats_handler_handles_zero_referrals_without_leaderboard():
    callback = _make_callback()
    referral_service = MagicMock()
    referral_service.get_referral_statistics = AsyncMock(
        return_value={
            "total": 0,
            "registered": 0,
            "unregistered": 0,
            "users_with_code": 0,
            "today": 0,
            "last_7_days": 0,
            "last_30_days": 0,
            "top_referrers": [],
            "rewards_paid": 0,
            "rewards_paid_today": 0,
            "coins_rewarded": 0,
        }
    )

    await referral_stats_handler(callback, referral_service)

    text = callback.message.edit_text.await_args.args[0]
    assert "نرخ تبدیل: —" in text
    assert "برترین دعوت‌کننده‌ها" not in text
    callback.answer.assert_awaited_once()
