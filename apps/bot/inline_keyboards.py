from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from django.utils.translation import gettext_lazy as _

ANOTHER_STR = str(_("📝 Бошқа"))
BACK_STR = str(_("🔙 Ортга"))
NEXT_STR = str(_("➡️ Кейинги савол"))

def get_inline_keyboards_markup(next_question, choices, show_back_button=True):
    keyboard = []
    for i, choice in enumerate(choices, start=1):
        button = InlineKeyboardButton(
            text=str(choice.order),
            callback_data=f"choice:{choice.id}"
        )
        if (i - 1) % 6 == 0:
            keyboard.append([])
        keyboard[-1].append(button)

    bottom_buttons = []
    if next_question.type == next_question.QuestionTypeChoices.MIXED:
        bottom_buttons.append(InlineKeyboardButton(text=ANOTHER_STR, callback_data="custom_input"))
    if show_back_button:
        bottom_buttons.append(InlineKeyboardButton(text=BACK_STR, callback_data="back"))

    if bottom_buttons:
        keyboard.append(bottom_buttons)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_inline_multiselect_keyboard(choice_map, selected_choices, show_back_button=True):
    keyboard = []
    for num, cid in choice_map.items():
        marker = "✅ " if cid in selected_choices else ""
        button = InlineKeyboardButton(
            text=f"{marker}{num}",
            callback_data=f"toggle:{cid}"
        )
        if len(keyboard) == 0 or len(keyboard[-1]) >= 6:
            keyboard.append([])
        keyboard[-1].append(button)

    bottom_buttons = [InlineKeyboardButton(text=NEXT_STR, callback_data="next")]
    if show_back_button:
        bottom_buttons.append(InlineKeyboardButton(text=BACK_STR, callback_data="back"))
    keyboard.append(bottom_buttons)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def render_question_inline_text(question, choices):
    msg_text = f"{str(_('Савол: '))} {question.text}\n\n"
    for choice in choices:
        msg_text += f"{choice.order}. {choice.text}\n"
    msg_text += "\n" + str(_("Жавобни танланг 👇"))
    return msg_text

def render_multiselect_inline_text(question_text, choice_map, selected_choices):
    msg_text = f"{str(_('Савол: '))} {question_text}\n\n"
    msg_text += f"{str(_('Танланган жавоблар ✅ билан белгиланган:'))}\n\n"
    for num, cid in choice_map.items():
        marker = "✅" if cid in selected_choices else "▫️"
        msg_text += f"{marker} {num}\n"
    return msg_text
