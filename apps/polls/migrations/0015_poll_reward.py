# Generated manually
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0014_add_chunked_export_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='poll',
            name='reward',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Сумма вознаграждения за прохождение опроса',
                max_digits=10,
                verbose_name='Вознаграждение'
            ),
        ),
    ]

