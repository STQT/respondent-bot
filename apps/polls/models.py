import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import TextChoices
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.users.models import TGUser


class Poll(models.Model):
    name = models.CharField(max_length=255)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    description = models.TextField()
    deadline = models.DateTimeField()

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
