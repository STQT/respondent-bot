from django.contrib.auth.models import AbstractUser
from django.db.models import (
    CharField, Model, BigIntegerField,
    BooleanField, ForeignKey, FloatField,
    CASCADE, DateTimeField, TextField,
    DecimalField, PROTECT
)
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Default custom user model for Toshmi Oshi.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    class Meta:
        verbose_name = _("Админ")
        verbose_name_plural = _("Админы")

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})


class LanguageChoices(CharField):
    """Choices for language selection"""
    UZ_CYRL = 'uz_cyrl'
    UZ_LATN = 'uz_latn'
    RU = 'ru'
    
    CHOICES = [
        (UZ_CYRL, _('Ўзбекча (кириллица)')),
        (UZ_LATN, _("O'zbekcha (lotin)")),
        (RU, _('Русский')),
    ]


class TGUser(Model):
    id = BigIntegerField(verbose_name=_("ID пользователя"), db_index=True, primary_key=True, unique=True)
    username = CharField(verbose_name=_("Имя пользователя"), null=True, blank=True, max_length=255)
    fullname = CharField(verbose_name=_("Полное имя"), max_length=255)
    is_active = BooleanField(verbose_name=_("Активен?"), default=True)
    last_activity = DateTimeField(verbose_name=_("Последняя активность"), auto_now=True, null=True, blank=True)
    blocked_bot = BooleanField(verbose_name=_("Заблокировал бота?"), default=False)
    
    # Языковые настройки
    lang = CharField(
        verbose_name=_("Язык"),
        max_length=10,
        choices=LanguageChoices.CHOICES,
        default=LanguageChoices.UZ_CYRL
    )
    
    # Баланс пользователя
    balance = DecimalField(
        verbose_name=_("Баланс"),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_("Текущий баланс пользователя")
    )

    class Meta:
        verbose_name = _("Пользователь телеграм")
        verbose_name_plural = _("Пользователи телеграма")

    def __str__(self):
        return self.fullname


class WithdrawalRequest(Model):
    """Модель для запросов на вывод средств"""
    
    STATUS_CHOICES = [
        ('pending', _('В ожидании')),
        ('approved', _('Одобрено')),
        ('rejected', _('Отклонено')),
        ('completed', _('Выполнено')),
    ]
    
    user = ForeignKey(
        TGUser,
        on_delete=PROTECT,
        related_name='withdrawal_requests',
        verbose_name=_("Пользователь")
    )
    amount = DecimalField(
        verbose_name=_("Сумма"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Сумма для вывода")
    )
    status = CharField(
        verbose_name=_("Статус"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_details = TextField(
        verbose_name=_("Реквизиты для оплаты"),
        help_text=_("Номер карты, телефона или другие реквизиты")
    )
    created_at = DateTimeField(
        verbose_name=_("Дата создания"),
        auto_now_add=True
    )
    processed_at = DateTimeField(
        verbose_name=_("Дата обработки"),
        null=True,
        blank=True
    )
    processed_by = ForeignKey(
        User,
        on_delete=PROTECT,
        related_name='processed_withdrawals',
        verbose_name=_("Обработал"),
        null=True,
        blank=True
    )
    admin_notes = TextField(
        verbose_name=_("Заметки администратора"),
        blank=True
    )
    
    class Meta:
        verbose_name = _("Запрос на вывод")
        verbose_name_plural = _("Запросы на вывод")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.fullname} - {self.amount} - {self.get_status_display()}"


class TransactionHistory(Model):
    """История транзакций пользователя"""
    
    TRANSACTION_TYPES = [
        ('earned', _('Заработано')),
        ('withdrawal', _('Вывод средств')),
        ('bonus', _('Бонус')),
        ('refund', _('Возврат')),
    ]
    
    user = ForeignKey(
        TGUser,
        on_delete=CASCADE,
        related_name='transactions',
        verbose_name=_("Пользователь")
    )
    transaction_type = CharField(
        verbose_name=_("Тип транзакции"),
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    amount = DecimalField(
        verbose_name=_("Сумма"),
        max_digits=10,
        decimal_places=2
    )
    description = TextField(
        verbose_name=_("Описание"),
        blank=True
    )
    created_at = DateTimeField(
        verbose_name=_("Дата"),
        auto_now_add=True
    )
    related_poll = ForeignKey(
        'polls.Poll',
        on_delete=PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Связанный опрос")
    )
    withdrawal_request = ForeignKey(
        WithdrawalRequest,
        on_delete=PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Связанный запрос на вывод")
    )
    
    class Meta:
        verbose_name = _("Транзакция")
        verbose_name_plural = _("Транзакции")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.fullname} - {self.get_transaction_type_display()} - {self.amount}"
