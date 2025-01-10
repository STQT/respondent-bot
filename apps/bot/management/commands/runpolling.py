import asyncio
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.bot.misc import bot_polling


# Название класса обязательно - "Command"
class Command(BaseCommand):
  	# Используется как описание команды обычно
    help = 'Just a command for launching a Telegram bot.'

    def handle(self, *args, **kwargs):
        asyncio.run(bot_polling())

