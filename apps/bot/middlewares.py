from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from apps.users.models import TGUser
from apps.bot.utils import async_get_or_create_user


class UserInternalIdMiddleware(BaseMiddleware):
    async def get_internal_user(self, user_id: int, full_name, username) -> TGUser | None:
        obj, _created = await async_get_or_create_user(
            id=user_id,
            defaults={
                "fullname": full_name,
                "username": username
            }
        )
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
