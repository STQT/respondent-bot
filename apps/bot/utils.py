import re

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.db.models import OuterRef, Exists
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bot.states import PollStates
from apps.polls.models import Poll, Respondent, Answer, Question
from apps.users.models import TGUser

ANOTHER_STR = str(_("Бошқа(ёзинг)__________"))
BACK_STR = str(_("🔙 Ортга"))
NEXT_STR = str(_("➡️ Кейинги савол"))


def escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы MarkdownV2.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


async def poll_checker(bot, chat_id, question, options):
    if len(question.text) > 255:
        await bot.send_message(
            chat_id=chat_id,
            text=question.text + "\n\n" + str(_("Савол матни жуда узун. Админ билан боғланинг."))
        )
        return

    if len(options) > 10:
        await bot.send_message(
            chat_id=chat_id,
            text=question.text + "\n\n" + str(_("Ушбу савол жавоби 10 та жавобдан коп! Админ билан богланинг"))
        )
        return

    for opt in options:
        if len(opt) > 100:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    question.text + "\n\n" + opt + "\n\n" + str(_(
                    "Жавоб вариантларидан бири 100 белгидан узун. Админ билан боғланинг."
                ))
                )
            )
            return
    return True


async def send_poll_question(bot: Bot, chat_id: int, state: FSMContext, respondent: Respondent, question: Question):
    choices = await sync_to_async(list)(question.choices.all().order_by("order"))
    allows_multiple_answers = question.type in (
        Question.QuestionTypeChoices.CLOSED_MULTIPLE,
        Question.QuestionTypeChoices.MIXED_MULTIPLE
    )

    # 💬 Открытый или смешанный вопрос — отправим текст
    if question.type == Question.QuestionTypeChoices.OPEN:
        await bot.send_message(
            chat_id,
            f"📨 {question.text}\n\nИлтимос, жавобингизни матн сифатида юборинг ✍️"
        )

        # Создаём пустой Answer для отслеживания
        answer = await Answer.objects.filter(
            respondent=respondent,
            question=question
        ).select_related("respondent", "question").afirst()
        if not answer:
            answer = await Answer.objects.acreate(
                respondent=respondent,
                question=question
            )
        await state.set_state(PollStates.waiting_for_answer)
        # Обновляем состояние FSM, чтобы ждать текстовый ответ
        await state.update_data(
            question_id=question.id,
            respondent_id=respondent.id,
            answer_id=answer.id
        )
        return

    # 📊 Закрытый вопрос — отправим Telegram poll
    options = [choice.text for choice in choices]
    if question.type in [
        Question.QuestionTypeChoices.MIXED,
        Question.QuestionTypeChoices.MIXED_MULTIPLE
    ]:
        options.append(ANOTHER_STR)

    if await poll_checker(bot, chat_id, question, options) is True:
        poll_message = await bot.send_poll(
            chat_id=chat_id,
            question=question.text,
            options=options,
            is_anonymous=False,
            allows_multiple_answers=allows_multiple_answers,
            protect_content=True
        )

        # Создаём или обновляем Answer с telegram_poll_id
        answer, created = await Answer.objects.aupdate_or_create(
            respondent=respondent,
            question=question,
            defaults={"telegram_poll_id": poll_message.poll.id,
                      "telegram_msg_id": poll_message.message_id,
                      "telegram_chat_id": poll_message.chat.id
                      }
        )
        await sync_to_async(lambda: answer.question)()
        await sync_to_async(lambda: answer.respondent)()

    await state.clear()


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


async def get_next_question(bot, chat_id, state: FSMContext, respondent, previous_questions, question_id):
    all_questions = await sync_to_async(lambda: respondent.poll.questions.order_by("order"))()
    answered_ids = await sync_to_async(list)(
        Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    )
    next_question = await all_questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await bot.send_message(
            chat_id,
            str(_(
                "Сиз сўровномани тўлиқ якунладингиз. Раҳмат!\n\n"
                "Сизнинг фикрингиз биз учун жуда муҳим.\n"
                "Иштирокингиз орқали муҳим ислоҳотлар ва қарорлар шакллантирилади.\n"
                "Янги сўровларда ҳам фаол иштирок этишингизни кутамиз!"
            ))
        )
        await state.clear()
        return

    if not respondent.history:
        await bot.send_message(
            chat_id,
            str(respondent.poll.description),
            parse_mode="Markdown"
        )

    updated_history = previous_questions + [question_id]
    respondent.history = updated_history
    await respondent.asave()

    await state.update_data(
        question_id=next_question.id,
        previous_questions=updated_history
    )
    await send_poll_question(bot, chat_id, state, respondent, next_question)


