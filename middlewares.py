from __future__ import annotations
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from repo import Repo

class AccessAndDIMiddleware(BaseMiddleware):
    def __init__(self, repo: Repo, tz_name: str, users: list[int]):
        super().__init__()
        self.repo = repo
        self.tz_name = tz_name
        self.users = users

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # доступ тільки 2 users
        from_user = getattr(event, "from_user", None)
        if from_user and from_user.id not in self.users:
            # нічого не відповідаємо (максимально просто)
            return

        data["repo"] = self.repo
        data["tz_name"] = self.tz_name
        data["users"] = self.users
        return await handler(event, data)
