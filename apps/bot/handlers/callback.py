from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from apps.users.models import TGUser

callback_router = Router()

#
# @callback_router.callback_query(F.data.startswith("increase_"))
# async def increase_product_count(callback: types.CallbackQuery):
#     _increase, count, product_id = callback.data.split('_')
#     count = int(count) + 1
#     await callback.message.edit_reply_markup(
#         reply_markup=product_inline_kb(product_id, count)
#     )
#     await callback.answer(str(_("{count} ta")).format(count=count))
#
#
# @callback_router.callback_query(F.data.startswith("decrease_"))
# async def decrease_product_count(callback: types.CallbackQuery):
#     _decrease, count, product_id = callback.data.split('_')
#     if count != "1":
#         count = int(count) - 1
#         await callback.message.edit_reply_markup(
#             reply_markup=product_inline_kb(product_id, count)
#         )
#     await callback.answer(str(_("{count} ta")).format(count=count))


@callback_router.callback_query(F.data.startswith("count_"))
async def info_product_count(callback: types.CallbackQuery):
    _count, count = callback.data.split("_")
    await callback.answer(str(_("{count} ta")).format(count=count))
