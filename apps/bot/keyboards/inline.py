from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from django.utils.translation import gettext_lazy as _


def product_inline_kb(product_id, product_count=1):
    inline_kb = InlineKeyboardBuilder()
    inline_kb.row(
        InlineKeyboardButton(text='-',
                             callback_data=f'decrease_{str(product_count)}_{str(product_id)}'),
        InlineKeyboardButton(text=f'{product_count}', callback_data=f'count_{product_count}'),
        InlineKeyboardButton(text='+',
                             callback_data=f'increase_{str(product_count)}_{str(product_id)}'),
    )
    inline_kb.row(
        InlineKeyboardButton(text=str(_("📥 Savatga qo'shish")),
                             callback_data=f'addtocart_{str(product_count)}_{str(product_id)}'),
    )
    return inline_kb.as_markup()


def shopping_cart_clean_kb():
    inline_kb = InlineKeyboardMarkup(row_width=2)
    inline_kb.add(
        InlineKeyboardButton(text=str(_("☑️ Ha")),
                             callback_data='yes'),
        InlineKeyboardButton(text=str(_("✖️ Yo'q")),
                             callback_data='no'),
    )
    return inline_kb


def approve_delivery_buy():
    inline_kb = InlineKeyboardMarkup(row_width=2)
    inline_kb.add(
        InlineKeyboardButton(text=str(_("☑️ Ha")),
                             callback_data='delivery_yes'),
        InlineKeyboardButton(text=str(_("✖️ Yo'q")),
                             callback_data='delivery_no'),
    )
    inline_kb.add(
        InlineKeyboardButton(text=str(_("⬅️ Ortga")),
                             callback_data='delivery_back')
    )
    return inline_kb


def cart_actions_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(_("🗑 Savatni tozalash")), callback_data="clearcart")],
        [InlineKeyboardButton(text=str(_("🚖 Buyurtma berish")), callback_data="checkout")],
        [InlineKeyboardButton(text=str(_("🛒 Mahsulot qo'shish")), callback_data="close")],
    ])
