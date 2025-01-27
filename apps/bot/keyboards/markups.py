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
    Создаёт реплай-клавиатуру с кнопками в две колонки
    :param items: список текстов для кнопок
    :param add_back: добавить кнопку "Ortga" вместо "Savat"
    :return: объект реплай-клавиатуры
    """
    # Разбиваем кнопки на строки по 2 кнопки в строке
    keyboard = [
        [KeyboardButton(text=items[i]), KeyboardButton(text=items[i + 1])]
        for i in range(0, len(items) - 1, 2)
    ]

    # Добавляем последнюю кнопку, если количество кнопок нечётное
    if len(items) % 2 != 0:
        keyboard.append([KeyboardButton(text=items[-1])])

    # Добавляем нижний ряд с кнопкой "Ortga" или "Savat"
    bottom_row = [KeyboardButton(text=str(_("Ortga")) if add_back else str(_("Savat")))]
    keyboard.append(bottom_row)

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
