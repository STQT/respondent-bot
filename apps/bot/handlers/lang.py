from aiogram import Router
from aiogram.fsm.context import FSMContext
from django.utils.translation import gettext_lazy as _
from apps.bot.keyboards.markups import TG_LANGUAGES
from apps.bot.states import MenuStates
from apps.bot.handlers.echo import echo_handler
from apps.users.models import TGUser

from aiogram import Router, types
from aiogram.types import Message
from django.utils.translation import gettext_lazy as _


lang_router = Router()


@lang_router.message(MenuStates.choose_language)
async def language_chosen(message: Message, state: FSMContext, user: TGUser | None):
    lang = message.text
    if lang == TG_LANGUAGES[0]: # uzbek
        user.lang = "uz"
    elif lang == TG_LANGUAGES[1]:
        user.lang = "ru"
    await user.asave()
    await echo_handler(message, state, user)
    await state.set_state(MenuStates.choose_menu)
