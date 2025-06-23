from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.bot.utils import get_current_question, BACK_STR, ANOTHER_STR, get_next_question, show_multiselect_question, \
    NEXT_STR, get_keyboards_markup
from apps.polls.models import Respondent, Answer, Question, Choice
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
    choice_map = data.get("choice_map", {})

    respondent = await Respondent.objects.aget(id=respondent_id)
    previous_questions = list(respondent.history or [])
    answer_text = message.text.strip()

    current_question = await Question.objects.select_related("poll").aget(id=question_id)
    show_back_button = current_question.order != 1
    if show_back_button is False:
        await message.answer(current_question.poll.description)

    # 🔙 Обработка кнопки "Назад"
    if answer_text == BACK_STR:
        current_poll = await sync_to_async(lambda: respondent.poll)()
        current_order = current_question.order

        if current_order == 1:
            await message.answer(str(_("Бу биринчи савол. Орқага қайтиш мумкин эмас.")))
            return

        previous_question = await Question.objects.filter(
            poll=current_poll,
            order__lt=current_order
        ).select_related("poll").order_by('-order').afirst()

        if not previous_question:
            await message.answer(str(_("Аввалги савол топилмади.")))
            return

        respondent.history = respondent.history[:-1]
        await respondent.asave()
        await Answer.objects.filter(respondent=respondent, question_id=question_id).adelete()

        await state.update_data(
            question_id=previous_question.id,
            previous_questions=respondent.history,
            selected_choices=[]  # ⬅️ очищаем список выбранных ответов
        )

        await render_question(message, state, previous_question, respondent.history)
        await state.set_state(PollStates.waiting_for_answer)
        return

    await Answer.objects.filter(respondent=respondent, question=current_question).adelete()
    answer = await Answer.objects.acreate(respondent=respondent, question=current_question)

    if current_question.type == Question.QuestionTypeChoices.OPEN:
        answer.open_answer = answer_text
        await answer.asave()

    elif current_question.type in [Question.QuestionTypeChoices.CLOSED_SINGLE, Question.QuestionTypeChoices.MIXED]:
        if answer_text == ANOTHER_STR:
            await state.set_state(PollStates.waiting_for_answer)
            await message.answer(str(_("Илтимос, ўз жавобингизни матн сифатида юборинг ✍️")),
                                 reply_markup=types.ReplyKeyboardRemove())
            return
        choice_id = choice_map.get(answer_text)
        if not choice_id:
            await message.answer(str(_("Бундай рақам йўқ. Илтимос, берилган рақамлардан танланг.")))
            return
        choice = await Choice.objects.aget(id=choice_id)
        await sync_to_async(answer.selected_choices.add)(choice)

    elif current_question.type == Question.QuestionTypeChoices.CLOSED_MULTIPLE:
        current_selected = set(data.get("selected_choices", []))
        if answer_text == NEXT_STR:
            if not current_selected:
                await message.answer(str(_("Илтимос, камида бир вариантни танланг.")))
                return
            selected_objs = [await Choice.objects.aget(id=cid) for cid in current_selected]
            await sync_to_async(answer.selected_choices.add)(*selected_objs)
            await state.update_data(selected_choices=[])
            await get_next_question(message, state, previous_questions, respondent, question_id)
            await state.set_state(PollStates.waiting_for_answer)
            return
        if answer_text.startswith("✅"):
            num = answer_text.replace("✅", "").strip()
            cid = choice_map.get(num)
            if cid and cid in current_selected:
                current_selected.remove(cid)
                await state.update_data(selected_choices=list(current_selected))
            await show_multiselect_question(message, choice_map, current_selected,
                                            question_text=current_question.text,
                                            show_back_button=show_back_button)
            return
        cid = choice_map.get(answer_text)
        if not cid:
            await message.answer(str(_(f'"{answer_text}" — нотўғри рақам. Илтимос, берилган рақамлардан танланг.')))
            return
        max_select = getattr(current_question, "max_choices", 3)
        if len(current_selected) >= max_select and cid not in current_selected:
            await message.answer(
                str(_("Кўп жавоб белгиланди. Илтимос, ортиқча танловни олиб ташланг ёки давом этинг."))
            )
            return
        current_selected.add(cid)
        await state.update_data(selected_choices=list(current_selected))

        await show_multiselect_question(message, choice_map, current_selected,
                                        question_text=current_question.text,
                                        show_back_button=show_back_button)
        return
    else:
        await message.answer(str(_("Бу турдаги савол ҳозирча қўллаб-қувватланмайди.")))
        return

    await get_next_question(message, state, previous_questions, respondent, question_id)
    await state.set_state(PollStates.waiting_for_answer)


async def render_question(message: Message, state: FSMContext, question: Question,
                          previous_questions: list):
    show_back_button = question.order != 1
    if show_back_button is False:
        await message.answer(str(_(question.poll.description)))

    await state.update_data(question_id=question.id, previous_questions=previous_questions)

    choices = await sync_to_async(list)(question.choices.all().order_by("order"))
    choice_map = {str(idx): choice.id for idx, choice in enumerate(choices, start=1)}

    msg_text = f"{_('Савол: ')} {question.text}\n\n"
    for idx, choice in enumerate(choices, start=1):
        msg_text += f"{idx}. {choice.text}\n"

    await state.update_data(choice_map=choice_map)

    if question.type in [Question.QuestionTypeChoices.CLOSED_SINGLE, Question.QuestionTypeChoices.CLOSED_MULTIPLE,
                         Question.QuestionTypeChoices.MIXED]:
        markup = get_keyboards_markup(question, choices, show_back_button=show_back_button)
        msg_text += "\n" + str(_("Жавобни танланг (номер билан) 👇"))
        await message.answer(msg_text, reply_markup=markup)
    else:
        await message.answer(msg_text + "\n" + str(_("Жавобингизни ёзинг ✍️")),
                             reply_markup=types.ReplyKeyboardRemove())
