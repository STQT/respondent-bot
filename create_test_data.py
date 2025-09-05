#!/usr/bin/env python3
"""
Скрипт для создания тестовых данных для демонстрации системы уведомлений
"""

import os
import sys
import django

# Добавляем путь к проекту
sys.path.append('/Users/macbookpro/respondent-bot')

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from apps.polls.models import Poll, Question, Choice, Respondent
from apps.users.models import TGUser
from django.utils import timezone
import uuid

def create_test_data():
    print("🧪 Создание тестовых данных для системы уведомлений")
    print("=" * 60)
    
    # Создаем тестовых пользователей
    print("👥 Создание тестовых пользователей...")
    users_created = 0
    for i in range(1, 101):  # 100 пользователей
        user, created = TGUser.objects.get_or_create(
            id=1000000 + i,  # Уникальный ID
            defaults={
                'username': f'test_user_{i}',
                'fullname': f'Тестовый пользователь {i}',
                'is_active': True
            }
        )
        if created:
            users_created += 1
    
    print(f"✅ Создано пользователей: {users_created}")
    
    # Создаем тестовый опрос
    print("\n📊 Создание тестового опроса...")
    poll, created = Poll.objects.get_or_create(
        name="Демо тест для уведомлений",
        defaults={
            'description': 'Тестовый опрос для демонстрации системы уведомлений',
            'uuid': uuid.uuid4(),
            'deadline': timezone.now() + timezone.timedelta(days=30)  # Дедлайн через 30 дней
        }
    )
    
    if created:
        print(f"✅ Создан опрос: {poll.name}")
        
        # Создаем вопросы для опроса
        question1, _ = Question.objects.get_or_create(
            poll=poll,
            text="Какой ваш любимый цвет?",
            type='closed_single',
            order=1
        )
        
        # Создаем варианты ответов
        colors = ['Красный', 'Синий', 'Зеленый', 'Желтый']
        for i, color in enumerate(colors):
            Choice.objects.get_or_create(
                question=question1,
                text=color,
                order=i + 1
            )
        
        question2, _ = Question.objects.get_or_create(
            poll=poll,
            text="Сколько вам лет?",
            type='open',
            order=2
        )
        
        print(f"✅ Создано вопросов: {poll.questions.count()}")
    else:
        print(f"ℹ️ Опрос уже существует: {poll.name}")
    
    # Создаем записи о завершенных опросах (для некоторых пользователей)
    print("\n📝 Создание записей о завершенных опросах...")
    completed_count = 0
    for i in range(1, 31):  # 30 пользователей завершили опрос
        user = TGUser.objects.get(id=1000000 + i)
        respondent, created = Respondent.objects.get_or_create(
            poll=poll,
            tg_user=user,
            defaults={
                'finished_at': timezone.now(),
                'started_at': timezone.now() - timezone.timedelta(minutes=5)
            }
        )
        if created:
            completed_count += 1
    
    print(f"✅ Создано записей о завершенных опросах: {completed_count}")
    
    # Показываем статистику
    print("\n📊 Статистика:")
    print(f"   👥 Всего пользователей: {TGUser.objects.count()}")
    print(f"   📊 Всего опросов: {Poll.objects.count()}")
    print(f"   ✅ Завершили опрос: {Respondent.objects.filter(finished_at__isnull=False).count()}")
    print(f"   ⏳ Не завершили опрос: {TGUser.objects.count() - Respondent.objects.filter(finished_at__isnull=False).count()}")
    
    print("\n🎉 Тестовые данные созданы успешно!")
    print(f"💡 Теперь можете протестировать команду: python manage.py test_notifications --poll-id {poll.id}")

if __name__ == "__main__":
    create_test_data()
