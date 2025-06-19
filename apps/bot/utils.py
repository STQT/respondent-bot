from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import ReplyKeyboardRemove
from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.db.models import OuterRef, Exists
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.polls.models import Poll, Respondent, Answer, Question
from apps.users.models import TGUser

ANOTHER_STR = str(_("Бошқа____"))
BACK_STR = str(_("🔙 Назад"))


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

    completed_respondents = Respondent.objects.filter(
        tg_user=user,
        poll=OuterRef('pk'),
        finished_at__isnull=False
    )
    available_polls = active_polls.annotate(
        has_completed=Exists(completed_respondents)
    ).filter(has_completed=False)

    if not await available_polls.aexists():
        await message.answer(
            str(_("Ҳозирча сиз учун янги сўровномалар мавжуд эмас.")),
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Есть ли незавершённый опрос
    respondent = await Respondent.objects.filter(
        tg_user=user, poll__in=active_polls, finished_at__isnull=True
    ).afirst()

    if not respondent:
        poll = await active_polls.afirst()
        respondent = await Respondent.objects.acreate(tg_user=user, poll=poll)

    poll = await sync_to_async(lambda: respondent.poll)()
    questions = await sync_to_async(lambda: poll.questions.all())()

    answered_ids = Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    next_question = await questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await message.answer(str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        return

    # Обновляем состояние
    await state.update_data(respondent_id=respondent.id, question_id=next_question.id, previous_questions=[])

    msg_text = str(_("Савол: ")) + next_question.text + "\n\n"

    choices = await sync_to_async(list)(next_question.choices.all())
    choice_map = {}
    for idx, choice in enumerate(choices, start=1):
        msg_text += f"{idx}. {choice.text}\n"
        choice_map[str(idx)] = choice.id

    await state.update_data(choice_map=choice_map)

    if next_question.type in [Question.QuestionTypeChoices.CLOSED_SINGLE, Question.QuestionTypeChoices.CLOSED_MULTIPLE,
                              Question.QuestionTypeChoices.MIXED]:
        markup = get_keyboards_markup(next_question, choices)
        msg_text += "\n" + str(_("Жавобни танланг (номер билан) 👇"))
        await message.answer(msg_text, reply_markup=markup)
    else:
        await message.answer(msg_text + "\n" + str(_("Жавобингизни ёзинг ✍️")), reply_markup=ReplyKeyboardRemove())

    await state.set_state(PollStates.waiting_for_answer)


def get_keyboards_markup(next_question, choices):
    number_buttons = [types.KeyboardButton(text=str(i)) for i in range(1, len(choices) + 1)]
    keyboard = [number_buttons]  # 👉 все числовые кнопки — в одной строке

    bottom_buttons = []
    if next_question.type == Question.QuestionTypeChoices.MIXED:
        bottom_buttons.append(types.KeyboardButton(text=ANOTHER_STR))
    bottom_buttons.append(types.KeyboardButton(text=BACK_STR))
    keyboard.append(bottom_buttons)  # 👉 отдельной строкой снизу

    markup = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    return markup
