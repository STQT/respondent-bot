from aiogram.fsm.state import State, StatesGroup

class PollStates(StatesGroup):
    waiting_for_answer = State()
