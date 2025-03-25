import os

from django.conf import settings
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile
from django.utils.translation import gettext_lazy as _

from apps.bot.handlers.cart import view_cart
from apps.bot.keyboards.inline import product_inline_kb
from apps.bot.keyboards.markups import make_row_keyboard, BACK_BUTTON, CART_BUTTON
from apps.bot.states import MenuStates
from apps.bot.utils import send_category_list_message
from apps.products.models import Product, Category
from apps.bot.handlers.echo import echo_handler
from apps.users.models import TGUser

menu_router = Router()


@menu_router.message(MenuStates.choose_menu)
async def menu_choose_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    menu_name = message.text
    if menu_name == BACK_BUTTON:
        await echo_handler(message, state, user)
        return
    lang = user.lang if user.lang else "uz"
    lang_str = f'name_{lang}'
    exists = await Category.objects.filter(**{lang_str: menu_name}).aexists()
    if exists:
        await state.update_data(category=message.text)
        products = []
        category__filter = "category__" + lang_str
        async for product in Product.objects.filter(
            **{category__filter: menu_name}
        ).values('name_ru', 'name_uz'):
            name_uz_data = product['name_uz']
            products.append(product.pop(lang_str, name_uz_data))
        await message.answer(str(_("Maxsulotni tanlang")),
                             reply_markup=make_row_keyboard(products, add_back=True))
        await state.set_state(MenuStates.choose_product)
    else:
        await echo_handler(message, state, user)


@menu_router.message(MenuStates.choose_product)
async def product_choose_handler(message: Message, state: FSMContext, user: TGUser | None) -> None:
    menu_name = message.text
    if menu_name == BACK_BUTTON:
        await echo_handler(message, state, user)
        return
    elif menu_name == CART_BUTTON:
        await view_cart(message, state, user)
        return
    lang = user.lang if user.lang else "uz"
    lang_str = f'name_{lang}'

    # Найти продукт
    product = await Product.objects.filter(**{lang_str: menu_name}).afirst()
    if product:
        # Подготовка подписи
        caption = f"{menu_name}\n{str(_('Narxi'))}: {product.price}"
        # Определяем путь к изображению
        if product.photo and product.photo.name:
            file_path = settings.MEDIA_ROOT + "/" + product.photo.name
            if os.path.exists(file_path):
                with open(file_path, "rb") as photo:
                    await message.answer_photo(
                        photo=FSInputFile(file_path),
                        caption=caption,
                        reply_markup=product_inline_kb(product.pk)
                    )
            else:
                await message.answer(str(_("Rasm bizni serverda topilmadi.")))
                return
        elif product.photo_uri:  # Альтернативный путь (можно дополнить обработку скачивания)
            await message.answer(str(_("Xozircha faqat lokal tarmoqdagi rasmlarni yuborish ishlaydi.")))
            return
        else:
            await message.answer(str(_("Foto mavjud emas.")))
            return

    else:
        await send_category_list_message(message, state, user)
