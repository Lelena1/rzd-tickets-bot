"""
Клиент к ticket.rzd.ru через настоящий (headless) браузер Playwright.

Почему не прямые HTTP-запросы: сайт защищён антибот-сервисом (BotFaqtor,
cdn.botfaqtor.ru), который блокирует запросы обычных HTTP-клиентов
(httpx/requests) — они получают 200 OK с пустым телом. Через реальный
движок Chromium (даже headless) сайт отдаёт данные нормально, как любому
посетителю — но все запросы выполняются через fetch() ВНУТРИ страницы
браузера (а не через отдельный APIRequestContext), иначе ловится
нестабильный DNS-резолв для ticket.rzd.ru на некоторых машинах.

Эндпоинты восстановлены по реальным сетевым запросам сайта (DevTools):
  - GET /api/v1/suggests — подсказки городов/станций (код и express-код).
  - GET /api/v1/railway-service/prices/train-pricing — тот же JSON с
    ценами и местами, которым пользуется сам сайт для отрисовки
    результатов поиска. Работает заметно быстрее, чем ждать и парсить
    отрисованную DOM-страницу, и даёт более подробные данные (нижние/
    верхние полки, места у питомцев и т.д. по каждому классу вагона).

Официальной документации на это у РЖД нет, сайт может измениться в любой
момент — тогда потребуется обновить парсинг ниже.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlencode

from playwright.async_api import (
    Browser,
    BrowserContext,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://ticket.rzd.ru"
SUGGESTS_URL = f"{BASE_URL}/api/v1/suggests"
PRICING_URL = f"{BASE_URL}/api/v1/railway-service/prices/train-pricing"

PAGE_LOAD_TIMEOUT_MS = 30_000

# Короткий код РЖД (CarType) -> человекочитаемое название, на случай
# если ServiceClassNameRu у группы вагонов не задан.
CAR_TYPE_NAMES = {
    "Sedentary": "Сидячий",
    "Compartment": "Купе",
    "ReservedSeat": "Плацкартный",
    "Luxury": "СВ",
    "Soft": "Люкс",
    "Baggage": "Багажный",
}


class RzdApiError(Exception):
    """Ошибка при обращении к ticket.rzd.ru."""


@dataclass
class Station:
    code: str  # nodeId (hex) — используется в ссылке на сайт для покупки
    express_code: str  # числовой код станции — используется в API поиска
    name: str


@dataclass
class CarGroup:
    type_name: str
    free_seats: int
    lower_seats: int
    upper_seats: int
    price_from: float | None
    has_pets: bool


@dataclass
class Train:
    number: str
    name: str
    carrier: str
    from_name: str
    to_name: str
    departure: str
    arrival: str
    travel_time: str
    cars: list[CarGroup] = field(default_factory=list)

    @property
    def total_free_seats(self) -> int:
        return sum(c.free_seats for c in self.cars)

    @property
    def has_any_pet_places(self) -> bool:
        return any(c.has_pets and c.free_seats > 0 for c in self.cars)


class RzdBrowser:
    """Держит один долгоживущий headless-браузер с сессией ticket.rzd.ru."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self.context = await self._browser.new_context(
            ignore_https_errors=True,  # сертификат ticket.rzd.ru от российского CA
            locale="ru-RU",
        )
        page = await self.context.new_page()
        await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        await page.close()
        logger.info("Браузер для ticket.rzd.ru запущен и готов")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


async def _fetch_json(context: BrowserContext, url: str) -> dict:
    """GET url через fetch() изнутри страницы ticket.rzd.ru (same-origin, с cookies)."""
    page = await context.new_page()
    try:
        try:
            await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        except PlaywrightTimeoutError as exc:
            raise RzdApiError("ticket.rzd.ru не ответил вовремя") from exc
        try:
            return await page.evaluate(
                "async (u) => { const r = await fetch(u); return await r.json(); }", url
            )
        except Exception as exc:  # noqa: BLE001
            raise RzdApiError(f"Не удалось получить ответ от ticket.rzd.ru: {exc}") from exc
    finally:
        await page.close()


async def suggest_stations(context: BrowserContext, name_part: str) -> list[Station]:
    """Поиск городов по части названия (автодополнение)."""
    name_part = name_part.strip()
    if len(name_part) < 2:
        return []

    query = urlencode(
        {
            "Query": name_part,
            "TransportType": "rail",
            "GroupResults": "true",
            "RailwaySortPriority": "true",
            "SynonymOn": "1",
            "Language": "ru",
        }
    )
    data = await _fetch_json(context, f"{SUGGESTS_URL}?{query}")

    stations: list[Station] = []
    for item in data.get("city") or []:
        node_id = item.get("nodeId")
        express_code = item.get("expressCode")
        name = item.get("name")
        if node_id and express_code and name:
            stations.append(Station(code=node_id, express_code=express_code, name=name))
    return stations


