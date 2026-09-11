from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 پروفایل"), KeyboardButton(text="👥 دعوت دوستان")],
        [KeyboardButton(text="🆘 پشتیبانی")],
    ],
    resize_keyboard=True,
)

support_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ لغو")]],
    resize_keyboard=True,
)
