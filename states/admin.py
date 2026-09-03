from aiogram.fsm.state import State, StatesGroup


class AdminUserStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_coin_amount = State()


class AdminBroadcastStates(StatesGroup):
    waiting_message = State()
    waiting_confirmation = State()


class AdminForceSubscriptionStates(StatesGroup):
    waiting_for_chat = State()
