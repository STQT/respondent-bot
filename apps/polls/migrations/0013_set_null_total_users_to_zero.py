# Generated manually to fix existing null values

from django.db import migrations


def set_null_total_users_to_zero(apps, schema_editor):
    """Set any existing null total_users values to 0"""
    NotificationCampaign = apps.get_model('polls', 'NotificationCampaign')
    NotificationCampaign.objects.filter(total_users__isnull=True).update(total_users=0)


def reverse_set_null_total_users_to_zero(apps, schema_editor):
    """Reverse migration - no action needed"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0012_add_default_to_total_users'),
    ]

    operations = [
        migrations.RunPython(
            set_null_total_users_to_zero,
            reverse_set_null_total_users_to_zero,
        ),
    ]
