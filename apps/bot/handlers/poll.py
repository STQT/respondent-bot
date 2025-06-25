from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.bot.utils import get_next_question, render_question, show_multiselect_question
from apps.bot.inline_keyboards import render_selected_single_answer_text
from apps.polls.models import Respondent, Answer, Question, Choice
from apps.users.models import TGUser

poll_router = Router()


@poll_router.callback_query()
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext, user: TGUser):
    data = await state.get_data()
    respondent_id = data["respondent_id"]
    question_id = data["question_id"]
    choice_map = data.get("choice_map", {})
    selected_choices = set(data.get("selected_choices", []))

    respondent = await Respondent.objects.select_related("poll").aget(id=respondent_id)
    current_question = await Question.objects.aget(id=question_id)
    show_back_button = current_question.order != 1

    # Обработка callback data
    cb_data = callback_query.data

    if cb_data == "back":
        prev_q = await Question.objects.filter(
            poll=respondent.poll, order__lt=current_question.order
        ).select_related("poll").order_by("-order").afirst()
        if not prev_q:
            await callback_query.message.answer(str(_("Аввалги савол топилмади.")))
            return
        respondent.history = respondent.history[:-1]
        await respondent.asave()
        await Answer.objects.filter(respondent=respondent, question_id=question_id).adelete()
        await state.update_data(
            question_id=prev_q.id,
            previous_questions=respondent.history,
            selected_choices=[]
        )
        await callback_query.answer()
        await callback_query.message.edit_reply_markup(reply_markup=None)
        await render_question(callback_query.message, state, prev_q, respondent.history)
        await state.set_state(PollStates.waiting_for_answer)
        # await callback_query.message.delete()
        return

    if cb_data == "custom_input":
        await state.set_state(PollStates.waiting_for_answer)
        await callback_query.message.answer(str(_("Илтимос, ўз жавобингизни матн сифатида юборинг ✍️")))
        await callback_query.answer()
        await callback_query.message.edit_reply_markup(reply_markup=None)
        # await callback_query.message.delete()
        return

    if cb_data.startswith("choice:"):
        choice_id = int(cb_data.split(":")[1])
        await Answer.objects.filter(respondent=respondent, question=current_question).adelete()
        answer = await Answer.objects.acreate(respondent=respondent, question=current_question)
        choice = await Choice.objects.aget(id=choice_id)
        await sync_to_async(answer.selected_choices.add)(choice)

        # Обновляем состояние, чтобы отрисовать с отметкой ✅
        await state.update_data(selected_id=choice.id)
        await callback_query.answer()

        # 1️⃣ Сначала: показать текущий вопрос с отметкой (редактируем старое сообщение)
        choices = await sync_to_async(lambda: list(current_question.choices.all().order_by("order")))()
        msg_text = render_selected_single_answer_text(current_question, choices, selected_id=choice.id)
        await callback_query.message.edit_text(msg_text)

        # 2️⃣ Потом: отправляем новый вопрос — отдельным сообщением
        await get_next_question(callback_query.message, state, respondent.history, respondent, question_id)
        await state.set_state(PollStates.waiting_for_answer)
        return

    if cb_data.startswith("toggle:"):
        cid = int(cb_data.split(":")[1])
        if cid in selected_choices:
            selected_choices.remove(cid)
        else:
            max_select = getattr(current_question, "max_choices", 3)
            if len(selected_choices) >= max_select:
                await callback_query.answer(str(_("Ортиқча танлов. Илтимос, аввалги танловни бекор қилинг.")),
                                            show_alert=True)
                return
            selected_choices.add(cid)
        await state.update_data(selected_choices=list(selected_choices))
        await callback_query.answer()
        await show_multiselect_question(callback_query.message, choice_map, selected_choices, current_question.text,
                                        show_back_button)
        return

    if cb_data == "next":
        if not selected_choices:
            await callback_query.answer(str(_("Илтимос, камида битта жавобни танланг.")), show_alert=True)
            return
        await Answer.objects.filter(respondent=respondent, question=current_question).adelete()
        answer = await Answer.objects.acreate(respondent=respondent, question=current_question)
        selected_objs = [await Choice.objects.aget(id=cid) for cid in selected_choices]
        await sync_to_async(answer.selected_choices.add)(*selected_objs)
        await state.update_data(selected_choices=[])
        await callback_query.answer()
        await callback_query.message.edit_reply_markup(reply_markup=None)
        await get_next_question(callback_query.message, state, respondent.history, respondent, question_id)
        await state.set_state(PollStates.waiting_for_answer)
        # await callback_query.message.delete()
        return


@poll_router.message(PollStates.waiting_for_answer)
async def process_custom_input(message: types.Message, state: FSMContext, user: TGUser):
    data = await state.get_data()
    respondent_id = data["respondent_id"]
    question_id = data["question_id"]

    respondent = await Respondent.objects.aget(id=respondent_id)
    current_question = await Question.objects.aget(id=question_id)

    await Answer.objects.filter(respondent=respondent, question=current_question).adelete()
    answer = await Answer.objects.acreate(respondent=respondent, question=current_question)
    answer.open_answer = message.text.strip()
    await answer.asave()

    await get_next_question(message, state, respondent.history, respondent, question_id)
    await state.set_state(PollStates.waiting_for_answer)
