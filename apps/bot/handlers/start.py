import re

from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override

from apps.bot.keyboards.markups import get_language_keyboards, TG_LANGUAGES
from apps.bot.states import RegistrationStates, MenuStates
from apps.bot.utils import send_category_list_message, send_phone_message
from apps.users.models import TGUser

start_router = Router()
uzbekistan_phone_regex = re.compile(r"^\+998\d{9}$")


@start_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    """
    This handler receives messages with `/start` command
    """
    if not user.lang:
        await message.answer(
            ("ToshmiOsh telegram botiga xush kelibsiz, <b>{full_name}!</b>\n"
             "Tilni tanlang\n\n"
             "Добро пожаловать в бот ToshmiOsh, <b>{full_name}!</b>\n"
             "Выберите язык"
             ).format(
                full_name=message.from_user.full_name),
            resize_keyboard=True,
            reply_markup=get_language_keyboards()
        )
        await state.set_state(RegistrationStates.choose_language)
    elif not user.phone:
        await send_phone_message(message, state, user)
    else:
        with override(user.lang):
            await send_category_list_message(message, state, user)


@start_router.message(RegistrationStates.choose_language)
async def language_chosen(message: Message, state: FSMContext, user: TGUser | None):
    lang = message.text
    if lang == TG_LANGUAGES[0]: # uzbek
        user.lang = "uz"
    elif lang == TG_LANGUAGES[1]:
        user.lang = "ru"
    else:
        return await message.answer(text=str(_("Quyidagi tugmalardan foydalaning👇")))
    await user.asave()
    await send_phone_message(message, state, user)
    await state.set_state(RegistrationStates.get_phone_number)


@start_router.message(
    RegistrationStates.get_phone_number,
    F.content_type.in_({types.ContentType.CONTACT, types.ContentType.TEXT})
)
async def phone_getting(message: Message, state: FSMContext, user: TGUser | None):
    if message.contact:
        contact = "+" + message.contact.phone_number
    else:
        contact = message.text
    if uzbekistan_phone_regex.match(contact):
        user.phone = contact
        await user.asave()
        await send_category_list_message(message, state, user)
        # Сброс состояния
        await state.clear()
        await state.set_state(MenuStates.choose_menu)
    else:
        await message.answer(str(_("Iltimos faqat O'zbekistonga tegishli raqamni yuboring")))
        # Сохраняем состояние ожидания
        await state.set_state(RegistrationStates.get_phone_number)
