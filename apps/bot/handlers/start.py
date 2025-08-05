from uuid import UUID

from aiogram.enums import ChatAction
from django.utils import timezone

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.types import Message, PollAnswer
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.bot.utils import get_current_question, get_next_question, poll_checker, ANOTHER_STR, send_confirmation_text
from apps.polls.models import Answer, Question, Respondent, Poll
from apps.users.models import TGUser

start_router = Router()


async def safe_edit_text(message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    try:
        if message.text != text:
            await message.edit_text(text, reply_markup=reply_markup)
        elif message.reply_markup != reply_markup:
            await message.edit_reply_markup(reply_markup=reply_markup)
        else:
            print("ℹ️ Пропущено редактирование: текст и кнопки не изменились.")
    except TelegramBadRequest as e:
        print(f"⚠️ Ошибка при редактировании сообщения: {e}")


async def safe_delete_or_edit(message, text: str = None, reply_markup=None):
    """
    Безопасно удаляет или редактирует сообщение.
    Если текст указан — редактирует, иначе удаляет.
    """
    try:
        if text is not None:
            await message.edit_text(text, reply_markup=reply_markup)
        else:
            await message.delete()
    except Exception as e:
        print(f"⚠️ safe_delete_or_edit error: {e}")


@start_router.message(CommandStart(deep_link=True))
async def command_start_handler(message: Message, state: FSMContext, user: TGUser | None, command):
    await message.bot.send_chat_action(message.from_user.id, action=ChatAction.TYPING)

    await state.clear()  # ✅ Всегда сбрасываем состояние
    if command.args and command.args.startswith("poll_"):
        raw_uuid = command.args.removeprefix("poll_")
        try:
            # ✅ Проверка валидности UUID
            poll_uuid = str(UUID(raw_uuid))
        except ValueError:
            poll_uuid = None
    else:
        poll_uuid = None

    if poll_uuid is None:
        await message.answer(str(_("Саволномадан отиш учун линкдан фойдаланинг")))
        return

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


@start_router.callback_query(lambda c: c.data.startswith("poll_"))
async def poll_callback_handler(callback, state: FSMContext, user: TGUser | None):
    action, poll_uuid = callback.data.split(":", 1)
    poll = await Poll.objects.filter(uuid=poll_uuid, deadline__gte=timezone.now()).afirst()

    if not poll:
        await callback.message.edit_text(str(_("Кечирасиз, ушбу сўровнома топилмади ёки муддати тугаган.")))
        return

    if action == "poll_continue":
        await safe_edit_text(callback.message, str(_("Сўровнома давом этилди.")))
        await get_current_question(callback.bot, callback.from_user.id, state, user, poll_uuid=poll_uuid)
    elif action == "poll_restart":
        # ❗ Удаляем старого респондента и его ответы
        await Answer.objects.filter(respondent__tg_user=user, respondent__poll=poll).adelete()
        await Respondent.objects.filter(tg_user=user, poll=poll).adelete()

        await safe_delete_or_edit(callback.message, str(_("Сўровнома янгидан бошланди.")))
        await get_current_question(callback.bot, callback.from_user.id, state, user, poll_uuid=poll_uuid)


@start_router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer, state: FSMContext, user: TGUser | None):
    await poll_answer.bot.send_chat_action(poll_answer.user.id, action=ChatAction.TYPING)
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
    selected_indexes = poll_answer.option_ids
    max_choices = answer.question.max_choices or 0

    question = await sync_to_async(lambda: answer.question)()
    if question.type in (
        Question.QuestionTypeChoices.CLOSED_MULTIPLE,
        Question.QuestionTypeChoices.MIXED_MULTIPLE,
    ) and max_choices > 0:
        if len(selected_indexes) > max_choices:
            # 🛑 Удаляем сообщение с poll
            await poll_answer.bot.delete_message(chat_id=answer.telegram_chat_id,
                                                 message_id=answer.telegram_msg_id)

            # 🔄 Повторно отправляем вопрос с предупреждением
            choices = await sync_to_async(list)(answer.question.choices.all().order_by("order"))
            options = [choice.text for choice in choices]

            if answer.question.type == Question.QuestionTypeChoices.MIXED_MULTIPLE:
                options.append(ANOTHER_STR)

            if len(options) > 10:
                await poll_answer.bot.send_message(
                    chat_id=answer.telegram_chat_id,
                    text=str(_("Ушбу савол жавоби 10 та жавобдан коп! Админ билан богланинг"))
                )
                return
            if await poll_checker(poll_answer.bot, answer.telegram_chat_id, answer.question, options) is True:
                poll_message = await poll_answer.bot.send_poll(
                    chat_id=answer.telegram_chat_id,
                    question=answer.question.text + f"\n⚠️ Иложи борича энг кўпи билан {max_choices} та жавобни танланг.",
                    options=options,
                    is_anonymous=False,
                    allows_multiple_answers=True,
                    protect_content=True
                )

                # 🔄 Обновляем answer с новым poll_id и message_id
                answer.telegram_poll_id = poll_message.poll.id
                answer.telegram_msg_id = poll_message.message_id
                answer.telegram_chat_id = poll_message.chat.id
                await answer.asave()
                return

    # Загружаем варианты
    choices = await sync_to_async(list)(answer.question.choices.all().order_by("order"))
    selected_choice_objs = [choices[i] for i in selected_indexes if i < len(choices)]

    is_mixed = answer.question.type in [
        Question.QuestionTypeChoices.MIXED,
        Question.QuestionTypeChoices.MIXED_MULTIPLE
    ]

    is_boshqa_selected = len(choices) in selected_indexes
    if is_mixed and is_boshqa_selected:
        selected_indexes = [i for i in selected_indexes if i != len(choices)]
        selected_choice_objs = [choices[i] for i in selected_indexes if i < len(choices)]

        # сохраняем выбранные до "Бошқа"
        await sync_to_async(answer.selected_choices.set)(selected_choice_objs)
        answer.is_answered = False
        await answer.asave()

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


    await sync_to_async(answer.selected_choices.set)(selected_choice_objs)
    answer.is_answered = True
    await answer.asave()
    await send_confirmation_text(poll_answer.bot, answer)
    # Следующий вопрос
    await get_next_question(poll_answer.bot, poll_answer.user.id, state, answer.respondent,
                            answer.respondent.history, answer.question_id)


@start_router.message(PollStates.waiting_for_mixed_custom_input)
async def handle_custom_input_for_mixed(message: Message, state: FSMContext, user: TGUser | None):
    await message.bot.send_chat_action(message.from_user.id, action=ChatAction.TYPING)

    data = await state.get_data()
    answer_id = data.get("answer_id")

    try:
        answer = await Answer.objects.select_related("respondent__poll", "question").aget(id=answer_id)
    except Answer.DoesNotExist:
        await message.answer("❌ Жавобни сақлашда хато юз берди.")
        return
    if message.text:
        open_answer = message.text.strip()
        answer.open_answer = open_answer
        await answer.asave()
        await send_confirmation_text(message.bot, answer, open_answer)
        await message.answer("✅ Жавоб қабул қилинди!", reply_markup=ReplyKeyboardRemove())

        await get_next_question(message.bot, message.chat.id, state, answer.respondent, answer.respondent.history,
                                answer.question_id)
    else:
        await get_current_question(message.bot, message.from_user.id, state, user)
