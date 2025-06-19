from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.utils import get_current_question
from apps.users.models import TGUser

start_router = Router()


@start_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext, user: TGUser | None):
    await get_current_question(message, state, user)
