from aiogram.fsm.state import State, StatesGroup


class PollStates(StatesGroup):
    waiting_for_answer = State()
    waiting_for_mixed_custom_input = State()
    waiting_for_captcha = State()


class WithdrawalStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment_details = State()
