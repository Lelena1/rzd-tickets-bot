from __future__ import annotations

from bot.rzd_api import Train


def format_train(train: Train) -> str:
    title = f"🚆 Поезд <b>{train.number}</b>"
    if train.name:
        title += f" «{train.name}»"
    if train.carrier:
        title += f" ({train.carrier})"
    lines = [
        title,
        f"{train.from_name} {train.departure} → {train.to_name} {train.arrival}",
        f"В пути: {train.travel_time}",
    ]
    if train.cars:
        for car in train.cars:
            seats = f"{car.free_seats} мест" if car.free_seats > 0 else "нет мест"
            price = f", от {car.price_from:.0f} ₽" if car.price_from else ""
            berths = ""
            if car.lower_seats or car.upper_seats:
                berths = f" (нижних: {car.lower_seats}, верхних: {car.upper_seats})"
            lines.append(f"  • {car.type_name}: {seats}{berths}{price}")
    else:
        lines.append("  Нет данных о местах (мест нет или продажа ещё не открыта)")
    lines.append(f"Всего свободно: <b>{train.total_free_seats}</b>")
    return "\n".join(lines)
