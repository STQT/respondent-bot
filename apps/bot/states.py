from aiogram.fsm.state import State, StatesGroup

class RegisterForm(StatesGroup):
    get_gender = State()
    get_age = State()
    get_education = State()
    get_location = State()

class PollStates(StatesGroup):
    waiting_for_answer = State()
    waiting_for_custom_answer = State()
