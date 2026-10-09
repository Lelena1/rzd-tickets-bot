from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from playwright.async_api import BrowserContext

from bot import db
from bot.rzd_api import RzdApiError, search_trains

logger = logging.getLogger(__name__)


async def check_all_tracked(bot: Bot, browser_ctx: BrowserContext) -> None:
    items = await db.list_active_tracked()
    if not items:
        return

    for item in items:
        try:
            item_date = datetime.strptime(item.date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if item_date < datetime.now().date():
            await db.deactivate(item.id)
            continue

        if not item.express_from or not item.express_to:
            logger.warning(
                "Пропускаю отслеживание id=%s: нет express-кодов (создано до обновления бота, "
                "поставьте на отслеживание заново через /search)",
                item.id,
            )
            continue

        try:
            trains = await search_trains(browser_ctx, item.express_from, item.express_to, item.date)
        except RzdApiError as exc:
            logger.warning("Ошибка проверки поезда %s: %s", item.train_number, exc)
            continue

        train = next((t for t in trains if t.number == item.train_number), None)
        if train is None:
            continue

        if item.car_class:
            wanted = item.car_class.strip().lower()
            car = next((c for c in train.cars if c.type_name.strip().lower() == wanted), None)
            current_seats = car.free_seats if car else 0
        else:
            current_seats = train.total_free_seats

        if current_seats > item.last_seats:
            display_date = item_date.strftime("%d.%m.%Y")
            class_label = item.car_class or "любой класс"
            try:
                await bot.send_message(
                    item.chat_id,
                    (
                        f"🎉 Появились места! Поезд {train.number} "
                        f"({item.name_from} → {item.name_to}, {display_date}), класс: {class_label}\n"
                        f"Свободно сейчас: {current_seats} (было {item.last_seats})"
                    ),
                )
            except Exception:  # noqa: BLE001 - не даём упасть всему циклу из-за одного чата
                logger.exception("Не удалось отправить уведомление chat_id=%s", item.chat_id)

        await db.update_last_seats(item.id, current_seats)
