from decimal import Decimal
from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.db.models import Q

from apps.bot.states import PollStates, WithdrawalStates
from apps.users.models import TGUser, WithdrawalRequest, TransactionHistory, LanguageChoices
from apps.polls.models import Poll, Respondent


menu_router = Router()


def get_main_menu_keyboard(lang='uz_cyrl'):
    """Возвращает главное меню бота в зависимости от языка"""
    texts = {
        'uz_cyrl': {
            'balance': '💰 Баланс',
            'language': '🌐 Тилни ўзгартириш',
            'active_polls': '📊 Актив сўровномалар',
            'completed_polls': '✅ Якунланган сўровномалар',
            'withdrawal_history': '📜 Чиқариш тарихи'
        },
        'uz_latn': {
            'balance': "💰 Balans",
            'language': "🌐 Tilni o'zgartirish",
            'active_polls': "📊 Aktiv so'rovnomalar",
            'completed_polls': "✅ Yakunlangan so'rovnomalar",
            'withdrawal_history': "📜 Chiqarish tarixi"
        },
        'ru': {
            'balance': '💰 Баланс',
            'language': '🌐 Изменить язык',
            'active_polls': '📊 Активные опросы',
            'completed_polls': '✅ Пройденные опросы',
            'withdrawal_history': '📜 История выводов'
        }
    }
    
    text = texts.get(lang, texts['uz_cyrl'])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text['balance'])],
            [KeyboardButton(text=text['language'])],
            [KeyboardButton(text=text['active_polls'])],
            [KeyboardButton(text=text['completed_polls'])],
            [KeyboardButton(text=text['withdrawal_history'])]
        ],
        resize_keyboard=True
    )
    
    return keyboard


