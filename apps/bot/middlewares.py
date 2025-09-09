import logging
from typing import Callable, Awaitable, Dict, Any

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import TelegramObject

from apps.bot.utils import async_get_or_create_user
from apps.users.models import TGUser

logger = logging.getLogger(__name__)


class UserInternalIdMiddleware(BaseMiddleware):
    async def get_internal_user(self, user_id: int, full_name, username) -> TGUser | None:
        obj, _created = await async_get_or_create_user(
            id=user_id,
            defaults={
                "fullname": full_name,
                "username": username
            }
        )
        
        # Если пользователь вернулся (отправил сообщение), сбрасываем флаг блокировки
        if not _created and obj.blocked_bot:
            await TGUser.objects.filter(id=user_id).aupdate(
                blocked_bot=False,
                is_active=True
            )
            logger.info(f"User {user_id} ({full_name}) unblocked the bot")
        
        return obj

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data["event_from_user"]
        data["user"] = await self.get_internal_user(
            user_id=user.id, full_name=user.full_name, username=user.username
        )
        return await handler(event, data)


class ForbiddenUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except TelegramForbiddenError:
            user: TGUser | None = data.get("user")
            if user and isinstance(user, TGUser):
                # Помечаем пользователя как заблокировавшего бота и неактивного
                await TGUser.objects.filter(id=user.id).aupdate(
                    is_active=False, 
                    blocked_bot=True
                )
                logger.info(f"User {user.id} ({user.fullname}) blocked the bot")
            # Не пробрасываем дальше, просто игнорируем update
            return None
        except Exception as e:
            logging.critical(f"Unhandled exception in ForbiddenUserMiddleware: {e}")
            return None