def _format_duration(minutes: int | None) -> str:
    if not minutes:
        return ""
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} ч {m} мин"
    if h:
        return f"{h} ч"
    return f"{m} мин"


def _format_time(iso_dt: str | None) -> str:
    if not iso_dt:
        return ""
    try:
        return datetime.fromisoformat(iso_dt).strftime("%H:%M")
    except ValueError:
        return ""


def _car_group_name(cg: dict) -> str:
    name = cg.get("ServiceClassNameRu")
    if name:
        return name
    return CAR_TYPE_NAMES.get(cg.get("CarType"), cg.get("CarTypeName") or "?")


def _aggregate_car_groups(raw_groups: list[dict]) -> list[CarGroup]:
    """РЖД отдаёт классы вагона раздельными подгруппами (напр. несколько
    «Эконом» с разными вагонами/ценами) — склеиваем по (название, места у
    питомцев), чтобы в боте было столько кнопок, сколько реально видно
    разных вариантов, но места у питомцев не терялись и не путались с
    обычными."""
    merged: dict[tuple[str, bool], CarGroup] = {}
    for raw in raw_groups:
        if raw.get("CarType") == "Baggage":
            # Багажный вагон — это место для крупного багажа, а не
            # пассажирское место; билет на него не продаётся как обычно
            # (цены у него и нет), поэтому в поиске и отслеживании он
            # только путает.
            continue
        name = _car_group_name(raw)
        has_pets = bool(raw.get("HasPlacesNearPets"))
        key = (name, has_pets)
        free = raw.get("TotalPlaceQuantity") or 0
        lower = raw.get("LowerPlaceQuantity") or 0
        upper = raw.get("UpperPlaceQuantity") or 0
        price = raw.get("MinPrice")

        if key not in merged:
            display_name = f"{name} 🐾" if has_pets else name
            merged[key] = CarGroup(
                type_name=display_name, free_seats=0, lower_seats=0, upper_seats=0,
                price_from=None, has_pets=has_pets,
            )
        group = merged[key]
        group.free_seats += free
        group.lower_seats += lower
        group.upper_seats += upper
        if price is not None and (group.price_from is None or price < group.price_from):
            group.price_from = price

    # Показываем только варианты, где реально есть свободные места.
    return [g for g in merged.values() if g.free_seats > 0]


async def search_trains(
    context: BrowserContext, express_from: str, express_to: str, date_iso: str
) -> list[Train]:
    """Поиск поездов между станциями на дату (date_iso — YYYY-MM-DD)."""
    params = {
        "service_provider": "B2B_RZD",
        "getByLocalTime": "true",
        "carGrouping": "DontGroup",
        "origin": express_from,
        "destination": express_to,
        "departureDate": f"{date_iso}T00:00:00",
        "specialPlacesDemand": "StandardPlacesAndForDisabledPersons",
        "carIssuingType": "All",
        "getTrainsFromSchedule": "true",
        "adultPassengersQuantity": "1",
        "childrenPassengersQuantity": "0",
        "hasPlacesForLargeFamily": "false",
    }
    url = f"{PRICING_URL}?{urlencode(params)}"
    data = await _fetch_json(context, url)

    if data.get("errorInfo"):
        raise RzdApiError(data["errorInfo"].get("Message") or "Ошибка поиска на ticket.rzd.ru")

    trains: list[Train] = []
    for raw in data.get("Trains") or []:
        carrier = ", ".join(raw.get("CarrierDisplayNames") or raw.get("Carriers") or [])
        trains.append(
            Train(
                number=(raw.get("TrainNumber") or "?").strip(),
                name=(raw.get("TrainName") or "").strip(),
                carrier=carrier,
                from_name=raw.get("OriginStationName") or "",
                to_name=raw.get("DestinationStationName") or "",
                departure=_format_time(raw.get("LocalDepartureDateTime")),
                arrival=_format_time(raw.get("LocalArrivalDateTime")),
                travel_time=_format_duration(raw.get("TripDuration")),
                cars=_aggregate_car_groups(raw.get("CarGroups") or []),
            )
        )
    return trains
