from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.utils.translation import gettext_lazy as _

from apps.bot.handlers.cart import view_cart
from apps.bot.states import MenuStates
from apps.bot.utils import send_category_list_message, send_languages_message, send_phone_message
from apps.users.models import TGUser
from django.utils.translation import override
from apps.bot.keyboards.markups import CART_BUTTON, CHANGE_LANG_BUTTON

echo_router = Router()


@echo_router.message()
async def echo_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    """
    Handler will forward receive a message back to the sender
    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    if not user.lang:
        await send_languages_message(message, state, user, back_button=False)
    elif not user.phone:
        await send_phone_message(message, state, user)
    else:
        with override(user.lang):
            if message.text == CART_BUTTON:
                await view_cart(message, state, user)
            elif message.text == CHANGE_LANG_BUTTON:
                await send_languages_message(message, state, user, back_button=True)
            else:
                await send_category_list_message(message, state, user)
