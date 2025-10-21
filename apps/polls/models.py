import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import TextChoices
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import os

from apps.users.models import TGUser


class Poll(models.Model):
    name = models.CharField(max_length=255)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    description = models.TextField()
    deadline = models.DateTimeField()
    reward = models.DecimalField(
        verbose_name=_("Вознаграждение"),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_("Сумма вознаграждения за прохождение опроса")
    )

    def is_active(self):
        return timezone.now() <= self.deadline

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Тема")
        verbose_name_plural = _("Темы")


class Question(models.Model):
    class QuestionTypeChoices(TextChoices):
        CLOSED_SINGLE = "closed_single", _("Закрытый — один ответ")
        CLOSED_MULTIPLE = "closed_multiple", _("Закрытый — несколько ответов")
        OPEN = "open", _("Открытый")
        MIXED = "mixed", _("Смешанный")
        MIXED_MULTIPLE = "mixed_multiple", _("Смешанный — несколько ответов")

    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    type = models.CharField(max_length=20, choices=QuestionTypeChoices.choices)
    max_choices = models.PositiveIntegerField(null=True, blank=True, help_text='Только для closed_multiple')

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text

    class Meta:
        verbose_name = _("Вопрос")
        verbose_name_plural = _("Вопросы")


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.order}. {self.text}"

    class Meta:
        verbose_name = _("Выбор")
        verbose_name_plural = _("Выборки")


class Respondent(models.Model):
    tg_user = models.ForeignKey(TGUser, on_delete=models.CASCADE, related_name='respondents')
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='respondents')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    history = ArrayField(models.IntegerField(), default=list, blank=True)

    def is_completed(self):
        return self.finished_at is not None

    def __str__(self):
        return f"Респондент: {self.tg_user.id} | TG: {self.tg_user.fullname}"

    class Meta:
        verbose_name = _("Респондент")
        verbose_name_plural = _("Респонденты")


class Answer(models.Model):
    respondent = models.ForeignKey(Respondent, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(Choice, blank=True)
    open_answer = models.TextField(blank=True)
    is_answered = models.BooleanField(default=False)
    telegram_poll_id = models.CharField(max_length=255, null=True, blank=True)
    telegram_msg_id = models.CharField(max_length=255, null=True, blank=True)
    telegram_chat_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'Ответ на "{self.question.text}" от пользователя {self.respondent.tg_user_id}'

    class Meta:
        verbose_name = _("Ответ")
        verbose_name_plural = _("Ответы")


def export_file_path(instance, filename):
    """Генерирует путь для файла экспорта"""
    return f'exports/{instance.created_at.strftime("%Y/%m/%d")}/{filename}'


class ExportFile(models.Model):
    """Модель для хранения экспортированных файлов"""
    STATUS_CHOICES = [
        ('pending', _('В ожидании')),
        ('processing', _('Обрабатывается')),
        ('completed', _('Завершено')),
        ('failed', _('Ошибка')),
    ]

    file = models.FileField(
        upload_to=export_file_path,
        verbose_name=_('Файл'),
        null=True,
        blank=True
    )
    filename = models.CharField(
        max_length=255,
        verbose_name=_('Имя файла')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Статус')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Дата завершения')
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Сообщение об ошибке')
    )
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name=_('Создатель'),
        null=True,
        blank=True
    )

    # Параметры экспорта
    poll = models.ForeignKey(
        'Poll',
        on_delete=models.CASCADE,
        verbose_name=_('Опрос'),
        null=True,
        blank=True
    )
    include_unfinished = models.BooleanField(
        default=False,
        verbose_name=_('Включать незавершенные')
    )
    
    # Параметры для chunked экспорта
    is_chunked = models.BooleanField(
        default=False,
        verbose_name=_('Разделен на части')
    )
    total_chunks = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Общее количество частей')
    )
    completed_chunks = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Завершенных частей')
    )
    chunk_size = models.PositiveIntegerField(
        default=1000,
        verbose_name=_('Размер части')
    )

    class Meta:
        verbose_name = _('Файл экспорта')
        verbose_name_plural = _('Файлы экспорта')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.filename} ({self.get_status_display()})"

    def get_file_url(self):
        """Возвращает URL для скачивания файла"""
        if self.file and self.status == 'completed':
            return self.file.url
        return None

    def delete_file(self):
        """Удаляет физический файл"""
        if self.file and os.path.exists(self.file.path):
            os.remove(self.file.path)

    def save(self, *args, **kwargs):
        # При удалении записи также удаляем файл
        if self.pk:
            try:
                old_instance = ExportFile.objects.get(pk=self.pk)
                if old_instance.file != self.file and old_instance.file:
                    old_instance.delete_file()
            except ExportFile.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.delete_file()
        super().delete(*args, **kwargs)
    
    def is_fully_completed(self):
        """Проверяет, завершен ли весь chunked экспорт"""
        if not self.is_chunked:
            return self.status == 'completed'
        return self.completed_chunks >= self.total_chunks
    
    def get_progress_percentage(self):
        """Получить процент выполнения chunked экспорта"""
        if not self.is_chunked:
            return 100 if self.status == 'completed' else 0
        if self.total_chunks == 0:
            return 0
        return round((self.completed_chunks / self.total_chunks) * 100, 1)


