from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.bot.utils import get_current_question
from apps.polls.models import Poll, Respondent, Answer, Question, Choice
from apps.users.models import TGUser

poll_router = Router()


@poll_router.message(Command("poll"))
async def start_poll_handler(message: Message, state: FSMContext, user: TGUser):
    await get_current_question(message, state, user)


@poll_router.message(PollStates.waiting_for_answer)
async def process_answer(message: Message, state: FSMContext, user: TGUser):
    data = await state.get_data()
    respondent_id = data["respondent_id"]
    question_id = data["question_id"]
    answer_text = message.text.strip()

    respondent = await Respondent.objects.aget(id=respondent_id)
    question = await Question.objects.aget(id=question_id)

    # Создаём ответ объект
    answer = await Answer.objects.acreate(
        respondent=respondent,
        question=question,
    )

    if question.type == Question.QuestionTypeChoices.OPEN:
        # Открытый вопрос: сохраняем текст
        answer.open_answer = answer_text
        await answer.asave()

    elif question.type == Question.QuestionTypeChoices.CLOSED_SINGLE:
        # Один вариант из списка
        try:
            choice = await Choice.objects.aget(question=question, text=answer_text)
            await sync_to_async(answer.selected_choices.add)(choice)
        except Choice.DoesNotExist:
            await message.answer(str(_("Бундай вариант йўқ. Илтимос, тўғри жавобни танланг.")))
            return


    elif question.type == Question.QuestionTypeChoices.CLOSED_MULTIPLE:

        input_choices = [s.strip() for s in answer_text.split(",")]

        valid_choices_qs = Choice.objects.filter(question=question).values_list("text", flat=True)

        valid_choices = await sync_to_async(list)(valid_choices_qs)

        selected = []

        for val in input_choices:

            if val in valid_choices:

                choice = await Choice.objects.aget(question=question, text=val)

                selected.append(choice)

            else:

                await message.answer(str(_(f'"{val}" — нотўғри жавоб. Илтимос, берилган вариантлардан танланг.')))

                return

        await sync_to_async(answer.selected_choices.add)(*selected)

    else:
        await message.answer(str(_("Бу турдаги савол ҳозирча қўллаб-қувватланмайди.")))
        return

    # Ищем следующий вопрос
    all_questions = await sync_to_async(lambda: respondent.poll.questions.all())()
    answered_ids = Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    next_question = await all_questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await message.answer(str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        await state.clear()
        return

    # Показываем следующий вопрос
    await state.update_data(question_id=next_question.id)
    await message.answer(str(_("Савол: ")) + next_question.text)

    if next_question.type in [Question.QuestionTypeChoices.CLOSED_SINGLE, Question.QuestionTypeChoices.CLOSED_MULTIPLE]:
        buttons = []
        async for choice in next_question.choices.all():
            buttons.append(types.KeyboardButton(text=choice.text))
        markup = types.ReplyKeyboardMarkup(keyboard=[[btn] for btn in buttons], resize_keyboard=True)
        await message.answer(str(_("Жавобни танланг 👇")), reply_markup=markup)
    else:
        await message.answer(str(_("Жавобингизни ёзинг ✍️")), reply_markup=types.ReplyKeyboardRemove())

    await state.set_state(PollStates.waiting_for_answer)
