from aiogram.fsm.state import State, StatesGroup


class EditProfileStates(StatesGroup):
    waiting_name = State()
    waiting_age = State()