class ExportChunk(models.Model):
    """Модель для хранения отдельных частей chunked экспорта"""
    
    STATUS_CHOICES = [
        ('pending', _('В ожидании')),
        ('processing', _('Обрабатывается')),
        ('completed', _('Завершено')),
        ('failed', _('Ошибка')),
    ]
    
    export_file = models.ForeignKey(
        ExportFile,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name=_('Основной экспорт')
    )
    chunk_number = models.PositiveIntegerField(
        verbose_name=_('Номер части')
    )
    file = models.FileField(
        upload_to=export_file_path,
        verbose_name=_('Файл части'),
        null=True,
        blank=True
    )
    filename = models.CharField(
        max_length=255,
        verbose_name=_('Имя файла части')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Статус')
    )
    rows_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Количество строк')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Дата завершения')
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Сообщение об ошибке')
    )
    
    class Meta:
        verbose_name = _('Часть экспорта')
        verbose_name_plural = _('Части экспорта')
        ordering = ['export_file', 'chunk_number']
        unique_together = ['export_file', 'chunk_number']
    
    def __str__(self):
        return f"{self.export_file.filename} - часть {self.chunk_number}"
    
    def get_file_url(self):
        """Возвращает URL для скачивания файла части"""
        if self.file and self.status == 'completed':
            return self.file.url
        return None


class NotificationCampaign(models.Model):
    """Кампания уведомлений для пользователей, не прошедших опрос по теме"""

    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('processing', 'В обработке'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
    ]

    topic = models.ForeignKey('Poll', on_delete=models.CASCADE, verbose_name='Тема')
    total_users = models.IntegerField(default=0, verbose_name='Общее количество пользователей')
    sent_users = models.IntegerField(default=0, verbose_name='Отправлено пользователям')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время создания')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Время начала')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Время завершения')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус обработки')
    error_message = models.TextField(blank=True, verbose_name='Сообщение об ошибке')

    class Meta:
        verbose_name = 'Кампания уведомлений'
        verbose_name_plural = 'Кампании уведомлений'
        ordering = ['-created_at']

    def __str__(self):
        return f"Уведомления по теме '{self.topic.name}' - {self.total_users} пользователей"
    
    def save(self, *args, **kwargs):
        """Переопределяем save для автоматического расчета total_users"""
        if not self.pk and self.topic:  # Новый объект с темой
            from apps.users.models import TGUser
            from .models import Respondent
            
            users_who_completed = Respondent.objects.filter(
                poll=self.topic,
                finished_at__isnull=False
            ).values_list('tg_user_id', flat=True).distinct()
            
            # Исключаем заблокированных пользователей
            all_users = TGUser.objects.filter(is_active=True, blocked_bot=False)
            users_to_notify = all_users.exclude(id__in=users_who_completed)
            
            self.total_users = users_to_notify.count()
        
        super().save(*args, **kwargs)

    def get_progress_percentage(self):
        """Получить процент выполнения"""
        if self.total_users is None or self.total_users == 0:
            return 0
        return round((self.sent_users / self.total_users) * 100, 1)


class BroadcastPost(models.Model):
    """Модель для хранения постов для массовой рассылки"""
    
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('scheduled', 'Запланировано'),
        ('sending', 'Отправляется'),
        ('sent', 'Отправлено'),
        ('failed', 'Ошибка'),
    ]
    
    title = models.CharField(max_length=255, verbose_name='Заголовок поста')
    content = models.TextField(verbose_name='Содержание поста')
    image = models.ImageField(upload_to='broadcasts/', null=True, blank=True, verbose_name='Изображение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='Время отправки')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='Статус')
    
    # Статистика рассылки
    total_users = models.IntegerField(default=0, verbose_name='Всего пользователей')
    sent_users = models.IntegerField(default=0, verbose_name='Отправлено пользователям')
    failed_users = models.IntegerField(default=0, verbose_name='Ошибок отправки')
    
    # Время выполнения
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Время начала отправки')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Время завершения')
    error_message = models.TextField(blank=True, verbose_name='Сообщение об ошибке')
    
    class Meta:
        verbose_name = 'Пост для рассылки'
        verbose_name_plural = 'Посты для рассылки'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    def get_progress_percentage(self):
        """Получить процент выполнения"""
        if self.total_users is None or self.total_users == 0:
            return 0
        return round((self.sent_users / self.total_users) * 100, 1)
    
    def get_success_rate(self):
        """Получить процент успешных отправок"""
        if self.sent_users == 0:
            return 0
        total_attempts = self.sent_users + self.failed_users
        if total_attempts == 0:
            return 0
        return round((self.sent_users / total_attempts) * 100, 1)
