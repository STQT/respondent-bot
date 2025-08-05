from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from django.conf import settings
from django.urls import reverse
from redis.asyncio import Redis

from apps.bot.handlers.echo import echo_router
from apps.bot.handlers.start import start_router
from apps.bot.handlers.poll import poll_router
from apps.bot.middlewares import UserInternalIdMiddleware
from apps.bot.middlewares import ForbiddenUserMiddleware


def get_redis_storage():
    redis = Redis.from_url(settings.CACHES["default"]["LOCATION"])
    return RedisStorage(redis)


def register_all_misc() -> (Dispatcher, Bot):
    redis_storage = get_redis_storage()
    memory_storage = MemoryStorage()
    # Dispatcher is a root router
    dp = Dispatcher(storage=memory_storage if settings.DEBUG else redis_storage)
    dp.update.outer_middleware(UserInternalIdMiddleware())
    dp.update.outer_middleware(ForbiddenUserMiddleware())
    # Register all the routers from handlers package
    routers = (
        start_router,
        poll_router,
        echo_router
    )
    dp.include_routers(*routers)
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return dp, bot


async def bot_polling() -> None:
    # And the run events dispatching
    dp, bot = register_all_misc()

    await dp.start_polling(bot)


def get_webhook_url():
    host: str = settings.BOT_HOST
    if host.endswith("/"):
        host = host[:-1]
    return host + reverse("bot:" + settings.BOT_WEBHOOK_PATH, args=(settings.BOT_TOKEN,))


async def start_webhook() -> None:
    dp, bot = register_all_misc()
    webhook_info = await bot.get_webhook_info()
    webhook_url = get_webhook_url()
    if webhook_url != webhook_info.url:
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
