from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.utils.translation import gettext_lazy as _

from apps.bot.handlers.cart import view_cart
from apps.bot.utils import send_category_list_message
from apps.users.models import TGUser


echo_router = Router()


@echo_router.message()
async def echo_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    """
    Handler will forward receive a message back to the sender

    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    if message.text == str(_("Savat")):
        await view_cart(message, state, user)
    else:
        await send_category_list_message(message, state, user)
