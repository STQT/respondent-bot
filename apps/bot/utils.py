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
from apps.polls.models import Poll, Respondent, Answer, Question, Choice
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
    print(f"📥 get_next_question() called with question_id={question_id}, previous_questions={previous_questions}")

    all_questions = await sync_to_async(lambda: respondent.poll.questions.all())()
    answered_ids = Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    next_question = await all_questions.exclude(id__in=answered_ids).afirst()

    print(f"🔎 Next question: {next_question.id if next_question else 'None'}")

    if next_question and next_question.order == 1:
        show_back_button = False
    else:
        show_back_button = True

    if show_back_button is False:
        await message.answer(next_question.poll.description)

    if not next_question:
        print("✅ All questions completed.")
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await message.answer(str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        await state.clear()
        return

    updated_history = previous_questions + [question_id]
    print(f"📜 Updated history: {updated_history}")

    respondent.history = updated_history
    await respondent.asave()

    await state.update_data(question_id=next_question.id, previous_questions=updated_history)
    print(f"💾 State updated with question_id={next_question.id}")

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
    print(f"📋 Choices: {choice_map}")

    for idx, choice in enumerate(choices, start=1):
        msg_text += f"{idx}. {choice.text}\n"

    await state.update_data(choice_map=choice_map)

    if next_question.type in [
        Question.QuestionTypeChoices.CLOSED_SINGLE,
        Question.QuestionTypeChoices.CLOSED_MULTIPLE,
        Question.QuestionTypeChoices.MIXED
    ]:
        markup = get_keyboards_markup(next_question, choices, show_back_button=show_back_button)
        msg_text += "\n" + str(_("Жавобни танланг (номер билан) 👇"))
        await message.answer(msg_text, reply_markup=markup)
    else:
        await message.answer(msg_text + "\n" + str(_("Жавобингизни ёзинг ✍️")),
                             reply_markup=types.ReplyKeyboardRemove())


async def get_current_question(message: Message, state: FSMContext, user: TGUser):
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


async def show_multiselect_question(message, choice_map, selected_choices,
                                    question_text="Номалум савол", show_back_button=True):
    print(f"🧩 show_multiselect_question with selected: {selected_choices}, show_back_button={show_back_button}")
    question_text = str(_("Савол: ")) + question_text + "\n\n"
    msg_text = question_text + str(_("Танланган жавоблар ✅ билан белгиланган:\n\n"))
    display_choices = []

    for num, cid in choice_map.items():
        choice = await Choice.objects.aget(id=cid)
        marker = "✅ " if cid in selected_choices else ""
        text = f"{marker}{num}. {choice.text}"
        msg_text += text + "\n"
        display_choices.append((num, marker))

    number_buttons = [types.KeyboardButton(text=f"{marker}{num}".strip()) for num, marker in display_choices]
    keyboard = [number_buttons[i:i + 6] for i in range(0, len(number_buttons), 6)]

    bottom_buttons = [types.KeyboardButton(text=NEXT_STR)]
    if show_back_button:
        bottom_buttons.append(types.KeyboardButton(text=BACK_STR))
    keyboard.append(bottom_buttons)

    print(f"⌨️ Generated keyboard with {len(number_buttons)} buttons")
    markup = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer(msg_text, reply_markup=markup)


def get_keyboards_markup(next_question, choices, show_back_button=True):
    print(
        f"🛠 get_keyboards_markup: question={next_question.id}, type={next_question.type}, show_back_button={show_back_button}")

    number_buttons = [types.KeyboardButton(text=str(i)) for i in range(1, len(choices) + 1)]
    keyboard = [number_buttons[i:i + 6] for i in range(0, len(number_buttons), 6)]

    bottom_buttons = []
    if next_question.type == Question.QuestionTypeChoices.MIXED:
        bottom_buttons.append(types.KeyboardButton(text=ANOTHER_STR))
    if show_back_button:
        bottom_buttons.append(types.KeyboardButton(text=BACK_STR))

    if bottom_buttons:
        keyboard.append(bottom_buttons)

    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