def get_text(key, lang='uz_cyrl'):
    """Получить текст на нужном языке"""
    texts = {
        'balance_info': {
            'uz_cyrl': '💰 Сизнинг балансингиз: {balance} сўм\n\nСиз сўровномаларни тўлдириш орқали пул ишлаб топишингиз мумкин.',
            'uz_latn': "💰 Sizning balansigiz: {balance} so'm\n\nSiz so'rovnomalarni to'ldirish orqali pul ishlab topishingiz mumkin.",
            'ru': '💰 Ваш баланс: {balance} сум\n\nВы можете зарабатывать деньги, заполняя опросы.'
        },
        'withdraw_button': {
            'uz_cyrl': '💳 Пулни чиқариш',
            'uz_latn': "💳 Pulni chiqarish",
            'ru': '💳 Вывести деньги'
        },
        'language_select': {
            'uz_cyrl': '🌐 Тилни танланг:',
            'uz_latn': "🌐 Tilni tanlang:",
            'ru': '🌐 Выберите язык:'
        },
        'language_changed': {
            'uz_cyrl': '✅ Тил муваффақиятли ўзгартирилди!',
            'uz_latn': "✅ Til muvaffaqiyatli o'zgartirildi!",
            'ru': '✅ Язык успешно изменен!'
        },
        'active_polls_title': {
            'uz_cyrl': '📊 Актив сўровномалар:\n\n',
            'uz_latn': "📊 Aktiv so'rovnomalar:\n\n",
            'ru': '📊 Активные опросы:\n\n'
        },
        'no_active_polls': {
            'uz_cyrl': 'Ҳозирча актив сўровномалар йўқ.',
            'uz_latn': "Hozircha aktiv so'rovnomalar yo'q.",
            'ru': 'В данный момент нет активных опросов.'
        },
        'poll_reward': {
            'uz_cyrl': '💰 Мукофот: {reward} сўм',
            'uz_latn': "💰 Mukofot: {reward} so'm",
            'ru': '💰 Вознаграждение: {reward} сум'
        },
        'start_poll': {
            'uz_cyrl': '▶️ Бошлаш',
            'uz_latn': "▶️ Boshlash",
            'ru': '▶️ Начать'
        },
        'completed_polls_title': {
            'uz_cyrl': '✅ Сиз якунлаган сўровномалар:\n\n',
            'uz_latn': "✅ Siz yakunlagan so'rovnomalar:\n\n",
            'ru': '✅ Вы завершили опросы:\n\n'
        },
        'no_completed_polls': {
            'uz_cyrl': 'Сиз ҳали ҳеч бир сўровномани якунламагансиз.',
            'uz_latn': "Siz hali hech bir so'rovnomani yakunlamagansiz.",
            'ru': 'Вы еще не завершили ни одного опроса.'
        },
        'earned': {
            'uz_cyrl': '✅ Ишлаб топилди: {amount} сўм',
            'uz_latn': "✅ Ishlab topildi: {amount} so'm",
            'ru': '✅ Заработано: {amount} сум'
        },
        'withdrawal_history_title': {
            'uz_cyrl': '📜 Чиқариш тарихи:\n\n',
            'uz_latn': "📜 Chiqarish tarixi:\n\n",
            'ru': '📜 История выводов:\n\n'
        },
        'no_withdrawal_history': {
            'uz_cyrl': 'Сизда ҳали чиқариш тарихи йўқ.',
            'uz_latn': "Sizda hali chiqarish tarixi yo'q.",
            'ru': 'У вас пока нет истории выводов.'
        },
        'withdrawal_status': {
            'uz_cyrl': {
                'pending': '⏳ Кутилмоқда',
                'approved': '✅ Тасдиқланди',
                'rejected': '❌ Рад этилди',
                'completed': '✅ Бажарилди'
            },
            'uz_latn': {
                'pending': "⏳ Kutilmoqda",
                'approved': "✅ Tasdiqlandi",
                'rejected': "❌ Rad etildi",
                'completed': "✅ Bajarildi"
            },
            'ru': {
                'pending': '⏳ В ожидании',
                'approved': '✅ Одобрено',
                'rejected': '❌ Отклонено',
                'completed': '✅ Выполнено'
            }
        },
        'enter_amount': {
            'uz_cyrl': '💳 Чиқариш учун суммани киритинг (минимум 10000 сўм):',
            'uz_latn': "💳 Chiqarish uchun summani kiriting (minimum 10000 so'm):",
            'ru': '💳 Введите сумму для вывода (минимум 10000 сум):'
        },
        'enter_payment_details': {
            'uz_cyrl': '💳 Тўлов маълумотларини киритинг (карта рақами ёки телефон):',
            'uz_latn': "💳 To'lov ma'lumotlarini kiriting (karta raqami yoki telefon):",
            'ru': '💳 Введите платежные данные (номер карты или телефон):'
        },
        'withdrawal_created': {
            'uz_cyrl': '✅ Чиқариш сўрови яратилди!\n\nАдминистратор кўриб чиқишини кутинг.',
            'uz_latn': "✅ Chiqarish so'rovi yaratildi!\n\nAdministrator ko'rib chiqishini kuting.",
            'ru': '✅ Запрос на вывод создан!\n\nОжидайте проверки администратора.'
        },
        'insufficient_balance': {
            'uz_cyrl': '❌ Балансингизда етарли маблағ йўқ.',
            'uz_latn': "❌ Balansingizda yetarli mablag' yo'q.",
            'ru': '❌ Недостаточно средств на балансе.'
        },
        'invalid_amount': {
            'uz_cyrl': '❌ Нотўғри сумма. Илтимос, рақам киритинг.',
            'uz_latn': "❌ Noto'g'ri summa. Iltimos, raqam kiriting.",
            'ru': '❌ Неверная сумма. Пожалуйста, введите число.'
        },
        'minimum_amount': {
            'uz_cyrl': '❌ Минимал чиқариш суммаси 10000 сўм.',
            'uz_latn': "❌ Minimal chiqarish summasi 10000 so'm.",
            'ru': '❌ Минимальная сумма вывода 10000 сум.'
        },
        'cancel': {
            'uz_cyrl': '❌ Бекор қилиш',
            'uz_latn': "❌ Bekor qilish",
            'ru': '❌ Отмена'
        },
        'cancelled': {
            'uz_cyrl': '❌ Операция бекор қилинди.',
            'uz_latn': "❌ Operatsiya bekor qilindi.",
            'ru': '❌ Операция отменена.'
        }
    }
    
    text_dict = texts.get(key, {})
    return text_dict.get(lang, text_dict.get('uz_cyrl', ''))


@menu_router.message(Command("menu"))
async def show_menu(message: Message, user: TGUser | None):
    """Показать главное меню"""
    if not user:
        return
    
    await message.answer(
        "Меню:",
        reply_markup=get_main_menu_keyboard(user.lang)
    )


@menu_router.message(lambda message: message.text and any(x in message.text for x in ['💰 Баланс', '💰 Balans']))
async def show_balance(message: Message, user: TGUser | None):
    """Показать баланс пользователя"""
    if not user:
        return
    
    await message.bot.send_chat_action(message.from_user.id, action=ChatAction.TYPING)
    
    # Получаем баланс пользователя
    balance = user.balance
    
    # Формируем текст
    text = get_text('balance_info', user.lang).format(balance=balance)
    
    # Создаем инлайн кнопку для вывода денег
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text('withdraw_button', user.lang),
            callback_data='withdraw_money'
        )]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@menu_router.callback_query(lambda c: c.data == 'withdraw_money')
