from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.rzd_api import Station, Train


def stations_keyboard(stations: list[Station], prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=s.name, callback_data=f"{prefix}:{s.code}:{s.express_code}")]
        for s in stations[:8]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Стандартные классы вагонов РЖД для кнопочного выбора в «Другой класс» —
# чтобы пользователю почти никогда не приходилось печатать текст руками
# (а значит, и уходить в конец чата набирать сообщение).
STANDARD_CLASSES = [
    "Сидячий",
    "Плацкартный",
    "Купе",
    "СВ",
    "Люкс",
    "Базовый",
    "Эконом",
    "Эконом+",
    "Комфорт",
    "Бизнес класс",
    "Первый класс",
    "Семейный",
    "Вагон-бистро",
]


def build_track_keyboard(train_number: str, car_rows: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    """Кнопка отслеживания под каждым классом вагона + «любой класс» (сумма).

    car_rows — список (название класса, свободных мест), в т.ч. из уже
    сохранённых данных поиска (для кнопки «Назад»), а не только из свежего
    ответа API.
    """
    rows = []
    for i, (name, seats) in enumerate(car_rows):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔔 {name} ({seats})",
                    callback_data=f"track:{train_number}:{i}",
                )
            ]
        )
    if len(car_rows) > 1:
        total = sum(seats for _, seats in car_rows)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔔 Любой класс (всего {total})",
                    callback_data=f"track:{train_number}:all",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="✏️ Другой класс", callback_data=f"trackpicker:{train_number}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def track_keyboard(train: Train) -> InlineKeyboardMarkup:
    return build_track_keyboard(train.number, [(c.type_name, c.free_seats) for c in train.cars])


def class_picker_keyboard(train_number: str) -> InlineKeyboardMarkup:
    """Список стандартных классов вагона — шаг 1 выбора «Другого класса»."""
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"trackclasspick:{train_number}:{i}")]
        for i, name in enumerate(STANDARD_CLASSES)
    ]
    rows.append(
        [InlineKeyboardButton(text="✏️ Своё название (редкий класс)", callback_data=f"trackcustom:{train_number}")]
    )
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data=f"trackback:{train_number}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pet_choice_keyboard(train_number: str, class_idx: int) -> InlineKeyboardMarkup:
    """Обычные места или места с питомцем — шаг 2 выбора «Другого класса»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Обычные места", callback_data=f"trackfinal:{train_number}:{class_idx}:0")],
            [InlineKeyboardButton(text="🐾 Места с питомцем", callback_data=f"trackfinal:{train_number}:{class_idx}:1")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"trackpicker:{train_number}")],
        ]
    )


def _buy_button_text(train_number: str | None) -> str:
    # RZD не даёт прямых ссылок на конкретный поезд (его выбор не кодируется
    # в URL, только в состоянии браузера) — страница результатов содержит
    # все поезда сразу, поэтому номер нужного добавляем в текст кнопки.
    if train_number:
        return f"🛒 Купить (ищите поезд {train_number})"
    return "🛒 Открыть на ticket.rzd.ru для покупки"


def buy_link_keyboard(code_from: str, code_to: str, date_iso: str, train_number: str | None = None) -> InlineKeyboardMarkup:
    """Ссылка на страницу результатов на самом ticket.rzd.ru — для
    реальной покупки билета (бот сам билеты не покупает, см. README)."""
    url = f"https://ticket.rzd.ru/searchresults/v/1/{code_from}/{code_to}/{date_iso}?adult=1"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=_buy_button_text(train_number), url=url)]]
    )


def stop_tracking_button(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛑 Остановить", callback_data=f"untrack:{item_id}")]
        ]
    )


def tracked_item_keyboard(
    item_id: int, code_from: str, code_to: str, date_iso: str, train_number: str | None = None
) -> InlineKeyboardMarkup:
    """Для /mytracking — ссылка на покупку вместе с кнопкой остановки."""
    url = f"https://ticket.rzd.ru/searchresults/v/1/{code_from}/{code_to}/{date_iso}?adult=1"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_buy_button_text(train_number), url=url)],
            [InlineKeyboardButton(text="🛑 Остановить", callback_data=f"untrack:{item_id}")],
        ]
    )
