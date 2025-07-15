from datetime import timezone

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import Message, PollAnswer
from asgiref.sync import sync_to_async
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.bot.utils import get_current_question, get_next_question
from apps.polls.models import Answer, Question, Respondent, Poll
from apps.users.models import TGUser

start_router = Router()


@start_router.message(CommandStart(deep_link=True))
async def command_start_handler(message: Message, state: FSMContext, user: TGUser | None, command):
    poll_uuid = None
    if command.args and command.args.startswith("poll_"):
        poll_uuid = command.args.removeprefix("poll_")

    if poll_uuid:
        poll = await Poll.objects.filter(uuid=poll_uuid, deadline__gte=timezone.now()).afirst()
        if not poll:
            await message.answer(str(_("Кечирасиз, ушбу сўровнома топилмади ёки муддати тугаган.")))
            return

        respondent = await Respondent.objects.filter(tg_user=user, poll=poll).afirst()

        if respondent:
            if respondent.finished_at:
                # ✅ Уже прошел — предложить повторить
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Қайта бошлаш", callback_data=f"poll_restart:{poll.uuid}")]
                ])
                await message.answer(str(_("Сиз бу сўровномани аввал якунлагансиз.")), reply_markup=markup)
            else:
                # 🔁 Не окончен — предложить продолжить или начать заново
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔄 Давом этиш", callback_data=f"poll_continue:{poll.uuid}"),
                        InlineKeyboardButton(text="♻️ Қайта бошлаш", callback_data=f"poll_restart:{poll.uuid}")
                    ]
                ])
                await message.answer(
                    str(_("Сиз сўровномани тўлиқ якунламагансиз. Давом этасизми ёки қайта бошлайсизми?")),
                    reply_markup=markup)
        else:
            # ✳️ Первый раз — сразу запустить
            await get_current_question(message.bot, message.from_user.id, state, user, poll_uuid=poll_uuid)
    else:
        # Стандартный сценарий
        await get_current_question(message.bot, message.from_user.id, state, user)


@start_router.callback_query(lambda c: c.data.startswith("poll_"))
async def poll_callback_handler(callback, state: FSMContext, user: TGUser | None):
    action, poll_uuid = callback.data.split(":", 1)
    poll = await Poll.objects.filter(uuid=poll_uuid, deadline__gte=timezone.now()).afirst()

    if not poll:
        await callback.message.edit_text(str(_("Кечирасиз, ушбу сўровнома топилмади ёки муддати тугаган.")))
        return

    if action == "poll_continue":
        await callback.message.delete()
        await get_current_question(callback.bot, callback.from_user.id, state, user, poll_uuid=poll_uuid)
    elif action == "poll_restart":
        # ❗ Удаляем старого респондента и его ответы
        await Answer.objects.filter(respondent__tg_user=user, respondent__poll=poll).adelete()
        await Respondent.objects.filter(tg_user=user, poll=poll).adelete()

        await callback.message.delete()
        await get_current_question(callback.bot, callback.from_user.id, state, user, poll_uuid=poll_uuid)


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
                            answer.question_id)
