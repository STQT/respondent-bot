from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from django.utils.translation import gettext_lazy as _

TG_LANGUAGES = ["🇺🇿 O'zbek", "🇷🇺 Русский"]
CASH_TYPE = [str(_("Naqd")), str(_("Click"))]


def get_language_keyboards():
    language_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=language) for language in TG_LANGUAGES],
        ],
        resize_keyboard=True,
    )
    return language_keyboard


def get_cash_type_keyboards():
    language_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=cash_type) for cash_type in CASH_TYPE],
        ],
        resize_keyboard=True,
    )
    return language_keyboard


def get_phone_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=str(_("📱 Telefon yuborish")), request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


def get_payment_type_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=str(_("Naqd")))],
            [KeyboardButton(text=str(_("ClickUZ")))],
            [KeyboardButton(text=str(_("Yetkazib berish")))],
            [KeyboardButton(text=str(_("Ortga")))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


def make_row_keyboard(items: list[str], add_back: bool = False) -> ReplyKeyboardMarkup:
    """
    Создаёт реплай-клавиатуру с кнопками в один ряд
    :param items: список текстов для кнопок
    :return: объект реплай-клавиатуры
    """
    row = [KeyboardButton(text=item) for item in items]
    bottom_row = []
    if add_back:
        bottom_row.append(KeyboardButton(text=str(_("Ortga"))))
    else:
        bottom_row.append(KeyboardButton(text=str(_("Savat"))))
    return ReplyKeyboardMarkup(keyboard=[row, bottom_row], resize_keyboard=True)
