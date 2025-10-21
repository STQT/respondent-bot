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
    # Получаем язык пользователя
    user = await sync_to_async(lambda: respondent.tg_user)()
    user_lang = user.lang if hasattr(user, 'lang') else 'uz_cyrl'
    
    choices = await sync_to_async(list)(question.choices.all().order_by("order"))
    allows_multiple_answers = question.type in (
        Question.QuestionTypeChoices.CLOSED_MULTIPLE,
        Question.QuestionTypeChoices.MIXED_MULTIPLE
    )
    
    # Получаем текст вопроса на языке пользователя
    question_text = await sync_to_async(question.get_text)(user_lang)

    # 💬 Открытый или смешанный вопрос — отправим текст
    if question.type == Question.QuestionTypeChoices.OPEN:
        prompt_texts = {
            'uz_cyrl': f"📨 {question_text}\n\nИлтимос, жавобингизни матн сифатида юборинг ✍️",
            'uz_latn': f"📨 {question_text}\n\nIltimos, javobingizni matn sifatida yuboring ✍️",
            'ru': f"📨 {question_text}\n\nПожалуйста, отправьте ваш ответ текстом ✍️"
        }
        prompt = prompt_texts.get(user_lang, prompt_texts['uz_cyrl'])
        
        await bot.send_message(chat_id, prompt)

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
    # Получаем тексты вариантов на языке пользователя
    options = []
    for choice in choices:
        choice_text = await sync_to_async(choice.get_text)(user_lang)
        options.append(choice_text)
    
    if question.type in [
        Question.QuestionTypeChoices.MIXED,
        Question.QuestionTypeChoices.MIXED_MULTIPLE
    ]:
        # Текст "Бошқа" на разных языках
        another_texts = {
            'uz_cyrl': str(_("Бошқа(ёзинг)__________")),
            'uz_latn': "Boshqa (yozing)__________",
            'ru': "Другое (напишите)__________"
        }
        options.append(another_texts.get(user_lang, str(ANOTHER_STR)))

    if await poll_checker(bot, chat_id, question, options) is True:
        poll_message = await bot.send_poll(
            chat_id=chat_id,
            question=question_text,  # Используем уже полученный текст на нужном языке
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
    from apps.bot.captcha_utils import should_show_captcha, generate_math_captcha, generate_text_captcha
    from apps.polls.models import CaptchaChallenge, Answer
    from datetime import timedelta
    import random
    
    # Проверяем, нужна ли капча
    answered_count = await sync_to_async(
        Answer.objects.filter(respondent=respondent, is_answered=True).count
    )()
    
    user = await sync_to_async(lambda: respondent.tg_user)()
    
    # Проверяем, была ли капча показана недавно (в последние 30 секунд)
    recent_captcha = await sync_to_async(
        CaptchaChallenge.objects.filter(
            respondent=respondent,
            created_at__gte=timezone.now() - timedelta(seconds=30)
        ).exists
    )()
    
    # Показываем капчу только если:
    # 1. Настало время (по answered_count)
    # 2. И не было капчи в последние 30 секунд
    if should_show_captcha(answered_count) and not recent_captcha:
        # Генерируем капчу
        captcha_type = random.choice(['math', 'text'])
        
        if captcha_type == 'math':
            question_text, correct_answer = generate_math_captcha(user.lang)
        else:
            question_text, correct_answer = generate_text_captcha(user.lang)
        
        # Сохраняем капчу в базу
        captcha = await sync_to_async(CaptchaChallenge.objects.create)(
            respondent=respondent,
            captcha_type=captcha_type,
            question=question_text,
            correct_answer=correct_answer
        )
        
        # Отправляем капчу пользователю
        await bot.send_message(chat_id, question_text, parse_mode="HTML")
        
        # Устанавливаем состояние ожидания капчи
        await state.set_state(PollStates.waiting_for_captcha)
        await state.update_data(
            captcha_id=captcha.id,
            respondent_id=respondent.id,
            previous_questions=previous_questions,
            question_id=question_id
        )
        return
    
    all_questions = await sync_to_async(lambda: respondent.poll.questions.order_by("order"))()
    answered_ids = await sync_to_async(list)(
        Answer.objects.filter(respondent=respondent).values_list('question_id', flat=True)
    )
    next_question = await all_questions.exclude(id__in=answered_ids).afirst()

    if not next_question:
        respondent.finished_at = timezone.now()
        await respondent.asave()
        
        # Начисляем вознаграждение за прохождение опроса
        poll = await sync_to_async(lambda: respondent.poll)()
        user = await sync_to_async(lambda: respondent.tg_user)()
        
        if poll.reward > 0:
            # Начисляем деньги на баланс
            user.balance += poll.reward
            await sync_to_async(user.save)()
            
            # Создаем транзакцию
            from apps.users.models import TransactionHistory
            await sync_to_async(TransactionHistory.objects.create)(
                user=user,
                transaction_type='earned',
                amount=poll.reward,
                description=f'Вознаграждение за прохождение опроса "{poll.name}"',
                related_poll=poll
            )
            
            completion_message = str(_(
                "Сиз сўровномани тўлиқ якунладингиз. Раҳмат!\n\n"
                "💰 Сизга {reward} сўм ҳисобингизга қўшилди!\n\n"
                "Сизнинг фикрингиз биз учун жуда муҳим.\n"
                "Иштирокингиз орқали муҳим ислоҳотлар ва қарорлар шакллантирилади.\n"
                "Янги сўровларда ҳам фаол иштирок этишингизни кутамиз!"
            )).format(reward=poll.reward)
        else:
            completion_message = str(_(
                "Сиз сўровномани тўлиқ якунладингиз. Раҳмат!\n\n"
                "Сизнинг фикрингиз биз учун жуда муҳим.\n"
                "Иштирокингиз орқали муҳим ислоҳотлар ва қарорлар шакллантирилади.\n"
                "Янги сўровларда ҳам фаол иштирок этишингизни кутамиз!"
            ))
        
        await bot.send_message(chat_id, completion_message)
        await state.clear()
        return

    if not respondent.history:
        # Получаем описание на языке пользователя
        user = await sync_to_async(lambda: respondent.tg_user)()
        user_lang = user.lang if hasattr(user, 'lang') else 'uz_cyrl'
        poll = await sync_to_async(lambda: respondent.poll)()
        description = await sync_to_async(poll.get_description)(user_lang)
        
        await bot.send_message(
            chat_id,
            description,
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


async def send_confirmation_text(bot, answer, open_answer=None):
    if not answer.telegram_chat_id:
        print(f"❌ Ошибка: telegram_chat_id отсутствует для Answer ID={answer.id}")
        return
    
    # Получаем язык пользователя
    respondent = await sync_to_async(lambda: answer.respondent)()
    user = await sync_to_async(lambda: respondent.tg_user)()
    user_lang = user.lang if hasattr(user, 'lang') else 'uz_cyrl'
    
    # ✅ Подтверждение ответа + % выполнения
    total_questions = await sync_to_async(lambda: answer.respondent.poll.questions.count())()
    answered_count = await sync_to_async(
        lambda: Answer.objects.filter(respondent=answer.respondent, is_answered=True).count())()
    progress = int((answered_count / total_questions) * 100)
    
    # 🧾 Собираем текст ответа (один или несколько)
    question = await sync_to_async(lambda: answer.question)()
    question_text = await sync_to_async(question.get_text)(user_lang)
    
    if question.type in (
            Question.QuestionTypeChoices.CLOSED_MULTIPLE,
            Question.QuestionTypeChoices.MIXED_MULTIPLE
    ):
        selected_choices = await sync_to_async(list)(answer.selected_choices.all())
        selected_texts = []
        for choice in selected_choices:
            choice_text = await sync_to_async(choice.get_text)(user_lang)
            selected_texts.append(f"• {choice_text}")
        selected_text = "\n".join(selected_texts)
    else:
        selected_choices = await sync_to_async(list)(answer.selected_choices.all())
        selected_text = ""
        if selected_choices:
            choice_text = await sync_to_async(selected_choices[0].get_text)(user_lang)
            selected_text += f"\n• {choice_text}"

    if open_answer:
        selected_text += f"\n• {open_answer}\n"

    def render_progress_bar(progress: int, total_blocks: int = 10) -> str:
        filled_blocks = int((progress / 100) * total_blocks)
        empty_blocks = total_blocks - filled_blocks
        return "█" * filled_blocks + "░" * empty_blocks

    progress_bar = render_progress_bar(progress)

    # Тексты подтверждения на разных языках
    confirmation_labels = {
        'uz_cyrl': f"✅ Сиз танлаган жавоб(лар):\n{selected_text}\n\nБитирганлилиги:",
        'uz_latn': f"✅ Siz tanlagan javob(lar):\n{selected_text}\n\nTamomlanganligi:",
        'ru': f"✅ Вы выбрали:\n{selected_text}\n\nПрогресс:"
    }
    
    confirmation_label = confirmation_labels.get(user_lang, confirmation_labels['uz_cyrl'])

    # 💬 Формируем текст подтверждения
    confirmation_text = (
        f"<b>{question_text}</b>\n\n"
        f"{confirmation_label} \n"
        f"{progress_bar} <b>{progress}%</b>"
    )

    await bot.send_message(
        chat_id=answer.telegram_chat_id,
        text=confirmation_text,
        parse_mode="HTML"
    )

    try:
        if answer.telegram_msg_id is not None:
            await bot.delete_message(chat_id=answer.telegram_chat_id, message_id=answer.telegram_msg_id)
    except Exception as e:
        print(f"⚠️ Не удалось удалить poll: {e}")
