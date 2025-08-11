from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.polls.models import NotificationCampaign, Poll, Respondent
from apps.users.models import TGUser


class Command(BaseCommand):
    help = 'Тестирование системы уведомлений'

    def add_arguments(self, parser):
        parser.add_argument(
            '--poll-id',
            type=int,
            help='ID опроса для тестирования (если не указан, берется первый)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать статистику, не создавать кампанию',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🧪 Тестирование системы уведомлений')
        )
        self.stdout.write('=' * 50)

        # Получаем опрос
        if options['poll_id']:
            try:
                poll = Poll.objects.get(id=options['poll_id'])
            except Poll.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ Опрос с ID {options["poll_id"]} не найден')
                )
                return
        else:
            poll = Poll.objects.first()
            if not poll:
                self.stdout.write(
                    self.style.ERROR('❌ Нет доступных опросов')
                )
                return

        self.stdout.write(f'📊 Опрос: {poll.name}')
        self.stdout.write(f'🔑 UUID: {poll.uuid}')

        # Получаем пользователей, которые НЕ прошли опрос
        users_who_completed = Respondent.objects.filter(
            poll=poll,
            finished_at__isnull=False
        ).values_list('tg_user_id', flat=True).distinct()

        self.stdout.write(f'👥 Пользователи, завершившие опрос: {len(users_who_completed)}')

        # Получаем всех активных пользователей
        all_users = TGUser.objects.filter(is_active=True)
        users_to_notify = all_users.exclude(id__in=users_who_completed)

        self.stdout.write(f'📢 Пользователи для уведомления: {users_to_notify.count()}')

        if users_to_notify.count() == 0:
            self.stdout.write(
                self.style.WARNING('⚠️ Нет пользователей для уведомления')
            )
            return

        # Разбиваем на группы по 100
        user_ids = list(users_to_notify.values_list('id', flat=True))
        chunk_size = 100
        user_chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]

        self.stdout.write(f'📦 Создано групп: {len(user_chunks)}')
        for i, chunk in enumerate(user_chunks):
            self.stdout.write(f'   Группа {i}: {len(chunk)} пользователей')

        # Показываем примеры пользователей
        self.stdout.write('\n👤 Примеры пользователей для уведомления:')
        for user in users_to_notify[:5]:
            self.stdout.write(f'   - {user.fullname} (ID: {user.id}, TG: {user.telegram_id})')

        if not options['dry_run']:
            # Создаем тестовую кампанию
            campaign = NotificationCampaign.objects.create(
                topic=poll,
                total_users=users_to_notify.count(),
                status='pending'
            )

            self.stdout.write(f'\n✅ Создана кампания уведомлений: {campaign.id}')
            self.stdout.write(
                self.style.SUCCESS('💡 Теперь можете запустить кампанию через админку Django')
            )

            # Очищаем тестовую кампанию
            campaign.delete()
            self.stdout.write('🧹 Тестовая кампания удалена')

        self.stdout.write(
            self.style.SUCCESS('\n✅ Тест завершен успешно!')
        )
