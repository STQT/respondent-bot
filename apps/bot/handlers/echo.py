from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from apps.users.models import TGUser
from apps.products.models import Category
from apps.bot.keyboards.markups import make_row_keyboard
from apps.bot.states import MenuStates

# For each module with handlers we can create a separate router.
echo_router = Router()


@echo_router.message()
async def echo_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    """
    Handler will forward receive a message back to the sender

    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    lang = user.lang
    lang_str = f'name_{lang}'
    menus = []
    async for category in Category.objects.values('name_ru', 'name_uz'):
        name_uz_data = category['name_uz']
        menus.append(category.pop(lang_str, name_uz_data))
    await message.answer("ECHO:", reply_markup=make_row_keyboard(menus))
    await state.set_state(MenuStates.choose_menu)

    # try:
    #     # Send a copy of the received message
    #     await message.send_copy(chat_id=message.chat.id)
    # except TypeError:
    #     # But not all the types is supported to be copied so need to handle it
    #     await message.answer("Nice try!")
