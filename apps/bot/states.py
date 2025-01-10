from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    choose_language = State()
    get_phone_number = State()


class MenuStates(StatesGroup):
    choose_menu = State()
    choose_product = State()
    # choose_cash_type = State()
