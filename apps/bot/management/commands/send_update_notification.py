"""
Management команда для отправки уведомлений пользователям об обновлении бота.
Отправка происходит через Celery tasks с соблюдением лимитов Telegram Bot API.
"""

from django.core.management.base import BaseCommand
from apps.users.models import TGUser
from apps.polls.tasks import send_update_notification_task


class Command(BaseCommand):
    help = 'Отправить уведомление об обновлении всем активным пользователям'

    def add_arguments(self, parser):
        parser.add_argument(
            '--message',
            type=str,
            default=None,
            help='Текст сообщения для отправки (по умолчанию используется стандартное сообщение)'
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=100,
            help='Размер группы пользователей для одной задачи (по умолчанию 100)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать количество пользователей без отправки'
        )

    def handle(self, *args, **options):
        message = options.get('message')
        chunk_size = options.get('chunk_size', 100)
        dry_run = options.get('dry_run', False)
        
        # Получаем всех активных пользователей, которые не заблокировали бота
        active_users = TGUser.objects.filter(is_active=True, blocked_bot=False)
        total_users = active_users.count()
        
        if total_users == 0:
            self.stdout.write(self.style.WARNING('Нет активных пользователей для отправки'))
            return
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Будет отправлено {total_users} пользователям в '
                    f'{(total_users + chunk_size - 1) // chunk_size} группах по {chunk_size} пользователей'
                )
            )
            return
        
        # Разбиваем пользователей на группы
        user_ids = list(active_users.values_list('id', flat=True))
        user_chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Начинаю отправку уведомлений {total_users} пользователям...'
            )
        )
        
        # Запускаем задачи для каждой группы
        for i, chunk in enumerate(user_chunks):
            # Запускаем задачу с задержкой для последовательности
            send_update_notification_task.apply_async(
                args=[chunk, i, message],
                countdown=i * 2  # 2 секунды между запусками
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Запущена задача {i+1}/{len(user_chunks)} для {len(chunk)} пользователей'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nВсе задачи запущены! '
                f'Отправка {total_users} уведомлений в {len(user_chunks)} группах.'
            )
        )

