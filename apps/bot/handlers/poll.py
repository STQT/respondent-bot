from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.bot.utils import get_current_question, BACK_STR, ANOTHER_STR, get_next_question, show_multiselect_question, \
    NEXT_STR
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

    # 🔙 Обработка кнопки "Назад"
    if answer_text == BACK_STR:
        current_poll = await sync_to_async(lambda: respondent.poll)()
        current_question = await Question.objects.aget(id=question_id)
        current_order = current_question.order

        if current_order == 1:
            await message.answer(str(_("Бу биринчи савол. Орқага қайтиш мумкин эмас.")))
            return

        # Получаем предыдущий вопрос по order
        previous_question = await Question.objects.filter(
            poll=current_poll,
            order__lt=current_order
        ).order_by('-order').afirst()

        if not previous_question:
            await message.answer(str(_("Аввалги савол топилмади.")))
            return

        # Обновим history и удалим текущий ответ
        respondent.history = respondent.history[:-1]
        await respondent.asave()
        await Answer.objects.filter(respondent=respondent, question_id=question_id).adelete()

        await state.update_data(
            question_id=previous_question.id,
            previous_questions=respondent.history
        )

        await get_next_question(
            message=message,
            state=state,
            previous_questions=respondent.history,
            respondent=respondent,
            question_id=previous_question.id
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

    elif question.type == Question.QuestionTypeChoices.CLOSED_MULTIPLE:
        current_selected = set(data.get("selected_choices", []))
        if answer_text == NEXT_STR:
            if not current_selected:
                await message.answer(str(_("Илтимос, камида бир вариантни танланг.")))
                return
            selected_objs = [await Choice.objects.aget(id=cid) for cid in current_selected]
            await sync_to_async(answer.selected_choices.add)(*selected_objs)
            await state.update_data(selected_choices=[])  # очистить
            await get_next_question(message, state, previous_questions, respondent, question_id)
            await state.set_state(PollStates.waiting_for_answer)
            return
        if answer_text.startswith("✅"):
            num = answer_text.replace("✅", "").strip()
            cid = choice_map.get(num)
            if cid and cid in current_selected:
                current_selected.remove(cid)
                await state.update_data(selected_choices=list(current_selected))
            show_back_button = question.order != 1
            await show_multiselect_question(message, choice_map, current_selected, show_back_button=show_back_button)
            return
        cid = choice_map.get(answer_text)
        if not cid:
            await message.answer(str(_(f'"{answer_text}" — нотўғри рақам. Илтимос, берилган рақамлардан танланг.')))
            return
        max_select = getattr(question, "max_choices", 3)
        if len(current_selected) >= max_select and cid not in current_selected:
            await message.answer(
                str(_("Кўп жавоб белгиланди. Илтимос, ортиқча танловни олиб ташланг ёки давом этинг."))
            )
            return
        current_selected.add(cid)
        await state.update_data(selected_choices=list(current_selected))
        show_back_button = question.order != 1
        await show_multiselect_question(message, choice_map, current_selected, show_back_button=show_back_button)
        return
    else:
        await message.answer(str(_("Бу турдаги савол ҳозирча қўллаб-қувватланмайди.")))
        return
    await get_next_question(message, state, previous_questions, respondent, question_id)
    await state.set_state(PollStates.waiting_for_answer)
