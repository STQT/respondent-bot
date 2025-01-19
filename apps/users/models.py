from django.contrib.auth.models import AbstractUser
from django.db.models import (
    CharField, Model, BigIntegerField,
    BooleanField, ForeignKey, FloatField,
    CASCADE
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
        verbose_name = _("Admin foydalanuvchilar")
        verbose_name_plural = _("Admin foydalanuvchilar")

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})


class TGUser(Model):
    id = BigIntegerField(verbose_name=_("ID пользователя"), db_index=True, primary_key=True, unique=True)
    username = CharField(verbose_name=_("Имя пользователя"), null=True, blank=True, max_length=255)
    lang = CharField(verbose_name=_("Язык пользователя"), default="uz", max_length=2)
    fullname = CharField(verbose_name=_("Полное имя"), max_length=255)
    phone = CharField(verbose_name=_("Телефонный номер"), max_length=20, blank=True, null=True)
    is_active = BooleanField(verbose_name=_("Активен?"), default=True)

    class Meta:
        verbose_name = _("Telegram foydalanuvchi")
        verbose_name_plural = _("Telegram foydalanuvchilar")

    def __str__(self):
        return self.fullname


class UserLocations(Model):
    user = ForeignKey(TGUser, on_delete=CASCADE, related_name="locations")
    longitude = FloatField()
    latitude = FloatField()
    name = CharField(max_length=255)

    class Meta:
        verbose_name = _("Telegram lokatsiya")
        verbose_name_plural = _("Telegram lokatsiyalar")

    def __str__(self):
        return self.name
