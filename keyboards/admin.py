from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👤 کاربران"),
            KeyboardButton(text="📊 آمار"),
        ],
        [
            KeyboardButton(text="📢 ارسال همگانی"),
            KeyboardButton(text="⚙️ تنظیمات"),
        ],
    ],
    resize_keyboard=True,
)
