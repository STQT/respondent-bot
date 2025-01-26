from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from apps.bot.keyboards.inline import cart_actions_kb
from apps.products.models import Product
from apps.users.models import TGUser


async def view_cart(message: Message, state: FSMContext, user: TGUser | None):
    user_id = message.from_user.id
    key = f"shopping_cart:{user_id}"
    cart_items = cache.keys(f"{key}:*")

    if not cart_items:
        await message.answer(str(_("Savat bo'sh")), show_alert=True)
        return

    cart_summary = str(_("Savatchadagi mahsulotlar:\n\n"))
    total_sum = 0

    for item in cart_items:
        product_id, count = item.split(":")[-2:]
        count = int(count)
        product = await Product.objects.aget(pk=product_id)
        total_price = product.price * count
        total_sum += total_price
        product_name = getattr(product, 'name_' + user.lang)
        cart_summary += f"{product_name}: {count} x {product.price} = {total_price}\n"

    cart_summary += str(_("\nUmumiy summa: {total_sum}")).format(total_sum=total_sum)
    await message.answer(
        cart_summary,
        reply_markup=cart_actions_kb()
    )
