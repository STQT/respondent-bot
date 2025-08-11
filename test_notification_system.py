#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы уведомлений
"""

import os
import sys
import django

# Добавляем путь к проекту
sys.path.append('/Users/macbookpro/respondent-bot')

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from apps.polls.models import NotificationCampaign, Poll, Respondent
from apps.users.models import TGUser
from django.utils import timezone

def test_notification_logic():
    """Тестируем логику уведомлений"""
    
    print("🧪 Тестирование системы уведомлений")
    print("=" * 50)
    
    # Получаем первый опрос
    try:
        poll = Poll.objects.first()
        if not poll:
            print("❌ Нет доступных опросов")
            return
        
        print(f"📊 Опрос: {poll.name}")
        print(f"🔑 UUID: {poll.uuid}")
        
        # Создаем тестовую кампанию уведомлений
        campaign = NotificationCampaign.objects.create(
            topic=poll,
            total_users=0,
            status='pending'
        )
        
        print(f"✅ Создана кампания уведомлений: {campaign.id}")
        
        # Получаем пользователей, которые НЕ прошли опрос
        users_who_completed = Respondent.objects.filter(
            poll=poll,
            finished_at__isnull=False
        ).values_list('tg_user_id', flat=True).distinct()
        
        print(f"👥 Пользователи, завершившие опрос: {len(users_who_completed)}")
        
        # Получаем всех активных пользователей
        all_users = TGUser.objects.filter(is_active=True)
        users_to_notify = all_users.exclude(id__in=users_who_completed)
        
        print(f"📢 Пользователи для уведомления: {users_to_notify.count()}")
        
        # Обновляем количество пользователей в кампании
        campaign.total_users = users_to_notify.count()
        campaign.save()
        
        print(f"📈 Обновлено total_users: {campaign.total_users}")
        
        # Разбиваем на группы по 100
        user_ids = list(users_to_notify.values_list('id', flat=True))
        chunk_size = 100
        user_chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]
        
        print(f"📦 Создано групп: {len(user_chunks)}")
        for i, chunk in enumerate(user_chunks):
            print(f"   Группа {i}: {len(chunk)} пользователей")
        
        # Показываем примеры пользователей
        if users_to_notify.exists():
            print("\n👤 Примеры пользователей для уведомления:")
            for user in users_to_notify[:5]:
                print(f"   - {user.fullname} (ID: {user.id}, Username: {user.username or 'Нет'})")
        
        # Очищаем тестовую кампанию
        campaign.delete()
        print(f"\n🧹 Тестовая кампания удалена")
        
        print("\n✅ Тест завершен успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_notification_logic()
