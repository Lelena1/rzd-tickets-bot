import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from playwright.async_api import BrowserContext

from bot.formatting import format_train
from bot.keyboards import buy_link_keyboard, stations_keyboard, track_keyboard
from bot.rzd_api import RzdApiError, search_trains, suggest_stations
from bot.states import SearchStates
from bot.utils import format_date, format_date_iso, parse_date

logger = logging.getLogger(__name__)
router = Router()

MAX_TRAINS_SHOWN = 50


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_from)
    await message.answer("Из какого города/станции едем? Введите название.")


@router.message(SearchStates.waiting_from)
async def got_from_name(message: Message, state: FSMContext, browser_ctx: BrowserContext) -> None:
    stations = await suggest_stations(browser_ctx, message.text or "")
    if not stations:
        await message.answer("Ничего не найдено, попробуйте ввести название иначе.")
        return
    await state.update_data(from_candidates={s.code: s.name for s in stations})
    await state.set_state(SearchStates.choosing_from)
    await message.answer("Выберите станцию отправления:", reply_markup=stations_keyboard(stations, "from"))


@router.callback_query(SearchStates.choosing_from, F.data.startswith("from:"))
async def chosen_from(callback: CallbackQuery, state: FSMContext) -> None:
    _, code, express = callback.data.split(":", 2)
    data = await state.get_data()
    name = data.get("from_candidates", {}).get(code, code)
    await state.update_data(code_from=code, express_from=express, name_from=name)
    await state.set_state(SearchStates.waiting_to)
    await callback.message.edit_text(f"Отправление: {name}")
    await callback.message.answer("Куда едем? Введите название города/станции.")
    await callback.answer()


@router.message(SearchStates.waiting_to)
async def got_to_name(message: Message, state: FSMContext, browser_ctx: BrowserContext) -> None:
    stations = await suggest_stations(browser_ctx, message.text or "")
    if not stations:
        await message.answer("Ничего не найдено, попробуйте ввести название иначе.")
        return
    await state.update_data(to_candidates={s.code: s.name for s in stations})
    await state.set_state(SearchStates.choosing_to)
    await message.answer("Выберите станцию прибытия:", reply_markup=stations_keyboard(stations, "to"))


@router.callback_query(SearchStates.choosing_to, F.data.startswith("to:"))
async def chosen_to(callback: CallbackQuery, state: FSMContext) -> None:
    _, code, express = callback.data.split(":", 2)
    data = await state.get_data()
    name = data.get("to_candidates", {}).get(code, code)
    await state.update_data(code_to=code, express_to=express, name_to=name)
    await state.set_state(SearchStates.waiting_date)
    await callback.message.edit_text(f"Прибытие: {name}")
    await callback.message.answer(
        "На какую дату искать? Формат дд.мм.гггг, либо 'сегодня' / 'завтра'."
    )
    await callback.answer()


@router.message(SearchStates.waiting_date)
async def got_date(message: Message, state: FSMContext, browser_ctx: BrowserContext) -> None:
    parsed = parse_date(message.text or "")
    if not parsed:
        await message.answer("Не понял дату. Введите в формате дд.мм.гггг, например 25.12.2026.")
        return

    date_display = format_date(parsed)
    date_iso = format_date_iso(parsed)
    data = await state.get_data()
    code_from, name_from = data["code_from"], data["name_from"]
    code_to, name_to = data["code_to"], data["name_to"]
    express_from, express_to = data["express_from"], data["express_to"]

    await message.answer("Ищу поезда…")
    try:
        trains = await search_trains(browser_ctx, express_from, express_to, date_iso)
    except RzdApiError as exc:
        await message.answer(f"Не удалось получить данные от РЖД: {exc}")
        await state.clear()
        return

    if not trains:
        await message.answer("На эту дату поездов не найдено.")
        await state.clear()
        return

    await state.update_data(
        date=date_iso,
        trains={
            t.number: {
                "name": t.name,
                "carrier": t.carrier,
                "departure": t.departure,
                "cars": [{"type_name": c.type_name, "free_seats": c.free_seats} for c in t.cars],
            }
            for t in trains
        },
    )

    await _delete_previous_results(message, data)

    shown = trains[:MAX_TRAINS_SHOWN]
    route_line = f"{name_from} → {name_to}, {date_display}"

    pet_trains = sum(1 for t in trains if t.has_any_pet_places)
    header = f"Найдено поездов: {len(trains)} ({route_line})"
    if pet_trains:
        header += f"\n🐾 С местами с питомцем: {pet_trains}"
    if len(trains) > MAX_TRAINS_SHOWN:
        header += f"\nПоказываю первые {MAX_TRAINS_SHOWN} — уточните дату/время, если нужного поезда нет в списке."

    sent_ids = []
    header_msg = await message.answer(header, reply_markup=buy_link_keyboard(code_from, code_to, date_iso))
    sent_ids.append(header_msg.message_id)

    for i, train in enumerate(shown, start=1):
        position = f"<b>№{i} из {len(shown)}</b> · {route_line}\n\n"
        train_msg = await message.answer(
            position + format_train(train), parse_mode="HTML", reply_markup=track_keyboard(train)
        )
        sent_ids.append(train_msg.message_id)

    await state.update_data(search_message_ids=sent_ids)
    await state.set_state(None)


async def _delete_previous_results(message: Message, data: dict) -> None:
    """Убирает карточки предыдущего поиска, чтобы в чате не накапливались
    результаты из разных дат/маршрутов вперемешку."""
    for msg_id in data.get("search_message_ids") or []:
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except Exception:  # noqa: BLE001 - сообщение могли удалить вручную и т.п.
            pass
