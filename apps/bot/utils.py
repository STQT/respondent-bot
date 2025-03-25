from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _

from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from django.utils.translation import override

from apps.users.models import TGUser
from apps.bot.states import MenuStates, RegistrationStates
from apps.products.models import Category
from apps.bot.keyboards.markups import get_language_keyboards, get_phone_keyboard, make_row_keyboard


async def async_get_or_create_user(defaults=None, **kwargs):
    """
    Async equivalent of Django's get_or_create.
    """
    defaults = defaults or {}
    try:
        # Try to get the object
        obj = await TGUser.objects.aget(**kwargs)
        created = False
    except TGUser.DoesNotExist:
        # Object does not exist, attempt to create it
        try:
            obj = await TGUser.objects.acreate(**{**kwargs, **defaults})
            created = True
        except IntegrityError:
            # Handle a race condition where the object was created between `aget` and `acreate`
            obj = await TGUser.objects.aget(**kwargs)
            created = False
    return obj, created


async def send_category_list_message(message: Message, state: FSMContext, user: TGUser | None):
    lang = user.lang
    lang_str = f'name_{lang}'
    menus = []
    async for category in Category.objects.values('name_ru', 'name_uz'):
        name_uz_data = category['name_uz']
        menus.append(category.pop(lang_str, name_uz_data))
    with override(user.lang):
        print("HEREEE", user.lang)
        await message.answer(
            str(_("Ushbu botdan foydalanish uchun quyidagi tugmalardan foydalaning👇")),
            reply_markup=make_row_keyboard(menus, lang=lang))
    await state.set_state(MenuStates.choose_menu)


async def send_languages_message(message: Message, state: FSMContext, user: TGUser | None, back_button=True):
    await message.answer(
        str(_("Iltimos, kerakli tilni tanlang👇")),
        reply_markup=get_language_keyboards(back_button=back_button))
    await state.set_state(MenuStates.choose_language)


async def send_phone_message(message: Message, state: FSMContext, user: TGUser | None):
    with override(user.lang):
        await message.answer(
            text=str(_("Botdan foydalanish uchun telefon raqamingiz yuboring.")),
            reply_markup=get_phone_keyboard()
        )
        await state.set_state(RegistrationStates.get_phone_number)