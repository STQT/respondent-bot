from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from apps.bot.keyboards.inline import product_inline_kb
from apps.bot.keyboards.markups import get_payment_type_keyboard
from apps.bot.states import OrderStates
from apps.bot.utils import send_category_list_message
from apps.products.models import Product
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


@callback_router.callback_query(F.data.startswith("addtocart_"))
async def add_to_cart(callback_query: types.CallbackQuery, state: FSMContext, user: TGUser | None):
    # Add to cart logic here
    _addtocart, count, product_id = callback_query.data.split('_')
    await callback_query.answer(str(_("Savatga qo'shildi")))
    await callback_query.message.edit_caption(str(_("Qo'shildi: {count} ta").format(count=count)))
    key = f"shopping_cart:{callback_query.from_user.id}"
    # try:
    item_key = f"{product_id}:{count}"
    product = await Product.objects.aget(pk=product_id)
    # Сохраняем данные в кэш Django
    cache.set(f"{key}:{item_key}", product.price * count,
              timeout=60 * 60 * 24)  # timeout — время хранения в кэше, например, 1 ден
    await send_category_list_message(callback_query.message, state, user)


@callback_router.callback_query(F.data.startswith("clearcart"))
async def clear_cart(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    key = f"shopping_cart:{user_id}"
    cart_items = cache.keys(f"{key}:*")

    for item in cart_items:
        cache.delete(item)

    await callback_query.answer(str(_("Savat tozalandi")), show_alert=True)
    await callback_query.message.delete()


@callback_router.callback_query(F.data.startswith("checkout"))
async def checkout(callback_query: types.CallbackQuery, state: FSMContext, user: TGUser | None):
    user_id = callback_query.from_user.id
    key = f"shopping_cart:{user_id}"
    cart_items = cache.keys(f"{key}:*")

    if not cart_items:
        await callback_query.answer(str(_("Savat bo'sh")), show_alert=True)
        return

    # Сохраняем детали заказа в состоянии
    order_items = []
    total_sum = 0

    for item in cart_items:
        product_id, count = item.split(":")[-2:]
        count = int(count)
        product = await Product.objects.aget(pk=product_id)
        total_price = product.price * count
        total_sum += total_price
        order_items.append({"product": product, "count": count, "price": total_price})
        cache.delete(item)

    # await state.update_data(order_items=order_items, total_sum=total_sum)

    await state.update_data(
        order_items=[
            {
                "product_id": item["product"].id,
                "product_name": getattr(item["product"], "name_" + user.lang),
                "price": item["price"],
                "count": item["count"]
            } for item in order_items
        ],
        total_sum=total_sum
    )
    # Запрашиваем способ оплаты
    await callback_query.message.answer(
        str(_("To'lov turini tanlang 👇")),
        reply_markup=get_payment_type_keyboard()
    )
    await callback_query.message.delete()
    await state.set_state(OrderStates.payment_type)


@callback_router.callback_query(F.data.startswith("close"))
async def clear_cart(callback_query: types.CallbackQuery, state, user):
    await callback_query.message.delete()
    await send_category_list_message(callback_query.message, state, user)
