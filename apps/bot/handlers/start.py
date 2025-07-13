from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PollAnswer
from asgiref.sync import sync_to_async

from apps.bot.states import PollStates
from apps.bot.utils import get_current_question, get_next_question
from apps.polls.models import Answer, Question
from apps.users.models import TGUser

start_router = Router()


@start_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext, user: TGUser | None):
    unfinished_answer = await Answer.objects.select_related("question", "respondent").filter(
        respondent__tg_user=user,
        is_answered=False,
        telegram_msg_id__isnull=False
    ).order_by("-id").afirst()
    print(unfinished_answer, "$" * 50)

    if unfinished_answer:
        try:
            await message.bot.delete_message(
                chat_id=unfinished_answer.telegram_chat_id,
                message_id=unfinished_answer.telegram_msg_id
            )
            print(f"🗑️ Удалено старое сообщение: {unfinished_answer.telegram_msg_id}")
        except Exception as e:
            print(f"⚠️ Не удалось удалить сообщение: {e}")

    # 2. Получаем и отправляем текущий неотвеченный вопрос
    await get_current_question(message.bot, message.from_user.id, state, user)


@start_router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer, state: FSMContext, user: TGUser | None):
    print("WORKING")
    telegram_poll_id = poll_answer.poll_id

    try:
        answer = await Answer.objects.select_related("question", "respondent").aget(
            telegram_poll_id=telegram_poll_id
        )
    except Answer.DoesNotExist:
        print("❌ Не найден answer по poll_id")
        return

    if not poll_answer.option_ids:
        print("⚠️ Пользователь ничего не выбрал, повторяем вопрос")
        unfinished_answer = await Answer.objects.select_related("question", "respondent").filter(
            respondent__tg_user=user,
            is_answered=False,
            telegram_msg_id__isnull=False
        ).order_by("-id").afirst()
        await poll_answer.bot.delete_message(chat_id=unfinished_answer.telegram_chat_id,
                                             message_id=unfinished_answer.telegram_msg_id)
        await get_current_question(poll_answer.bot, poll_answer.user.id, state, user)
        return
    selected_index = poll_answer.option_ids[0]

    # Загружаем варианты
    choices = await sync_to_async(list)(
        answer.question.choices.all().order_by("order")
    )

    is_mixed = answer.question.type == Question.QuestionTypeChoices.MIXED

    if is_mixed and selected_index == len(choices):
        # Выбран вариант "Бошқа"
        print("IS MIXED")
        await state.update_data(
            answer_id=answer.id,
            respondent_id=answer.respondent_id,
            question_id=answer.question_id
        )
        await poll_answer.bot.send_message(
            poll_answer.user.id,
            "📝 Илтимос, ўз жавобингизни матн сифатида юборинг:"
        )
        await state.set_state(PollStates.waiting_for_mixed_custom_input)
        return

    # Обычный выбор — сохраняем выбранный вариант
    try:
        selected_choice = choices[selected_index]
    except IndexError:
        print("❌ Неверный индекс опции")
        return

    await answer.selected_choices.aadd(selected_choice)
    answer.is_answered = True
    await answer.asave()

    print(f"✅ User {answer.respondent.tg_user_id} выбрал: {selected_choice.text}")
    await poll_answer.bot.delete_message(chat_id=answer.telegram_chat_id, message_id=answer.telegram_msg_id)
    # Следующий вопрос
    await get_next_question(poll_answer.bot, poll_answer.user.id, state, answer.respondent,
                            answer.respondent.history, answer.question_id)


@start_router.message(PollStates.waiting_for_mixed_custom_input)
async def handle_custom_input_for_mixed(message: Message, state: FSMContext):
    print("HANDLING")
    data = await state.get_data()
    answer_id = data.get("answer_id")

    try:
        answer = await Answer.objects.select_related("respondent").aget(id=answer_id)
    except Answer.DoesNotExist:
        await message.answer("❌ Жавобни сақлашда хато юз берди.")
        return

    answer.open_answer = message.text.strip()
    await answer.asave()
    await message.answer("✅ Жавоб қабул қилинди!")

    await get_next_question(message.bot, message.chat.id, state, answer.respondent, answer.respondent.history,
                            answer.question.id)
