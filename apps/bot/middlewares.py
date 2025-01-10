from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from apps.users.models import TGUser


class UserInternalIdMiddleware(BaseMiddleware):
    async def get_internal_user(self, user_id: int) -> TGUser | None:
        try:
            obj = await TGUser.objects.aget(id=user_id)
            return obj
        except TGUser.DoesNotExist:
            return None

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data["event_from_user"]
        data["user"] = await self.get_internal_user(user.id)
        return await handler(event, data)
