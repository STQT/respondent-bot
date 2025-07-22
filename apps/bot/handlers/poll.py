from django.utils.translation import gettext_lazy as _
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from apps.bot.states import PollStates
from apps.bot.utils import get_next_question
from apps.polls.models import Respondent, Answer, Question
from apps.users.models import TGUser

poll_router = Router()


@poll_router.message(PollStates.waiting_for_answer)
async def process_custom_input(message: types.Message, state: FSMContext, user: TGUser):
    data = await state.get_data()
    respondent_id = data.get("respondent_id")
    question_id = data.get("question_id")

    if not respondent_id or not question_id:
        await message.answer(str(_("Сўровнома яроқсиз ҳолатда. Илтимос, ҳавола орқали қайтадан бошланг.")))
        await state.clear()
        return

    try:
        respondent = await Respondent.objects.aget(id=respondent_id)
    except Respondent.DoesNotExist:
        await message.answer(str(_("Сўровнома маълумотлари топилмади. Илтимос, ҳавола орқали қайтадан бошланг.")))
        await state.clear()
        return

    current_question = await Question.objects.aget(id=question_id)

    # 🔧 Заменили delete/create на update_or_create
    answer, _updated = await Answer.objects.aupdate_or_create(
        respondent=respondent,
        question=current_question,
        defaults={"open_answer": message.text.strip(), "is_answered": True}
    )
    await message.answer("✅ Жавоб қабул қилинди!", reply_markup=ReplyKeyboardRemove())
    await state.clear()
    await get_next_question(
        message.bot,
        message.from_user.id,
        state,
        respondent,
        respondent.history,
        question_id
    )
