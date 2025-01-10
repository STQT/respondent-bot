from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.utils.translation import gettext_lazy as _

from apps.bot.keyboards.inline import product_inline_kb
from apps.bot.keyboards.markups import make_row_keyboard, get_cash_type_keyboards
from apps.bot.states import MenuStates
from apps.users.models import TGUser

menu_router = Router()


@menu_router.message(MenuStates.choose_menu)
async def menu_choose_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    menu_name = message.text
    if menu_name in ("name", "name1"):
        await state.update_data(category=message.text)
        products = ["product", "product1"]
        await message.answer(message.text, reply_markup=make_row_keyboard(products))
        await state.set_state(MenuStates.choose_product)
    else:
        await message.answer(str(_("Quyida ko'rsatilgan tugmadan birontasini tanlang 👇")))


@menu_router.message(MenuStates.choose_product)
async def product_choose_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    menu_name = message.text
    if menu_name in ("product", "product1"):
        await message.answer("product description", reply_markup=product_inline_kb("1"))
    else:
        await message.answer(str(_("Quyida ko'rsatilgan tugmadan birontasini tanlang 👇")))
