# Generated manually
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_tguser_last_activity_blocked_bot'),
        ('polls', '0014_add_chunked_export_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='tguser',
            name='balance',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Текущий баланс пользователя',
                max_digits=10,
                verbose_name='Баланс'
            ),
        ),
        migrations.AlterField(
            model_name='tguser',
            name='lang',
            field=models.CharField(
                choices=[
                    ('uz_cyrl', 'Ўзбекча (кириллица)'),
                    ('uz_latn', "O'zbekcha (lotin)"),
                    ('ru', 'Русский')
                ],
                default='uz_cyrl',
                max_length=10,
                verbose_name='Язык'
            ),
        ),
        migrations.CreateModel(
            name='WithdrawalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Сумма для вывода', max_digits=10, verbose_name='Сумма')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'В ожидании'),
                        ('approved', 'Одобрено'),
                        ('rejected', 'Отклонено'),
                        ('completed', 'Выполнено')
                    ],
                    default='pending',
                    max_length=20,
                    verbose_name='Статус'
                )),
                ('payment_details', models.TextField(help_text='Номер карты, телефона или другие реквизиты', verbose_name='Реквизиты для оплаты')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('processed_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата обработки')),
                ('admin_notes', models.TextField(blank=True, verbose_name='Заметки администратора')),
                ('processed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='processed_withdrawals',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Обработал'
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='withdrawal_requests',
                    to='users.tguser',
                    verbose_name='Пользователь'
                )),
            ],
            options={
                'verbose_name': 'Запрос на вывод',
                'verbose_name_plural': 'Запросы на вывод',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TransactionHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(
                    choices=[
                        ('earned', 'Заработано'),
                        ('withdrawal', 'Вывод средств'),
                        ('bonus', 'Бонус'),
                        ('refund', 'Возврат')
                    ],
                    max_length=20,
                    verbose_name='Тип транзакции'
                )),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Сумма')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата')),
                ('related_poll', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to='polls.poll',
                    verbose_name='Связанный опрос'
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transactions',
                    to='users.tguser',
                    verbose_name='Пользователь'
                )),
                ('withdrawal_request', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to='users.withdrawalrequest',
                    verbose_name='Связанный запрос на вывод'
                )),
            ],
            options={
                'verbose_name': 'Транзакция',
                'verbose_name_plural': 'Транзакции',
                'ordering': ['-created_at'],
            },
        ),
    ]

