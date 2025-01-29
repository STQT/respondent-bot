from django.core.management.base import BaseCommand, CommandError
from apps.contrib.clickuz.clickuz import ClickUz


class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def handle(self, *args, **options):
        url = ClickUz.generate_url("3", 1000, "https://google.com")
        return url
