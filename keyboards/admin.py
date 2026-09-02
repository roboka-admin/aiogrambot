from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 کاربران")],
        [KeyboardButton(text="📩 پشتیبانی")],
        [
            KeyboardButton(text="📊 آمار"),
            KeyboardButton(text="📢 ارسال همگانی"),
        ],
        [KeyboardButton(text="⚙️ تنظیمات ربات")],
    ],
    resize_keyboard=True,
)
