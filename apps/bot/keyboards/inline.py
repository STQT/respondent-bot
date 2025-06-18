from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.polls.models import Question


async def build_choices_keyboard(question: Question) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)

    async for choice in question.choices.all():
        callback_data = f"choice:{question.id}:{choice.id}"
        keyboard.add(InlineKeyboardButton(text=choice.text, callback_data=callback_data))

    # Для смешанного типа добавляем кнопку "Свой ответ"
    if question.type == 'mixed':
        callback_data = f"custom_answer:{question.id}"
        keyboard.add(InlineKeyboardButton(text="Бошқа: _______________", callback_data=callback_data))

    return keyboard
