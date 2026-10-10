from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import ALLOWED_USER_IDS

DENY_MESSAGE = "Этот бот приватный и недоступен для вас."


class AccessControlMiddleware(BaseMiddleware):
    """Пропускает только пользователей из ALLOWED_USER_IDS (если список задан)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not ALLOWED_USER_IDS:
            return await handler(event, data)

        user = data.get("event_from_user")
        if user is not None and user.id in ALLOWED_USER_IDS:
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(DENY_MESSAGE)
        elif isinstance(event, CallbackQuery):
            await event.answer(DENY_MESSAGE, show_alert=True)
        return None
