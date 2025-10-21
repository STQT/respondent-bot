# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0015_poll_reward'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaptchaChallenge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('captcha_type', models.CharField(
                    choices=[
                        ('math', 'Математическая задача'),
                        ('text', 'Текстовая задача')
                    ],
                    max_length=20,
                    verbose_name='Тип капчи'
                )),
                ('question', models.TextField(verbose_name='Вопрос')),
                ('correct_answer', models.CharField(max_length=255, verbose_name='Правильный ответ')),
                ('user_answer', models.CharField(blank=True, max_length=255, verbose_name='Ответ пользователя')),
                ('is_correct', models.BooleanField(default=False, verbose_name='Правильный?')),
                ('attempts', models.IntegerField(default=0, verbose_name='Количество попыток')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('solved_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата решения')),
                ('respondent', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='captcha_challenges',
                    to='polls.respondent',
                    verbose_name='Респондент'
                )),
            ],
            options={
                'verbose_name': 'Капча',
                'verbose_name_plural': 'Капчи',
                'ordering': ['-created_at'],
            },
        ),
    ]

