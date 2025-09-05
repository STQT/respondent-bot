from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.polls.models import BroadcastPost
from apps.users.models import TGUser


class Command(BaseCommand):
    help = 'Тестирование системы массовой рассылки'

    def add_arguments(self, parser):
        parser.add_argument(
            '--title',
            type=str,
            default='Тестовый пост',
            help='Заголовок поста',
        )
        parser.add_argument(
            '--content',
            type=str,
            default='Это тестовый пост для проверки системы рассылки.',
            help='Содержание поста',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать статистику, не создавать пост',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('📢 Тестирование системы массовой рассылки')
        )
        self.stdout.write('=' * 50)

        # Получаем статистику пользователей
        all_users = TGUser.objects.filter(is_active=True)
        total_users = all_users.count()

        self.stdout.write(f'👥 Всего активных пользователей: {total_users}')

        if total_users == 0:
            self.stdout.write(
                self.style.WARNING('⚠️ Нет активных пользователей для рассылки')
            )
            return

        # Разбиваем на группы по 100
        user_ids = list(all_users.values_list('id', flat=True))
        chunk_size = 100
        user_chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]

        self.stdout.write(f'📦 Создано групп: {len(user_chunks)}')
        for i, chunk in enumerate(user_chunks):
            self.stdout.write(f'   Группа {i}: {len(chunk)} пользователей')

        # Показываем примеры пользователей
        self.stdout.write('\n👤 Примеры пользователей для рассылки:')
        for user in all_users[:5]:
            self.stdout.write(f'   - {user.fullname} (TG: {user.id})')

        if not options['dry_run']:
            # Создаем тестовый пост
            broadcast = BroadcastPost.objects.create(
                title=options['title'],
                content=options['content'],
                status='draft'
            )

            self.stdout.write(f'\n✅ Создан пост: {broadcast.id}')
            self.stdout.write(f'   Заголовок: {broadcast.title}')
            self.stdout.write(f'   Содержание: {broadcast.content[:50]}...')
            self.stdout.write(
                self.style.SUCCESS('💡 Теперь можете запустить рассылку через админку Django')
            )

            # Очищаем тестовый пост
            broadcast.delete()
            self.stdout.write('🧹 Тестовый пост удален')

        self.stdout.write(
            self.style.SUCCESS('\n✅ Тест завершен успешно!')
        )
