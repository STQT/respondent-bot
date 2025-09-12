from django.core.management.base import BaseCommand
from apps.polls.models import NotificationCampaign, Poll, Respondent
from apps.users.models import TGUser


class Command(BaseCommand):
    help = 'Тестирует работу с заблокированными пользователями в системе уведомлений'

    def add_arguments(self, parser):
        parser.add_argument(
            '--poll-id',
            type=int,
            help='ID опроса для тестирования',
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Создать тестовые данные (заблокированных пользователей)',
        )

    def handle(self, *args, **options):
        if options['create_test_data']:
            self.create_test_data()
            return

        poll_id = options.get('poll_id')
        if not poll_id:
            # Показываем доступные опросы
            polls = Poll.objects.all()
            if not polls.exists():
                self.stdout.write(
                    self.style.ERROR('Нет доступных опросов. Создайте опрос сначала.')
                )
                return

            self.stdout.write('Доступные опросы:')
            for poll in polls:
                self.stdout.write(f'  ID: {poll.id} - {poll.name}')
            
            poll_id = polls.first().id
            self.stdout.write(f'Используем опрос ID: {poll_id}')

        try:
            poll = Poll.objects.get(id=poll_id)
        except Poll.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Опрос с ID {poll_id} не найден')
            )
            return

        self.analyze_users(poll)

    def create_test_data(self):
        """Создает тестовые данные с заблокированными пользователями"""
        self.stdout.write('Создание тестовых данных...')
        
        # Создаем тестовых пользователей
        test_users = []
        for i in range(5):
            user, created = TGUser.objects.get_or_create(
                id=900000000 + i,
                defaults={
                    'fullname': f'Test User {i+1}',
                    'is_active': True,
                    'blocked_bot': i < 2,  # Первые 2 пользователя заблокированы
                }
            )
            test_users.append(user)
            if created:
                self.stdout.write(f'  Создан пользователь: {user.fullname} (ID: {user.id}, blocked: {user.blocked_bot})')
            else:
                self.stdout.write(f'  Пользователь уже существует: {user.fullname} (ID: {user.id}, blocked: {user.blocked_bot})')

        self.stdout.write(
            self.style.SUCCESS(f'Создано {len(test_users)} тестовых пользователей')
        )

    def analyze_users(self, poll):
        """Анализирует пользователей для данного опроса"""
        self.stdout.write(f'\nАнализ пользователей для опроса: {poll.name}')
        self.stdout.write('=' * 50)

        # Общая статистика пользователей
        total_users = TGUser.objects.filter(is_active=True).count()
        blocked_users = TGUser.objects.filter(is_active=True, blocked_bot=True).count()
        active_users = total_users - blocked_users

        self.stdout.write(f'Всего активных пользователей: {total_users}')
        self.stdout.write(f'  - Заблокировавших бота: {blocked_users}')
        self.stdout.write(f'  - Активных (не заблокировавших): {active_users}')

        # Пользователи, прошедшие опрос
        users_who_completed = Respondent.objects.filter(
            poll=poll,
            finished_at__isnull=False
        ).values_list('tg_user_id', flat=True).distinct()

        completed_count = users_who_completed.count()
        self.stdout.write(f'\nПользователи, прошедшие опрос: {completed_count}')

        # Пользователи для уведомления (исключая заблокированных)
        users_to_notify = TGUser.objects.filter(
            is_active=True,
            blocked_bot=False
        ).exclude(id__in=users_who_completed)

        notify_count = users_to_notify.count()
        self.stdout.write(f'Пользователи для уведомления: {notify_count}')

        # Заблокированные пользователи, которые не прошли опрос
        blocked_not_completed = TGUser.objects.filter(
            is_active=True,
            blocked_bot=True
        ).exclude(id__in=users_who_completed)

        blocked_not_completed_count = blocked_not_completed.count()
        self.stdout.write(f'Заблокированные, не прошедшие опрос: {blocked_not_completed_count}')

        # Детальная информация о заблокированных пользователях
        if blocked_not_completed_count > 0:
            self.stdout.write(f'\nДетали заблокированных пользователей:')
            for user in blocked_not_completed[:10]:  # Показываем первых 10
                self.stdout.write(f'  - {user.fullname} (ID: {user.id})')
            
            if blocked_not_completed_count > 10:
                self.stdout.write(f'  ... и еще {blocked_not_completed_count - 10} пользователей')

        # Рекомендации
        self.stdout.write(f'\nРекомендации:')
        if blocked_not_completed_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'  - {blocked_not_completed_count} пользователей заблокировали бота и не получат уведомления'
                )
            )
        
        if notify_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    '  - Нет пользователей для уведомления. Все пользователи либо прошли опрос, либо заблокировали бота.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'  - {notify_count} пользователей получат уведомления'
                )
            )

        # Тестируем создание кампании
        self.stdout.write(f'\nТестирование создания кампании...')
        try:
            campaign = NotificationCampaign.objects.create(
                topic=poll,
                status='pending'
            )
            self.stdout.write(f'  Создана кампания ID: {campaign.id}')
            self.stdout.write(f'  Пользователей для уведомления: {campaign.total_users}')
            
            # Удаляем тестовую кампанию
            campaign.delete()
            self.stdout.write('  Тестовая кампания удалена')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  Ошибка при создании кампании: {e}')
            )
