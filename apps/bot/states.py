from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    choose_language = State()
    get_phone_number = State()


class MenuStates(StatesGroup):
    choose_menu = State()
    choose_product = State()
    choose_language = State()


class OrderStates(StatesGroup):
    payment_type = State()
    delivery_address = State()
