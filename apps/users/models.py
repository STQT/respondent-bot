from django.contrib.auth.models import AbstractUser
from django.db.models import (
    CharField, Model, BigIntegerField,
    BooleanField, ForeignKey, FloatField,
    CASCADE, DateTimeField
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


class TGUser(Model):
    id = BigIntegerField(verbose_name=_("ID пользователя"), db_index=True, primary_key=True, unique=True)
    username = CharField(verbose_name=_("Имя пользователя"), null=True, blank=True, max_length=255)
    fullname = CharField(verbose_name=_("Полное имя"), max_length=255)
    is_active = BooleanField(verbose_name=_("Активен?"), default=True)
    last_activity = DateTimeField(verbose_name=_("Последняя активность"), auto_now=True, null=True, blank=True)
    blocked_bot = BooleanField(verbose_name=_("Заблокировал бота?"), default=False)

    class Meta:
        verbose_name = _("Пользователь телеграм")
        verbose_name_plural = _("Пользователи телеграма")

    def __str__(self):
        return self.fullname
