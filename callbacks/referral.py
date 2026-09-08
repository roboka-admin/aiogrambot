from aiogram.filters.callback_data import CallbackData


class ReferralListCallback(CallbackData, prefix="referral_list"):
    page: int
