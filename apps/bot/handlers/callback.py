from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache

from apps.bot.keyboards.inline import product_inline_kb
from apps.users.models import TGUser

callback_router = Router()


@callback_router.callback_query(F.data.startswith("increase_"))
async def increase_product_count(callback: types.CallbackQuery):
    _increase, count, product_id = callback.data.split('_')
    count = int(count) + 1
    await callback.message.edit_reply_markup(
        reply_markup=product_inline_kb(product_id, count)
    )
    await callback.answer(str(_("{count} ta")).format(count=count))


@callback_router.callback_query(F.data.startswith("decrease_"))
async def decrease_product_count(callback: types.CallbackQuery):
    _decrease, count, product_id = callback.data.split('_')
    if count != "1":
        count = int(count) - 1
        await callback.message.edit_reply_markup(
            reply_markup=product_inline_kb(product_id, count)
        )
    await callback.answer(str(_("{count} ta")).format(count=count))


@callback_router.callback_query(F.data.startswith("count_"))
async def info_product_count(callback: types.CallbackQuery):
    _count, count = callback.data.split("_")
    await callback.answer(str(_("{count} ta")).format(count=count))


async def add_to_cart(callback_query: types.CallbackQuery, state: FSMContext, user: TGUser | None):
    # Add to cart logic here
    _cart, count, product_id = callback_query.data.split('_')
    await callback_query.answer(_("Savatga qo'shildi"))
    await callback_query.message.edit_caption(_("Qo'shildi: {count} ta").format(count=count))
    data = await state.get_data()

    key = f"shopping_cart:{callback_query.from_user.id}"
    category = data.get("category")
    try:
        item_key = f"{data['product']}:{count}"
        # Сохраняем данные в кэш Django
        cache.set(f"{key}:{item_key}", data['price'], timeout=60*60*24)  # timeout — время хранения в кэше, например, 1 день
    except Exception as _e:
        await callback_query.message.answer(_("Server bilan ulanishda muammo bo'ldi. Boshidan uruning"))

    # Если категория присутствует, показываем продукты в этой категории
    if category:
        products, _status = await get_products(category=category, user_lang=user_lang)
        await callback_query.message.answer(_("Muzqaymoqni tanlang"),
                                            reply_markup=generate_category_keyboard(products, user_lang))
        await BuyState.get_product.set()
    else:
        categories, _status = await get_categories()
        await callback_query.message.answer(_("Muzqaymoq turini tanlang."),
                                            reply_markup=generate_category_keyboard(categories, user_lang))
        await BuyState.get_category.set()
