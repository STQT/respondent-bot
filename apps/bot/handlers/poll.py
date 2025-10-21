from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from asgiref.sync import sync_to_async

from apps.bot.states import PollStates
from apps.bot.utils import get_next_question, send_confirmation_text
from apps.bot.captcha_utils import (
    get_captcha_error_message,
    get_captcha_failed_message,
    get_captcha_success_message
)
from apps.polls.models import Respondent, Answer, Question, CaptchaChallenge
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
    open_answer = message.text.strip()
    # 🔧 Заменили delete/create на update_or_create
    answer, _updated = await Answer.objects.aupdate_or_create(
        respondent=respondent,
        question=current_question,
        defaults={"open_answer": open_answer, "is_answered": True}
    )
    if not answer.telegram_chat_id:
        answer.telegram_chat_id = message.chat.id
        await answer.asave()

    await send_confirmation_text(message.bot, answer, open_answer)
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


@poll_router.message(PollStates.waiting_for_captcha)
async def process_captcha_answer(message: types.Message, state: FSMContext, user: TGUser):
    """Обработка ответа на капчу"""
    data = await state.get_data()
    captcha_id = data.get("captcha_id")
    respondent_id = data.get("respondent_id")
    previous_questions = data.get("previous_questions", [])
    question_id = data.get("question_id")
    
    if not captcha_id:
        await message.answer("Ошибка: капча не найдена")
        await state.clear()
        return
    
    try:
        captcha = await CaptchaChallenge.objects.aget(id=captcha_id)
        respondent = await Respondent.objects.select_related('tg_user', 'poll').aget(id=respondent_id)
    except (CaptchaChallenge.DoesNotExist, Respondent.DoesNotExist):
        await message.answer("Ошибка: данные не найдены")
        await state.clear()
        return
    
    user_answer = message.text.strip().lower()
    correct_answer = captcha.correct_answer.lower()
    
    # Обновляем капчу
    captcha.user_answer = message.text.strip()
    captcha.attempts += 1
    
    if user_answer == correct_answer:
        # Правильный ответ
        captcha.is_correct = True
        captcha.solved_at = timezone.now()
        await sync_to_async(captcha.save)()
        
        # Отправляем сообщение об успехе
        await message.answer(get_captcha_success_message(user.lang))
        
        # Продолжаем опрос
        await state.clear()
        await get_next_question(
            message.bot,
            message.from_user.id,
            state,
            respondent,
            previous_questions,
            question_id
        )
    else:
        # Неправильный ответ
        await sync_to_async(captcha.save)()
        
        if captcha.attempts >= 3:
            # Превышено количество попыток
            await message.answer(get_captcha_failed_message(user.lang))
            
            # Удаляем респондента и его ответы (бот)
            await sync_to_async(Answer.objects.filter(respondent=respondent).delete)()
            await sync_to_async(respondent.delete)()
            
            await state.clear()
        else:
            # Еще есть попытки
            await message.answer(get_captcha_error_message(user.lang, captcha.attempts))
            # Состояние остается тем же - ждем новый ответ
