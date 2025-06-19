from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.bot.utils import get_current_question, BACK_STR, ANOTHER_STR, get_keyboards_markup
from apps.polls.models import Respondent, Answer, Question, Choice
from apps.users.models import TGUser

poll_router = Router()


async def get_next_question(message: Message, state, previous_questions, respondent, question, question_id):
    # Переход к следующему вопросу
    all_questions = await sync_to_async(lambda: respondent.poll.questions.all())()
    answered_ids = Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    next_question = await all_questions.exclude(id__in=answered_ids).afirst()
    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await message.answer(str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        await state.clear()
        return

    updated_history = previous_questions + [question_id]
    await state.update_data(question_id=next_question.id, previous_questions=updated_history)

    msg_text = str(_("Савол: ")) + next_question.text + "\n\n"

    # Добавим варианты ответа
    choices = await sync_to_async(list)(next_question.choices.all().order_by("order"))
    print(choices)
    choice_map = {}
    for idx, choice in enumerate(choices, start=1):
        msg_text += f"{idx}. {choice.text}\n"
        choice_map[str(idx)] = choice.id

    # Сохраняем словарь номера → id варианта
    await state.update_data(choice_map=choice_map)

    # Клавиатура
    if next_question.type in [Question.QuestionTypeChoices.CLOSED_SINGLE, Question.QuestionTypeChoices.CLOSED_MULTIPLE,
                              Question.QuestionTypeChoices.MIXED]:
        markup = get_keyboards_markup(next_question, choices)
        msg_text += "\n" + str(_("Жавобни танланг (номер билан) 👇"))
        await message.answer(msg_text, reply_markup=markup)
    else:
        await message.answer(msg_text + "\n" + str(_("Жавобингизни ёзинг ✍️")),
                             reply_markup=types.ReplyKeyboardRemove())


@poll_router.message(Command("poll"))
async def start_poll_handler(message: Message, state: FSMContext, user: TGUser):
    await get_current_question(message, state, user)


@poll_router.message(PollStates.waiting_for_answer)
async def process_answer(message: Message, state: FSMContext, user: TGUser):
    data = await state.get_data()
    respondent_id = data["respondent_id"]
    question_id = data["question_id"]
    previous_questions = data.get("previous_questions", [])
    choice_map = data.get("choice_map", {})

    answer_text = message.text.strip()

    # 🔙 Обработка "Назад"
    if answer_text == BACK_STR and previous_questions:
        previous_question_id = previous_questions.pop()
        await state.update_data(question_id=previous_question_id, previous_questions=previous_questions)
        question = await Question.objects.aget(id=previous_question_id)

        await message.answer(str(_("Савол: ")) + question.text)
        if question.type in [Question.QuestionTypeChoices.CLOSED_SINGLE, Question.QuestionTypeChoices.CLOSED_MULTIPLE,
                             Question.QuestionTypeChoices.MIXED]:
            buttons = []
            async for choice in question.choices.all():
                buttons.append(types.KeyboardButton(text=choice.text))
            if question.type == Question.QuestionTypeChoices.MIXED:
                buttons.append(types.KeyboardButton(text=ANOTHER_STR))
            buttons.append(types.KeyboardButton(text=BACK_STR))
            markup = types.ReplyKeyboardMarkup(keyboard=[[btn] for btn in buttons], resize_keyboard=True)
            await message.answer(str(_("Жавобни танланг 👇")), reply_markup=markup)
        else:
            await message.answer(str(_("Жавобингизни ёзинг ✍️")), reply_markup=types.ReplyKeyboardRemove())
        return

    respondent = await Respondent.objects.aget(id=respondent_id)
    question = await Question.objects.aget(id=question_id)

    # Удаляем старый ответ (если редактируем)
    await Answer.objects.filter(respondent=respondent, question=question).adelete()

    # Создаём новый ответ
    answer = await Answer.objects.acreate(respondent=respondent, question=question)

    if question.type == Question.QuestionTypeChoices.OPEN:
        answer.open_answer = answer_text
        await answer.asave()

    elif question.type in [Question.QuestionTypeChoices.CLOSED_SINGLE, Question.QuestionTypeChoices.MIXED]:
        if answer_text == ANOTHER_STR:
            await state.set_state(PollStates.waiting_for_custom_answer)
            await message.answer(str(_("Илтимос, ўз жавобингизни матн сифатида юборинг ✍️")),
                                 reply_markup=types.ReplyKeyboardRemove())
            return
        choice_id = choice_map.get(answer_text)
        if not choice_id:
            await message.answer(str(_("Бундай рақам йўқ. Илтимос, берилган рақамлардан танланг.")))
            return
        choice = await Choice.objects.aget(id=choice_id)
        await sync_to_async(answer.selected_choices.add)(choice)

    elif question.type == Question.QuestionTypeChoices.CLOSED_MULTIPLE:
        input_numbers = [s.strip() for s in answer_text.split(",")]
        selected = []
        for num in input_numbers:
            choice_id = choice_map.get(num)
            if choice_id:
                choice = await Choice.objects.aget(id=choice_id)
                selected.append(choice)
            else:
                await message.answer(str(_(f'"{num}" — нотўғри рақам. Илтимос, берилган рақамлардан танланг.')))
                return
        await sync_to_async(answer.selected_choices.add)(*selected)

    else:
        await message.answer(str(_("Бу турдаги савол ҳозирча қўллаб-қувватланмайди.")))
        return
    await get_next_question(message, state, previous_questions, respondent, question, question_id)
    await state.set_state(PollStates.waiting_for_answer)


@poll_router.message(PollStates.waiting_for_custom_answer)
async def process_custom_answer(message: Message, state: FSMContext, user: TGUser):
    data = await state.get_data()
    respondent_id = data["respondent_id"]
    question_id = data["question_id"]
    previous_questions = data.get("previous_questions", [])

    answer_text = message.text.strip()

    respondent = await Respondent.objects.aget(id=respondent_id)
    question = await Question.objects.aget(id=question_id)

    # Удаляем старый ответ (если редактируем)
    await Answer.objects.filter(respondent=respondent, question=question).adelete()

    # Создаём ответ и сохраняем текст как open_answer
    answer = await Answer.objects.acreate(respondent=respondent, question=question)
    answer.open_answer = answer_text
    await answer.asave()

    await get_next_question(message, state, previous_questions, respondent, question, question_id)

    await state.set_state(PollStates.waiting_for_answer)