async def initiate_withdrawal(callback: CallbackQuery, state: FSMContext, user: TGUser | None):
    """Начать процесс вывода средств"""
    if not user:
        return
    
    await callback.answer()
    
    # Проверяем минимальный баланс
    if user.balance < 10000:
        await callback.message.answer(
            get_text('insufficient_balance', user.lang)
        )
        return
    
    # Запрашиваем сумму
    await callback.message.answer(
        get_text('enter_amount', user.lang)
    )
    await state.set_state(WithdrawalStates.waiting_for_amount)


@menu_router.message(WithdrawalStates.waiting_for_amount)
async def process_withdrawal_amount(message: Message, state: FSMContext, user: TGUser | None):
    """Обработка введенной суммы для вывода"""
    if not user:
        return
    
    # Проверяем на отмену
    if message.text and any(x in message.text for x in ['❌ Бекор қилиш', "❌ Bekor qilish", '❌ Отмена']):
        await state.clear()
        await message.answer(
            get_text('cancelled', user.lang),
            reply_markup=get_main_menu_keyboard(user.lang)
        )
        return
    
    try:
        amount = Decimal(message.text.strip())
    except:
        await message.answer(get_text('invalid_amount', user.lang))
        return
    
    # Проверяем минимальную сумму
    if amount < 10000:
        await message.answer(get_text('minimum_amount', user.lang))
        return
    
    # Проверяем достаточность баланса
    if amount > user.balance:
        await message.answer(get_text('insufficient_balance', user.lang))
        return
    
    # Сохраняем сумму в состоянии
    await state.update_data(amount=amount)
    
    # Запрашиваем платежные данные
    await message.answer(get_text('enter_payment_details', user.lang))
    await state.set_state(WithdrawalStates.waiting_for_payment_details)


@menu_router.message(WithdrawalStates.waiting_for_payment_details)
async def process_payment_details(message: Message, state: FSMContext, user: TGUser | None):
    """Обработка платежных данных"""
    if not user:
        return
    
    # Проверяем на отмену
    if message.text and any(x in message.text for x in ['❌ Бекор қилиш', "❌ Bekor qilish", '❌ Отмена']):
        await state.clear()
        await message.answer(
            get_text('cancelled', user.lang),
            reply_markup=get_main_menu_keyboard(user.lang)
        )
        return
    
    payment_details = message.text.strip()
    
    # Получаем сумму из состояния
    data = await state.get_data()
    amount = data.get('amount')
    
    # Создаем запрос на вывод
    withdrawal = await sync_to_async(WithdrawalRequest.objects.create)(
        user=user,
        amount=amount,
        payment_details=payment_details,
        status='pending'
    )
    
    # Списываем с баланса (резервируем)
    user.balance -= amount
    await sync_to_async(user.save)()
    
    # Очищаем состояние
    await state.clear()
    
    # Уведомляем пользователя
    await message.answer(
        get_text('withdrawal_created', user.lang),
        reply_markup=get_main_menu_keyboard(user.lang)
    )


@menu_router.message(lambda message: message.text and any(x in message.text for x in ['🌐 Тилни ўзгартириш', "🌐 Tilni o'zgartirish", '🌐 Изменить язык']))
async def change_language(message: Message, user: TGUser | None):
    """Изменить язык"""
    if not user:
        return
    
    # Создаем инлайн кнопки для выбора языка
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Ўзбекча (кириллица)', callback_data='lang_uz_cyrl')],
        [InlineKeyboardButton(text="O'zbekcha (lotin)", callback_data='lang_uz_latn')],
        [InlineKeyboardButton(text='Русский', callback_data='lang_ru')]
    ])
    
    await message.answer(
        get_text('language_select', user.lang),
        reply_markup=keyboard
    )


@menu_router.callback_query(lambda c: c.data.startswith('lang_'))
async def process_language_change(callback: CallbackQuery, user: TGUser | None):
    """Обработка изменения языка"""
    if not user:
        return
    
    lang = callback.data.replace('lang_', '')
    
    # Обновляем язык пользователя
    user.lang = lang
    await sync_to_async(user.save)()
    
    await callback.answer()
    await callback.message.edit_text(get_text('language_changed', lang))
    
    # Показываем обновленное меню
    await callback.message.answer(
        "Меню:",
        reply_markup=get_main_menu_keyboard(lang)
    )


