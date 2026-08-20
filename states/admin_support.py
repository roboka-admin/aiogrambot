from aiogram.fsm.state import State, StatesGroup


class AdminSupportStates(StatesGroup):
    waiting_reply = State()
