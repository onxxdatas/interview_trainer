from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from app.config import get_settings


class AllowedUserMiddleware(BaseMiddleware):
    """If ALLOWED_TELEGRAM_USER_ID is set, silently ignore everyone else."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings = get_settings()
        if settings.allowed_telegram_user_id is None:
            return await handler(event, data)

        user: TgUser | None = data.get("event_from_user")
        if user is not None and user.id != settings.allowed_telegram_user_id:
            return None  # silently drop; do not leak bot existence/behavior
        return await handler(event, data)
