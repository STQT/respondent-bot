import asyncio
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.bot.misc import start_webhook


# Название класса обязательно - "Command"
class Command(BaseCommand):
  	# Используется как описание команды обычно
    help = 'Just a command for update webhook a Telegram bot.'

    def handle(self, *args, **kwargs):
        start_webhook()

