from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.utils.translation import gettext_lazy as _

from apps.bot.utils import get_current_question
from apps.users.models import TGUser
from django.utils.translation import override

echo_router = Router()


@echo_router.message()
async def echo_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    """
    Handler will forward receive a message back to the sender
    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    # with override(user.lang):
    await get_current_question(message, state, user)
