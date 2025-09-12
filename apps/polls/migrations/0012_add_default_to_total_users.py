# Generated manually to fix IntegrityError

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0010_broadcastpost'),
        ('users', '0011_tguser_last_activity_blocked_bot'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificationcampaign',
            name='total_users',
            field=models.IntegerField(default=0, verbose_name='Общее количество пользователей'),
        ),
    ]
