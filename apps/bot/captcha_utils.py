"""
Утилиты для генерации и проверки капчи (антибот)
"""
import random
from typing import Tuple


def generate_math_captcha(lang='uz_cyrl') -> Tuple[str, str]:
    """
    Генерирует математическую капчу
    Возвращает (вопрос, правильный_ответ)
    """
    operations = [
        ('add', '+'),
        ('subtract', '-'),
        ('multiply', '×'),
    ]
    
    operation_type, symbol = random.choice(operations)
    
    if operation_type == 'add':
        a = random.randint(1, 50)
        b = random.randint(1, 50)
        answer = str(a + b)
    elif operation_type == 'subtract':
        a = random.randint(20, 100)
        b = random.randint(1, a - 1)
        answer = str(a - b)
    else:  # multiply
        a = random.randint(1, 12)
        b = random.randint(1, 12)
        answer = str(a * b)
    
    # Формируем вопрос на нужном языке
    texts = {
        'uz_cyrl': f"🤖 Антибот текшируви\n\nҲисобланг: {a} {symbol} {b} = ?\n\nИлтимос, жавобни киритинг:",
        'uz_latn': f"🤖 Antibot tekshiruvi\n\nHisoblang: {a} {symbol} {b} = ?\n\nIltimos, javobni kiriting:",
        'ru': f"🤖 Антибот проверка\n\nВычислите: {a} {symbol} {b} = ?\n\nПожалуйста, введите ответ:"
    }
    
    question = texts.get(lang, texts['uz_cyrl'])
    
    return question, answer


def generate_text_captcha(lang='uz_cyrl') -> Tuple[str, str]:
    """
    Генерирует текстовую капчу (повтор слова/числа)
    Возвращает (вопрос, правильный_ответ)
    """
    captcha_types = [
        'word',
        'number',
    ]
    
    captcha_type = random.choice(captcha_types)
    
    if captcha_type == 'word':
        words_uz_cyrl = ['китоб', 'қалам', 'дафтар', 'стол', 'курси', 'ойна', 'эшик', 'китоб']
        words_uz_latn = ['kitob', 'qalam', 'daftar', 'stol', 'kursi', 'oyna', 'eshik', 'kitob']
        words_ru = ['книга', 'ручка', 'тетрадь', 'стол', 'стул', 'окно', 'дверь', 'книга']
        
        if lang == 'uz_cyrl':
            word = random.choice(words_uz_cyrl)
            question = f"🤖 Антибот текшируви\n\nҚуйидаги сўзни қайта ёзинг:\n\n<code>{word}</code>"
        elif lang == 'uz_latn':
            word = random.choice(words_uz_latn)
            question = f"🤖 Antibot tekshiruvi\n\nQuyidagi so'zni qayta yozing:\n\n<code>{word}</code>"
        else:  # ru
            word = random.choice(words_ru)
            question = f"🤖 Антибот проверка\n\nПовторите следующее слово:\n\n<code>{word}</code>"
        
        answer = word
    else:  # number
        number = random.randint(1000, 9999)
        answer = str(number)
        
        if lang == 'uz_cyrl':
            question = f"🤖 Антибот текшируви\n\nҚуйидаги рақамни қайта ёзинг:\n\n<code>{number}</code>"
        elif lang == 'uz_latn':
            question = f"🤖 Antibot tekshiruvi\n\nQuyidagi raqamni qayta yozing:\n\n<code>{number}</code>"
        else:  # ru
            question = f"🤖 Антибот проверка\n\nПовторите следующее число:\n\n<code>{number}</code>"
    
    return question, answer


def should_show_captcha(answered_count: int) -> bool:
    """
    Определяет, нужно ли показать капчу
    Показываем капчу случайно, примерно каждые 3-5 вопросов
    """
    # Не показываем на первых 2 вопросах
    if answered_count < 2:
        return False
    
    # После 2 вопросов - случайная проверка (30% вероятность)
    # Или обязательно каждые 5 вопросов
    if answered_count % 5 == 0:
        return True
    
    return random.random() < 0.3


def get_captcha_error_message(lang='uz_cyrl', attempts=0) -> str:
    """Возвращает сообщение об ошибке капчи"""
    texts = {
        'uz_cyrl': f"❌ Нотўғри жавоб! Қайта уриниб кўринг.\n\nУринишлар: {attempts}/3",
        'uz_latn': f"❌ Noto'g'ri javob! Qayta urinib ko'ring.\n\nUrinishlar: {attempts}/3",
        'ru': f"❌ Неправильный ответ! Попробуйте снова.\n\nПопыток: {attempts}/3"
    }
    return texts.get(lang, texts['uz_cyrl'])


def get_captcha_failed_message(lang='uz_cyrl') -> str:
    """Возвращает сообщение о провале капчи"""
    texts = {
        'uz_cyrl': (
            "❌ Сиз 3 марта нотўғри жавоб бердингиз.\n\n"
            "Сўровнома тўхтатилди. Илтимос, бошқатдан уриниб кўринг."
        ),
        'uz_latn': (
            "❌ Siz 3 marta noto'g'ri javob berdingiz.\n\n"
            "So'rovnoma to'xtatildi. Iltimos, boshqatdan urinib ko'ring."
        ),
        'ru': (
            "❌ Вы ответили неправильно 3 раза.\n\n"
            "Опрос остановлен. Пожалуйста, попробуйте снова."
        )
    }
    return texts.get(lang, texts['uz_cyrl'])


def get_captcha_success_message(lang='uz_cyrl') -> str:
    """Возвращает сообщение об успешной капче"""
    texts = {
        'uz_cyrl': "✅ Тўғри! Сўровнома давом этади...",
        'uz_latn': "✅ To'g'ri! So'rovnoma davom etadi...",
        'ru': "✅ Правильно! Опрос продолжается..."
    }
    return texts.get(lang, texts['uz_cyrl'])

