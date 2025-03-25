from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override


TG_LANGUAGES = ["🇺🇿 O'zbek", "🇷🇺 Русский"]
CASH_TYPE = [str(_("💴 Naqd")), str(_("💲 Click"))]
BACK_BUTTON = str(_("⬅️ Ortga"))
CHANGE_LANG_BUTTON = str(_("🌎 Tilni sozlash"))
CART_BUTTON = str(_("🛒 Savat"))


def get_language_keyboards(back_button: bool = False):
    language_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=language) for language in TG_LANGUAGES],
        ],
        resize_keyboard=True,
    )
    if back_button:
        language_keyboard.keyboard.append([KeyboardButton(text=BACK_BUTTON)])
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
            [KeyboardButton(text=CASH_TYPE[0])], # Naqd
            [KeyboardButton(text=CASH_TYPE[1])], # Click
            [KeyboardButton(text=str(_("Yetkazib berish")))],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_language_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TG_LANGUAGES[0])], # Uzbek
            [KeyboardButton(text=TG_LANGUAGES[1])],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard



def make_row_keyboard(items: list[str], add_back: bool = False, lang="uz") -> ReplyKeyboardMarkup:
    """
    Создаёт реплай-клавиатуру с кнопками в две колонки
    :param items: список текстов для кнопок
    :param add_back: добавить кнопку "Ortga" вместо "Savat"
    :return: объект реплай-клавиатуры
    """
    # Разбиваем кнопки на строки по 2 кнопки в строке
    with override(lang):
        keyboard = [
            [KeyboardButton(text=items[i]), KeyboardButton(text=items[i + 1])]
            for i in range(0, len(items) - 1, 2)
        ]

        # Добавляем последнюю кнопку, если количество кнопок нечётное
        if len(items) % 2 != 0:
            keyboard.append([KeyboardButton(text=items[-1])])

        # Добавляем нижний ряд с кнопкой "Ortga" или "Savat"
        if add_back:
            bottom_row = [KeyboardButton(text=BACK_BUTTON)]
        else:
            bottom_row = [KeyboardButton(text=CART_BUTTON), KeyboardButton(text=CHANGE_LANG_BUTTON)]
        keyboard.append(bottom_row)

        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
