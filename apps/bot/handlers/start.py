import re

from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.utils.translation import gettext_lazy as _

from apps.bot.keyboards.markups import get_language_keyboards, TG_LANGUAGES, get_phone_keyboard, make_row_keyboard
from apps.bot.states import RegistrationStates, MenuStates
from apps.bot.utils import async_get_or_create_user, send_category_list_message
from apps.users.models import TGUser

start_router = Router()
uzbekistan_phone_regex = re.compile(r"^\+998\d{9}$")


@start_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    """
    This handler receives messages with `/start` command
    """
    obj, _created = await async_get_or_create_user(
        id=message.from_user.id,
        defaults={
            "fullname": message.from_user.full_name,
            "username": message.from_user.username
        }
    )
    if not obj.lang:
        await message.answer(
            str(_("ToshmiOsh telegram botiga xush kelibsiz, <b>{full_name}!</b>\n"
                  "Tilni tanlang")).format(
                full_name=message.from_user.full_name),
            resize_keyboard=True,
            reply_markup=get_language_keyboards()
        )
        await state.set_state(RegistrationStates.choose_language)
    elif not obj.phone:
        await message.answer(
            text=str(_("Botdan foydalanish uchun telefon raqamingiz yuboring.")),
            reply_markup=get_phone_keyboard()
        )
        await state.set_state(RegistrationStates.get_phone_number)
    else:
        await send_category_list_message(message, state, user)


@start_router.message(
    RegistrationStates.choose_language,
    F.text.in_(TG_LANGUAGES)
)
async def language_chosen(message: Message, state: FSMContext):
    await state.update_data(lang=message.text) # TODO: need to convert text |uz |ru
    await message.answer(
        text=str(_("Botdan foydalanish uchun telefon raqamingiz yuboring.")),
        reply_markup=get_phone_keyboard()
    )
    await state.set_state(RegistrationStates.get_phone_number)


@start_router.message(
    RegistrationStates.get_phone_number,
    F.content_type.in_({types.ContentType.CONTACT, types.ContentType.TEXT})
)
async def phone_getting(message: Message, state: FSMContext, user: TGUser | None):
    if message.contact:
        contact = message.contact.phone_number
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
        await message.answer("Iltimos faqat O'zbekistonga tegishli raqamni yuboring")
        # Сохраняем состояние ожидания
        await state.set_state(RegistrationStates.get_phone_number)
