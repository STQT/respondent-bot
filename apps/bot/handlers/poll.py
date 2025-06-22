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


async def get_next_question(message: Message, state: FSMContext, previous_questions, respondent, question, question_id):
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

    # 🧠 Сохраняем историю в БД
    respondent.history = updated_history
    await respondent.asave()

    await state.update_data(question_id=next_question.id, previous_questions=updated_history)

    total_questions = await sync_to_async(lambda: respondent.poll.questions.count())()
    current_index = total_questions - await all_questions.exclude(id__in=answered_ids).acount() + 1

    progress_percent = int((current_index / total_questions) * 100)
    bar_length = 10
    filled_length = int(bar_length * progress_percent / 100)
    progress_bar = "▰" * filled_length + "▱" * (bar_length - filled_length)
    progress_text = f"📊 [{progress_bar}] {progress_percent}%\n\n"

    msg_text = progress_text + str(_("Савол: ")) + next_question.text + "\n\n"

    choices = await sync_to_async(list)(next_question.choices.all().order_by("order"))
    choice_map = {str(idx): choice.id for idx, choice in enumerate(choices, start=1)}

    for idx, choice in enumerate(choices, start=1):
        msg_text += f"{idx}. {choice.text}\n"

    await state.update_data(choice_map=choice_map)

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
    choice_map = data.get("choice_map", {})

    respondent = await Respondent.objects.aget(id=respondent_id)
    previous_questions = list(respondent.history or [])

    answer_text = message.text.strip()

    # 🔙 Обработка кнопки "Назад"
    if answer_text == BACK_STR and len(previous_questions) >= 2:
        previous_questions.pop()  # Удаляем текущий
        previous_question_id = previous_questions.pop()  # Берем предыдущий

        respondent.history = previous_questions
        await respondent.asave()

        await state.update_data(
            question_id=previous_question_id,
            previous_questions=previous_questions
        )

        await Answer.objects.filter(respondent=respondent, question_id=question_id).adelete()
        question = await Question.objects.aget(id=previous_question_id)

        await get_next_question(
            message=message,
            state=state,
            previous_questions=previous_questions,
            respondent=respondent,
            question=question,
            question_id=previous_question_id
        )
        await state.set_state(PollStates.waiting_for_answer)
        return

    question = await Question.objects.aget(id=question_id)
    await Answer.objects.filter(respondent=respondent, question=question).adelete()
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

    respondent = await Respondent.objects.aget(id=respondent_id)
    question = await Question.objects.aget(id=question_id)
    previous_questions = respondent.history or []

    await Answer.objects.filter(respondent=respondent, question=question).adelete()
    answer = await Answer.objects.acreate(respondent=respondent, question=question)
    answer.open_answer = message.text.strip()
    await answer.asave()

    await get_next_question(message, state, previous_questions, respondent, question, question_id)
    await state.set_state(PollStates.waiting_for_answer)