@menu_router.message(lambda message: message.text and any(x in message.text for x in ['📊 Актив сўровномалар', "📊 Aktiv so'rovnomalar", '📊 Активные опросы']))
async def show_active_polls(message: Message, user: TGUser | None):
    """Показать активные опросы"""
    if not user:
        return
    
    await message.bot.send_chat_action(message.from_user.id, action=ChatAction.TYPING)
    
    # Получаем активные опросы
    active_polls = await sync_to_async(list)(
        Poll.objects.filter(deadline__gte=timezone.now())
    )
    
    if not active_polls:
        await message.answer(get_text('no_active_polls', user.lang))
        return
    
    text = get_text('active_polls_title', user.lang)
    
    keyboard_buttons = []
    for poll in active_polls:
        # Проверяем, прошел ли пользователь этот опрос
        completed = await sync_to_async(
            Respondent.objects.filter(
                tg_user=user,
                poll=poll,
                finished_at__isnull=False
            ).exists
        )()
        
        status = '✅ ' if completed else '▶️ '
        poll_text = f"{status}{poll.name}\n"
        poll_text += get_text('poll_reward', user.lang).format(reward=poll.reward)
        
        text += f"\n{poll_text}\n"
        
        if not completed:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{poll.name}",
                    callback_data=f"start_poll:{poll.uuid}"
                )
            ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None
    
    await message.answer(text, reply_markup=keyboard)


@menu_router.callback_query(lambda c: c.data.startswith('start_poll:'))
async def start_poll_from_menu(callback: CallbackQuery, state: FSMContext, user: TGUser | None):
    """Начать опрос из меню"""
    if not user:
        return
    
    from apps.bot.utils import get_current_question
    
    poll_uuid = callback.data.replace('start_poll:', '')
    
    await callback.answer()
    await callback.message.delete()
    
    # Запускаем опрос
    await get_current_question(callback.bot, callback.from_user.id, state, user, poll_uuid=poll_uuid)


@menu_router.message(lambda message: message.text and any(x in message.text for x in ['✅ Якунланган сўровномалар', "✅ Yakunlangan so'rovnomalar", '✅ Пройденные опросы']))
async def show_completed_polls(message: Message, user: TGUser | None):
    """Показать завершенные опросы"""
    if not user:
        return
    
    await message.bot.send_chat_action(message.from_user.id, action=ChatAction.TYPING)
    
    # Получаем завершенные опросы пользователя
    completed_respondents = await sync_to_async(list)(
        Respondent.objects.filter(
            tg_user=user,
            finished_at__isnull=False
        ).select_related('poll').order_by('-finished_at')
    )
    
    if not completed_respondents:
        await message.answer(get_text('no_completed_polls', user.lang))
        return
    
    text = get_text('completed_polls_title', user.lang)
    
    for resp in completed_respondents:
        poll = resp.poll
        finished_date = resp.finished_at.strftime('%d.%m.%Y %H:%M')
        text += f"\n📊 {poll.name}\n"
        text += f"📅 {finished_date}\n"
        if poll.reward > 0:
            text += get_text('earned', user.lang).format(amount=poll.reward) + "\n"
    
    await message.answer(text)


@menu_router.message(lambda message: message.text and any(x in message.text for x in ['📜 Чиқариш тарихи', "📜 Chiqarish tarixi", '📜 История выводов']))
async def show_withdrawal_history(message: Message, user: TGUser | None):
    """Показать историю выводов"""
    if not user:
        return
    
    await message.bot.send_chat_action(message.from_user.id, action=ChatAction.TYPING)
    
    # Получаем историю выводов
    withdrawals = await sync_to_async(list)(
        WithdrawalRequest.objects.filter(user=user).order_by('-created_at')
    )
    
    if not withdrawals:
        await message.answer(get_text('no_withdrawal_history', user.lang))
        return
    
    text = get_text('withdrawal_history_title', user.lang)
    
    status_texts = get_text('withdrawal_status', user.lang)
    
    for withdrawal in withdrawals:
        created_date = withdrawal.created_at.strftime('%d.%m.%Y %H:%M')
        status = status_texts.get(withdrawal.status, withdrawal.status)
        
        text += f"\n💳 {withdrawal.amount} сўм\n"
        text += f"📅 {created_date}\n"
        text += f"{status}\n"
    
    await message.answer(text)

