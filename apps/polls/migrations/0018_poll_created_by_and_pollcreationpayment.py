from django.conf import settings
from django.db import migrations
from django.db import models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("polls", "0017_add_multilingual_fields"),
        ("users", "0012_add_balance_and_language_features"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="poll",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_polls",
                to="users.tguser",
                verbose_name="Создатель (TG)",
            ),
        ),
        migrations.CreateModel(
            name="PollCreationPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, default=50000.0, max_digits=10, verbose_name="Сумма")),
                ("currency", models.CharField(default="UZS", max_length=8, verbose_name="Валюта")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ожидает подтверждения"),
                            ("approved", "Подтверждено"),
                            ("rejected", "Отклонено"),
                            ("cancelled", "Отменено"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                (
                    "proof",
                    models.TextField(
                        blank=True,
                        help_text="Текст/номер транзакции/комментарий пользователя",
                        verbose_name="Подтверждение оплаты",
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True, verbose_name="Дата подтверждения")),
                ("consumed_at", models.DateTimeField(blank=True, null=True, verbose_name="Дата использования")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата обновления")),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approved_poll_creation_payments",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Подтвердил",
                    ),
                ),
                (
                    "consumed_poll",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consuming_payments",
                        to="polls.poll",
                        verbose_name="Опрос (использовано)",
                    ),
                ),
                (
                    "tg_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="poll_creation_payments",
                        to="users.tguser",
                        verbose_name="Пользователь телеграм",
                    ),
                ),
            ],
            options={
                "verbose_name": "Оплата создания опроса",
                "verbose_name_plural": "Оплаты создания опросов",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pollcreationpayment",
            index=models.Index(fields=["tg_user", "status"], name="pollc_tguser_status_idx"),
        ),
        migrations.AddIndex(
            model_name="pollcreationpayment",
            index=models.Index(fields=["status", "created_at"], name="pollc_status_created_idx"),
        ),
    ]

