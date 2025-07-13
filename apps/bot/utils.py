from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.db.models import OuterRef, Exists
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bot.inline_keyboards import (
    get_inline_keyboards_markup,
    get_inline_multiselect_keyboard,
    render_question_inline_text,
    render_multiselect_inline_text
)
from apps.bot.states import PollStates
from apps.polls.models import Poll, Respondent, Answer, Question
from apps.users.models import TGUser

ANOTHER_STR = str(_("📝 Бошқа"))
BACK_STR = str(_("🔙 Ортга"))
NEXT_STR = str(_("➡️ Кейинги савол"))


async def send_poll_question(bot: Bot, chat_id: int, state: FSMContext, respondent: Respondent, question: Question):
    choices = await sync_to_async(list)(question.choices.all().order_by("order"))
    allows_multiple_answers = question.type == Question.QuestionTypeChoices.CLOSED_MULTIPLE

    # 💬 Открытый или смешанный вопрос — отправим текст
    if question.type == Question.QuestionTypeChoices.OPEN:
        await bot.send_message(
            chat_id,
            f"📨 {question.text}\n\nИлтимос, жавобингизни матн сифатида юборинг ✍️"
        )

        # Создаём пустой Answer для отслеживания
        answer, _ = await Answer.objects.aget_or_create(
            respondent=respondent,
            question=question
        )

        # Обновляем состояние FSM, чтобы ждать текстовый ответ
        await state.update_data(
            question_id=question.id,
            respondent_id=respondent.id,
            answer_id=answer.id
        )
        await state.set_state(PollStates.waiting_for_answer)
        return

    # 📊 Закрытый вопрос — отправим Telegram poll
    options = [choice.text for choice in choices]
    if question.type == Question.QuestionTypeChoices.MIXED:
        options.append("📝 Бошқа")
    poll_message = await bot.send_poll(
        chat_id=chat_id,
        question=question.text,
        options=options,
        is_anonymous=False,
        allows_multiple_answers=allows_multiple_answers
    )

    # Создаём или обновляем Answer с telegram_poll_id
    answer, created = await Answer.objects.aupdate_or_create(
        respondent=respondent,
        question=question,
        defaults={"telegram_poll_id": poll_message.poll.id,
                  "telegram_msg_id": poll_message.message_id,
                  "telegram_chat_id": poll_message.chat.id
                  }
    )


async def async_get_or_create_user(defaults=None, **kwargs):
    """
    Async equivalent of Django's get_or_create.
    """
    defaults = defaults or {}
    try:
        # Try to get the object
        obj = await TGUser.objects.aget(**kwargs)
        created = False
    except TGUser.DoesNotExist:
        # Object does not exist, attempt to create it
        try:
            obj = await TGUser.objects.acreate(**{**kwargs, **defaults})
            created = True
        except IntegrityError:
            # Handle a race condition where the object was created between `aget` and `acreate`
            obj = await TGUser.objects.aget(**kwargs)
            created = False
    return obj, created


async def get_next_question(bot, chat_id, state: FSMContext, respondent, previous_questions, question_id):
    all_questions = await sync_to_async(lambda: respondent.poll.questions.all())()
    answered_ids = await sync_to_async(list)(
        Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    )
    next_question = await all_questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await bot.send_message(chat_id, str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        await state.clear()
        return

    updated_history = previous_questions + [question_id]
    respondent.history = updated_history
    await respondent.asave()

    await state.update_data(
        question_id=next_question.id,
        previous_questions=updated_history
    )
    await send_poll_question(bot, chat_id, state, respondent, next_question)
    await state.set_state(PollStates.waiting_for_answer)


async def render_question(message: Message, state: FSMContext, question: Question, previous_questions: list):
    show_back_button = question.order != 1
    if not show_back_button:
        await message.answer(str(question.poll.description))

    await state.update_data(question_id=question.id, previous_questions=previous_questions)

    choices = await sync_to_async(list)(question.choices.all().order_by("order"))
    choice_map = {str(idx): choice.id for idx, choice in enumerate(choices, start=1)}
    await state.update_data(choice_map=choice_map)

    if question.type in [
        Question.QuestionTypeChoices.CLOSED_SINGLE,
        Question.QuestionTypeChoices.MIXED
    ]:
        msg_text = render_question_inline_text(question, choices)
        markup = get_inline_keyboards_markup(question, choices, show_back_button)
        await message.answer(msg_text, reply_markup=markup)
    elif question.type == Question.QuestionTypeChoices.CLOSED_MULTIPLE:
        selected_choices = []
        await state.update_data(selected_choices=selected_choices)
        msg_text = render_multiselect_inline_text(question.text, choice_map, selected_choices)
        markup = get_inline_multiselect_keyboard(choice_map, selected_choices, show_back_button)
        await message.answer(msg_text, reply_markup=markup)
    else:
        await message.answer(
            str(question.text) + "\n\n" +
            str(_("Жавобингизни ёзинг ✍️")
                ), reply_markup=ReplyKeyboardRemove())


async def show_multiselect_question(message, choice_map, selected_choices, question_text="Номалум савол",
                                    show_back_button=True):
    msg_text = render_multiselect_inline_text(question_text, choice_map, selected_choices)
    markup = get_inline_multiselect_keyboard(choice_map, selected_choices, show_back_button)
    await message.answer(msg_text, reply_markup=markup)


async def get_current_question(message, state: FSMContext, user):
    active_polls = Poll.objects.filter(deadline__gte=timezone.now())
    if not await active_polls.aexists():
        await message.answer(str(_("Ҳозирча актив сўровномалар мавжуд эмас.")))
        return

    completed_respondents = Respondent.objects.filter(
        tg_user=user,
        poll=OuterRef('pk'),
        finished_at__isnull=False
    )
    available_polls = active_polls.annotate(
        has_completed=Exists(completed_respondents)
    ).filter(has_completed=False)

    if not await available_polls.aexists():
        await message.answer(str(_("Ҳозирча сиз учун янги сўровномалар мавжуд эмас.")))
        return

    respondent = await Respondent.objects.filter(
        tg_user=user, poll__in=active_polls, finished_at__isnull=True
    ).afirst()

    if not respondent:
        poll = await available_polls.afirst()
        respondent = await Respondent.objects.acreate(tg_user=user, poll=poll)

    # ✅ Попытка найти неотвеченный Answer
    unfinished_answer = await Answer.objects.select_related("question").filter(
        respondent=respondent,
        is_answered=False
    ).order_by("id").afirst()

    if unfinished_answer:
        print("🔁 Повторно отправляем неотвеченный вопрос")
        await state.update_data(respondent_id=respondent.id)
        await send_poll_question(
            message.bot, message.from_user.id, state, respondent, unfinished_answer.question
        )
        return

    # 🧭 Продолжение как раньше: ищем след. неотвеченный вопрос
    poll = await sync_to_async(lambda: respondent.poll)()
    questions = await sync_to_async(lambda: poll.questions.all())()
    answered_ids = await sync_to_async(list)(
        Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    )
    next_question = await questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await message.answer(str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        return

    await state.update_data(respondent_id=respondent.id)
    await get_next_question(message.bot, message.from_user.id, state, respondent, [], next_question.id)
    await state.set_state(PollStates.waiting_for_answer)
