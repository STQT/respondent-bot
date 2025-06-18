from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class GenderChoices(TextChoices):
    MALE = "M", _("Эркак")
    FEMALE = "F", _("Аёл")


class AgeChoices(TextChoices):
    AGE_18_25 = "18-25", _("18–25")
    AGE_26_35 = "26-35", _("26–35")
    AGE_36_45 = "36-45", _("36–45")
    AGE_46_60 = "46-60", _("46–60")
    AGE_60_PLUS = "60+", _("60 ёшдан катта")


class GraduateChoices(TextChoices):
    HIGHER = "higher", _("Олий")
    SPECIAL_SECONDARY = "special_secondary", _("Ўрта махсус")
    SECONDARY = "secondary", _("Ўрта")
    OTHER = "other", _("Бошқа")


class SettlementTypeChoices(TextChoices):
    CITY = "city", _("Шаҳар")
    VILLAGE = "village", _("Қишлоқ")


def get_gender_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=str(GenderChoices.MALE.label))
            ],
            [
                KeyboardButton(text=str(GenderChoices.FEMALE.label))
            ]
        ],
        resize_keyboard=True
    )


def get_age_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=str(age.label))] for age in AgeChoices],
        resize_keyboard=True
    )


def get_education_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=str(choice.label))] for choice in GraduateChoices],
        resize_keyboard=True
    )


def get_location_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=str(SettlementTypeChoices.CITY.label))],
                  [KeyboardButton(text=str(SettlementTypeChoices.VILLAGE.label))]],
        resize_keyboard=True
    )
