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


async def get_next_question(message: Message, state: FSMContext, previous_questions, respondent, question_id):
    all_questions = await sync_to_async(lambda: respondent.poll.questions.all())()
    answered_ids = await sync_to_async(list)(
        Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    )
    next_question = await all_questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await message.answer(str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        await state.clear()
        return

    updated_history = previous_questions + [question_id]
    respondent.history = updated_history
    await respondent.asave()

    await state.update_data(
        question_id=next_question.id,
        previous_questions=updated_history,
        selected_id=None
    )

    await render_question(message, state, next_question, updated_history)
    await state.set_state(PollStates.waiting_for_answer)


async def render_question(message: Message, state: FSMContext, question: Question, previous_questions: list):
    show_back_button = question.order != 1
    if not show_back_button:
        await message.answer(str(question.poll.description))

    await state.update_data(question_id=question.id, previous_questions=previous_questions)

    choices = await sync_to_async(list)(question.choices.all().order_by("order"))
    choice_map = {str(idx): choice.id for idx, choice in enumerate(choices, start=1)}
    await state.update_data(choice_map=choice_map)
    state_data = await state.get_data()

    if question.type in [
        Question.QuestionTypeChoices.CLOSED_SINGLE,
        Question.QuestionTypeChoices.MIXED
    ]:
        selected_id = state_data.get("selected_id")
        if selected_id:
            msg_text = render_selected_single_answer_text(question, choices, selected_id)
            # 🧾 Отметка выбора — редактируем старое сообщение
            try:
                await message.edit_text(msg_text)
            except:
                pass  # если не редактируется — пропускаем
            # 📩 Новый вопрос — отправляем как новое сообщение
            msg_text = render_question_inline_text(question, choices)
            markup = get_inline_keyboards_markup(question, choices, show_back_button)
            await message.answer(msg_text, reply_markup=markup)
            return
        else:
            msg_text = render_question_inline_text(question, choices)
            markup = get_inline_keyboards_markup(question, choices, show_back_button)
            await message.answer(msg_text, reply_markup=markup)
    elif question.type == Question.QuestionTypeChoices.CLOSED_MULTIPLE:
        selected_choices = []
        await state.update_data(selected_choices=selected_choices)
        msg_text = await render_multiselect_inline_text(question.text, choice_map, selected_choices)
        markup = get_inline_multiselect_keyboard(choice_map, selected_choices, show_back_button)
        await message.answer(msg_text, reply_markup=markup)
    else:
        await message.answer(
            str(question.text) + "\n\n" +
            str(_("Жавобингизни ёзинг ✍️")
                ),
            reply_markup=ReplyKeyboardRemove())


async def show_multiselect_question(message: Message, choice_map, selected_choices, question_text="Номалум савол",
                                    show_back_button=True):
    msg_text = await render_multiselect_inline_text(question_text, choice_map, selected_choices)
    markup = get_inline_multiselect_keyboard(choice_map, selected_choices, show_back_button)
    await message.edit_text(msg_text, reply_markup=markup)


async def get_current_question(message: Message, state: FSMContext, user):
    print(f"🚦 get_current_question() called for user {user.id}")

    active_polls = Poll.objects.filter(deadline__gte=timezone.now())
    if not await active_polls.aexists():
        print("❌ No active polls")
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
        print("🔒 No available polls for user")
        await message.answer(
            str(_("Ҳозирча сиз учун янги сўровномалар мавжуд эмас.")),
            reply_markup=ReplyKeyboardRemove()
        )
        return

    respondent = await Respondent.objects.filter(
        tg_user=user, poll__in=active_polls, finished_at__isnull=True
    ).afirst()

    if not respondent:
        poll = await available_polls.afirst()
        respondent = await Respondent.objects.acreate(tg_user=user, poll=poll)
        print(f"🆕 New respondent created: {respondent.id}")
    else:
        print(f"👤 Existing respondent: {respondent.id}")

    poll = await sync_to_async(lambda: respondent.poll)()
    questions = await sync_to_async(lambda: poll.questions.all())()
    answered_ids = Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    next_question = await questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        print("📭 No next question — poll complete")
        respondent.finished_at = timezone.now()
        await respondent.asave()
        print(message, "FIVE")
        await message.answer(str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        return

    print(f"➡️ Starting at question_id={next_question.id}")
    await state.update_data(respondent_id=respondent.id)
    await get_next_question(
        message=message,
        state=state,
        previous_questions=[],
        respondent=respondent,
        question_id=next_question.id
    )
    await state.set_state(PollStates.waiting_for_answer)

def render_selected_single_answer_text(question, choices, selected_id):
    msg_text = f"{str(_('Савол:'))} {question.text}\n\n"
    for choice in choices:
        marker = "✅ " if choice.id == selected_id else ""
        msg_text += f"{marker}{choice.order}. {choice.text}\n"
    return msg_text
