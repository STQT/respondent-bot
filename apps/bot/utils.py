from django.core.cache import cache
from django.db import IntegrityError

from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from apps.users.models import TGUser
from apps.bot.states import MenuStates
from apps.products.models import Category
from apps.bot.keyboards.markups import make_row_keyboard


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
    await message.answer("ECHO:", reply_markup=make_row_keyboard(menus))
    await state.set_state(MenuStates.choose_menu)
