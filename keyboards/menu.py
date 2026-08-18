from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👤 پروفایل"),
            KeyboardButton(text="✏️ ویرایش پروفایل"),
        ],
    ],
    resize_keyboard=True,
)

edit_profile_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✏️ تغییر نام")],
        [KeyboardButton(text="🎂 تغییر سن")],
        [KeyboardButton(text="❌ لغو")],
    ],
    resize_keyboard=True,
)
