# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0016_captchachallenge'),
    ]

    operations = [
        # Poll мультиязычность
        migrations.AlterField(
            model_name='poll',
            name='description',
            field=models.TextField(verbose_name='Описание (узбекский кириллица)'),
        ),
        migrations.AddField(
            model_name='poll',
            name='description_uz_latn',
            field=models.TextField(
                blank=True,
                verbose_name='Описание (узбекский латиница)',
                help_text='Если пустое, будет использовано основное описание'
            ),
        ),
        migrations.AddField(
            model_name='poll',
            name='description_ru',
            field=models.TextField(
                blank=True,
                verbose_name='Описание (русский)',
                help_text='Если пустое, будет использовано основное описание'
            ),
        ),
        
        # Question мультиязычность
        migrations.AlterField(
            model_name='question',
            name='text',
            field=models.TextField(verbose_name='Текст (узбекский кириллица)'),
        ),
        migrations.AddField(
            model_name='question',
            name='text_uz_latn',
            field=models.TextField(
                blank=True,
                verbose_name='Текст (узбекский латиница)',
                help_text='Если пустое, будет использован основной текст'
            ),
        ),
        migrations.AddField(
            model_name='question',
            name='text_ru',
            field=models.TextField(
                blank=True,
                verbose_name='Текст (русский)',
                help_text='Если пустое, будет использован основной текст'
            ),
        ),
        
        # Choice мультиязычность
        migrations.AlterField(
            model_name='choice',
            name='text',
            field=models.CharField(max_length=255, verbose_name='Текст (узбекский кириллица)'),
        ),
        migrations.AddField(
            model_name='choice',
            name='text_uz_latn',
            field=models.CharField(
                max_length=255,
                blank=True,
                verbose_name='Текст (узбекский латиница)',
                help_text='Если пустое, будет использован основной текст'
            ),
        ),
        migrations.AddField(
            model_name='choice',
            name='text_ru',
            field=models.CharField(
                max_length=255,
                blank=True,
                verbose_name='Текст (русский)',
                help_text='Если пустое, будет использован основной текст'
            ),
        ),
    ]

