from __future__ import annotations

from datetime import date, datetime, timedelta

_ALIASES = {
    "сегодня": 0,
    "today": 0,
    "завтра": 1,
    "tomorrow": 1,
    "послезавтра": 2,
}


def parse_date(text: str) -> date | None:
    """Разбирает dd.mm.yyyy, dd.mm или слова 'сегодня'/'завтра'. Возвращает None, если не удалось."""
    text = text.strip().lower()

    if text in _ALIASES:
        return date.today() + timedelta(days=_ALIASES[text])

    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    try:
        day, month = (int(p) for p in text.split(".")[:2])
        today = date.today()
        candidate = date(today.year, month, day)
        if candidate < today:
            candidate = date(today.year + 1, month, day)
        return candidate
    except (ValueError, IndexError):
        return None


def format_date(d: date) -> str:
    """Формат для показа пользователю: дд.мм.гггг."""
    return d.strftime("%d.%m.%Y")


def format_date_iso(d: date) -> str:
    """Формат для API ticket.rzd.ru: гггг-мм-дд."""
    return d.strftime("%Y-%m-%d")


def display_date(date_iso: str) -> str:
    """Переводит хранимую ISO-дату (гггг-мм-дд) в дд.мм.гггг для пользователя."""
    try:
        return datetime.strptime(date_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return date_iso
