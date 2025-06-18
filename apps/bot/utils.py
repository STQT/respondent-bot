from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.polls.models import Poll, Respondent, Answer, Question
from apps.users.models import TGUser


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


async def get_current_question(message: Message, state: FSMContext, user: TGUser):
    # Проверяем, есть ли активные опросы
    active_polls = Poll.objects.filter(deadline__gte=timezone.now())
    if not await active_polls.aexists():
        await message.answer(str(_("Ҳозирча актив сўровномалар мавжуд эмас.")))
        return

    # Проверяем, есть ли незавершённый опрос
    respondent = await Respondent.objects.filter(tg_user=user, poll__in=active_polls, finished_at__isnull=True).afirst()
    if not respondent:
        # Если нет, создаём нового
        poll = await active_polls.afirst()  # Пока берём первый активный
        respondent = await Respondent.objects.acreate(tg_user=user, poll=poll)

    # Получаем все вопросы
    poll = await sync_to_async(lambda: respondent.poll)()
    questions = await sync_to_async(lambda: poll.questions.all())()

    # Получаем список вопросов, на которые уже есть ответы
    answered_question_ids = Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)

    # Определяем следующий вопрос
    next_question = await questions.exclude(id__in=answered_question_ids).afirst()

    if not next_question:
        # Опрос завершён
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await message.answer(str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        return

    # Сохраняем состояние и ID вопроса
    await state.update_data(respondent_id=respondent.id, question_id=next_question.id)

    await message.answer(str(_("Савол: ")) + next_question.text)

    # Можно также вывести варианты ответов для закрытых типов
    if next_question.type in [Question.QuestionTypeChoices.CLOSED_SINGLE, Question.QuestionTypeChoices.CLOSED_MULTIPLE]:
        buttons = []
        async for choice in next_question.choices.all():
            buttons.append(types.KeyboardButton(text=choice.text))

        markup = types.ReplyKeyboardMarkup(
            keyboard=[[button] for button in buttons],
            resize_keyboard=True
        )
        await message.answer(str(_("Жавобни танланг 👇")), reply_markup=markup)
    await state.set_state(PollStates.waiting_for_answer)
