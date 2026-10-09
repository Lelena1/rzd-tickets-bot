from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.rzd_api import Station, Train


def stations_keyboard(stations: list[Station], prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=s.name, callback_data=f"{prefix}:{s.code}:{s.express_code}")]
        for s in stations[:8]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def track_keyboard(train: Train) -> InlineKeyboardMarkup:
    """Кнопка отслеживания под каждым классом вагона + «любой класс» (сумма)."""
    rows = []
    for i, car in enumerate(train.cars):
        label = car.type_name.strip()
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔔 {label} ({car.free_seats})",
                    callback_data=f"track:{train.number}:{i}",
                )
            ]
        )
    if len(train.cars) > 1:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔔 Любой класс (всего {train.total_free_seats})",
                    callback_data=f"track:{train.number}:all",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="✏️ Другой класс (которого нет в списке)",
                callback_data=f"trackcustom:{train.number}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def buy_link_keyboard(code_from: str, code_to: str, date_iso: str) -> InlineKeyboardMarkup:
    """Ссылка на страницу результатов на самом ticket.rzd.ru — для
    реальной покупки билета (бот сам билеты не покупает, см. README)."""
    url = f"https://ticket.rzd.ru/searchresults/v/1/{code_from}/{code_to}/{date_iso}?adult=1"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛒 Открыть на ticket.rzd.ru для покупки", url=url)]]
    )


def stop_tracking_button(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛑 Остановить", callback_data=f"untrack:{item_id}")]
        ]
    )