async def get_current_question(bot, chat_id, state: FSMContext, user, poll_uuid=None):
    active_polls = Poll.objects.filter(deadline__gte=timezone.now())
    if not await active_polls.aexists():
        await bot.send_message(chat_id, str(_("Ҳозирча актив сўровномалар мавжуд эмас.")))
        return

    if poll_uuid:
        poll = await Poll.objects.filter(uuid=poll_uuid, deadline__gte=timezone.now()).afirst()
        if not poll:
            await bot.send_message(chat_id, str(_("Кечирасиз, ушбу сўровнома топилмади ёки муддати тугаган.")))
            return
        available_polls = [poll]
    else:
        completed_respondents = Respondent.objects.filter(
            tg_user=user,
            poll=OuterRef('pk'),
            finished_at__isnull=False
        )
        available_polls = active_polls.annotate(
            has_completed=Exists(completed_respondents)
        ).filter(has_completed=False)

    if isinstance(available_polls, list):
        poll = available_polls[0]
    else:
        if not await available_polls.aexists():
            await bot.send_message(chat_id, str(_("Ҳозирча сиз учун янги сўровномалар мавжуд эмас.")))
            return
        poll = await available_polls.afirst()

    respondent = await Respondent.objects.filter(
        tg_user=user, poll=poll, finished_at__isnull=True
    ).afirst()

    if not respondent:
        respondent = await Respondent.objects.acreate(tg_user=user, poll=poll)

    unfinished_answer = await Answer.objects.filter(
        respondent=respondent,
        is_answered=False,
        telegram_msg_id__isnull=False
    ).select_related("question", "question__poll").order_by("id").afirst()

    if unfinished_answer:
        await state.update_data(respondent_id=respondent.id)
        await send_poll_question(
            bot, chat_id, state, respondent, unfinished_answer.question
        )
        return

    # ➕ Попробовать найти следующий неотвеченный вопрос
    questions = await sync_to_async(lambda: poll.questions.order_by("order"))()
    answered_ids = await sync_to_async(list)(
        Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    )
    next_question = await questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        await bot.send_message(chat_id, str(_("Сиз сўровномани тўлиқ якунладингиз. Рахмат!")))
        return

    # ✅ Запускаем первый вопрос
    await state.update_data(respondent_id=respondent.id)
    await get_next_question(bot, chat_id, state, respondent, respondent.history, next_question.id)


async def send_confirmation_text(bot, answer):
    # ✅ Подтверждение ответа + % выполнения
    total_questions = await sync_to_async(lambda: answer.respondent.poll.questions.count())()
    answered_count = await sync_to_async(
        lambda: Answer.objects.filter(respondent=answer.respondent, is_answered=True).count())()
    progress = int((answered_count / total_questions) * 100)
    # 🧾 Собираем текст ответа (один или несколько)
    if answer.question.type in (
            Question.QuestionTypeChoices.CLOSED_MULTIPLE,
            Question.QuestionTypeChoices.MIXED_MULTIPLE
    ):
        selected_choices = await sync_to_async(list)(answer.selected_choices.all())
        selected_text = "\n".join([f"• {choice.text}" for choice in selected_choices])
    else:
        selected_choices = await sync_to_async(list)(answer.selected_choices.all())
        selected_text = ""
        if answer.open_answer:
            selected_text += f"• {answer.open_answer}\n"
        if selected_choices:
            selected_text += f"• {selected_choices[0].text}"



    def render_progress_bar(progress: int, total_blocks: int = 10) -> str:
        filled_blocks = int((progress / 100) * total_blocks)
        empty_blocks = total_blocks - filled_blocks
        return "█" * filled_blocks + "░" * empty_blocks  # или ▓ и ░ для более мягкого стиля

    progress_bar = render_progress_bar(progress)

    # 💬 Формируем текст подтверждения
    confirmation_text = (
        f"<b>{answer.question.text}</b>\n\n"
        f"✅ Сиз танлаган жавоб(лар):\n{selected_text}\n\n"
        f"{progress_bar} <b>{progress}%</b>"
    )

    await bot.send_message(
        chat_id=answer.telegram_chat_id,
        text=confirmation_text,
        parse_mode="HTML"
    )

    try:
        await bot.delete_message(chat_id=answer.telegram_chat_id, message_id=answer.telegram_msg_id)
    except Exception as e:
        print(f"⚠️ Не удалось удалить poll: {e}")
