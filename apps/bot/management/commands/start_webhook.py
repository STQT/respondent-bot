import asyncio
from django.core.management.base import BaseCommand
from asgiref.sync import async_to_sync

from apps.bot.misc import start_webhook


class Command(BaseCommand):
    help = 'Just a command to update the webhook for a Telegram bot.'

    def handle(self, *args, **kwargs):
        # Run the async function in a sync context
        async_to_sync(self.run_webhook)()

    async def run_webhook(self):
        await start_webhook()
