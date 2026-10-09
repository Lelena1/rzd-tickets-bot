import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import db
from bot.keyboards import stop_tracking_button
from bot.states import TrackStates
from bot.utils import display_date

logger = logging.getLogger(__name__)
router = Router()


def _check_context(data: dict) -> bool:
    required = (
        "code_from", "name_from", "code_to", "name_to",
        "express_from", "express_to", "date", "trains",
    )
    return all(k in data for k in required)


async def _save_tracking(
    chat_id: int,
    data: dict,
    train_number: str,
    car_class: str,
    initial_seats: int,
    class_label: str,
) -> str:
    train_info = data["trains"].get(train_number, {})
    await db.add_tracked(
        chat_id=chat_id,
        code_from=data["code_from"],
        name_from=data["name_from"],
        code_to=data["code_to"],
        name_to=data["name_to"],
        express_from=data["express_from"],
        express_to=data["express_to"],
        date=data["date"],
        train_number=train_number,
        train_brand=train_info.get("carrier", ""),
        departure=train_info.get("departure", ""),
        initial_seats=initial_seats,
        car_class=car_class,
    )
    return (
        f"Слежу за поездом {train_number} ({data['name_from']} → {data['name_to']}, "
        f"{display_date(data['date'])}), класс: {class_label}.\n"
        f"Напишу, когда появятся новые свободные места.\n"
        f"Сейчас свободно: {initial_seats}."
    )


@router.callback_query(F.data.startswith("track:"))
async def track_train(callback: CallbackQuery, state: FSMContext) -> None:
    _, train_number, selector = callback.data.split(":", 2)
    data = await state.get_data()

    if not _check_context(data) or train_number not in data["trains"]:
        await callback.answer(
            "Контекст поиска устарел, выполните /search заново.", show_alert=True
        )
        return

    cars = data["trains"][train_number].get("cars", [])
    if selector == "all":
        car_class = ""
        initial_seats = sum(c["free_seats"] for c in cars)
        class_label = "любой класс"
    else:
        idx = int(selector)
        if idx >= len(cars):
            await callback.answer("Этот вариант больше не актуален.", show_alert=True)
            return
        car_class = cars[idx]["type_name"]
        initial_seats = cars[idx]["free_seats"]
        class_label = car_class

    text = await _save_tracking(callback.message.chat.id, data, train_number, car_class, initial_seats, class_label)
    await callback.answer("Беру поезд под отслеживание 🔔")
    await callback.message.answer(text)


@router.callback_query(F.data.startswith("trackcustom:"))
async def track_custom_start(callback: CallbackQuery, state: FSMContext) -> None:
    train_number = callback.data.split(":", 1)[1]
    data = await state.get_data()

    if not _check_context(data) or train_number not in data["trains"]:
        await callback.answer(
            "Контекст поиска устарел, выполните /search заново.", show_alert=True
        )
        return

    await state.update_data(track_train_number=train_number)
    await state.set_state(TrackStates.waiting_custom_class)
    await callback.answer()
    await callback.message.answer(
        "Введите точное название класса вагона, как на сайте РЖД — например:\n"
        "Плацкартный, Купе, СВ, Сидячий, Люкс.\n\n"
        "Если нужны именно места у питомцев для этого класса — допишите в конце 🐾 "
        "(например: «Эконом 🐾»).\n\n"
        "Сейчас у этого класса может не быть мест в продаже — это нормально, "
        "бот напишет, как только места появятся."
    )


@router.message(TrackStates.waiting_custom_class)
async def track_custom_finish(message: Message, state: FSMContext) -> None:
    car_class = (message.text or "").strip()
    if not car_class:
        await message.answer("Название класса не может быть пустым. Введите ещё раз.")
        return

    data = await state.get_data()
    train_number = data.get("track_train_number")
    if not train_number or not _check_context(data) or train_number not in data["trains"]:
        await message.answer("Контекст поиска устарел, выполните /search заново.")
        await state.set_state(None)
        return

    cars = data["trains"][train_number].get("cars", [])
    match = next((c for c in cars if c["type_name"].strip().lower() == car_class.lower()), None)
    initial_seats = match["free_seats"] if match else 0

    text = await _save_tracking(message.chat.id, data, train_number, car_class, initial_seats, car_class)
    await message.answer(text)
    await state.set_state(None)


@router.message(Command("mytracking"))
async def my_tracking(message: Message) -> None:
    items = await db.list_tracked_for_chat(message.chat.id)
    if not items:
        await message.answer("У вас нет активных отслеживаний. Используйте /search.")
        return

    await message.answer(f"Активных отслеживаний: {len(items)}")
    for item in items:
        class_label = item.car_class or "любой класс"
        text = (
            f"🚆 Поезд {item.train_number} ({item.train_brand}), класс: {class_label}\n"
            f"{item.name_from} → {item.name_to}, {display_date(item.date)}\n"
            f"Последнее известное число мест: {item.last_seats}"
        )
        await message.answer(text, reply_markup=stop_tracking_button(item.id))


@router.callback_query(F.data.startswith("untrack:"))
async def untrack(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":", 1)[1])
    ok = await db.deactivate(item_id, chat_id=callback.message.chat.id)
    if ok:
        await callback.answer("Остановлено")
        await callback.message.edit_text(callback.message.text + "\n\n🛑 Отслеживание остановлено.")
    else:
        await callback.answer("Не найдено", show_alert=True)
