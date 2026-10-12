import html
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import db
from bot.keyboards import (
    STANDARD_CLASSES,
    build_track_keyboard,
    class_picker_keyboard,
    pet_choice_keyboard,
    stop_tracking_button,
    tracked_item_keyboard,
)
from bot.states import TrackStates
from bot.utils import display_date

logger = logging.getLogger(__name__)
router = Router()

STALE_CONTEXT_MSG = "Контекст поиска устарел, выполните /search заново."


def _check_context(data: dict) -> bool:
    required = (
        "code_from", "name_from", "code_to", "name_to",
        "express_from", "express_to", "date", "trains",
    )
    return all(k in data for k in required)


async def _finalize_tracking(
    callback: CallbackQuery,
    state: FSMContext,
    train_number: str,
    car_class: str,
    initial_seats: int,
    class_label: str,
) -> None:
    """Сохраняет отслеживание в БД и показывает подтверждение прямо в
    карточке поезда (редактируя её), а не новым сообщением в конце чата."""
    data = await state.get_data()
    train_info = data["trains"].get(train_number, {})

    item_id = await db.add_tracked(
        chat_id=callback.message.chat.id,
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

    confirmation = (
        f"\n\n🔔 <b>Отслеживаю: {html.escape(class_label)}</b> (сейчас {initial_seats} мест).\n"
        f"Напишу, когда появятся новые места."
    )
    base_text = callback.message.html_text or ""
    await callback.message.edit_text(
        base_text + confirmation, parse_mode="HTML", reply_markup=stop_tracking_button(item_id)
    )
    await callback.answer("Беру под отслеживание 🔔")


@router.callback_query(F.data.startswith("track:"))
async def track_train(callback: CallbackQuery, state: FSMContext) -> None:
    _, train_number, selector = callback.data.split(":", 2)
    data = await state.get_data()

    if not _check_context(data) or train_number not in data["trains"]:
        await callback.answer(STALE_CONTEXT_MSG, show_alert=True)
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

    await _finalize_tracking(callback, state, train_number, car_class, initial_seats, class_label)


@router.callback_query(F.data.startswith("trackpicker:"))
async def show_class_picker(callback: CallbackQuery, state: FSMContext) -> None:
    train_number = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if not _check_context(data) or train_number not in data["trains"]:
        await callback.answer(STALE_CONTEXT_MSG, show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=class_picker_keyboard(train_number))
    await callback.answer()


@router.callback_query(F.data.startswith("trackback:"))
async def show_train_keyboard(callback: CallbackQuery, state: FSMContext) -> None:
    train_number = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if not _check_context(data) or train_number not in data["trains"]:
        await callback.answer(STALE_CONTEXT_MSG, show_alert=True)
        return
    cars = data["trains"][train_number].get("cars", [])
    car_rows = [(c["type_name"], c["free_seats"]) for c in cars]
    await callback.message.edit_reply_markup(reply_markup=build_track_keyboard(train_number, car_rows))
    await callback.answer()


@router.callback_query(F.data.startswith("trackclasspick:"))
async def show_pet_choice(callback: CallbackQuery, state: FSMContext) -> None:
    _, train_number, idx_str = callback.data.split(":", 2)
    idx = int(idx_str)
    if idx >= len(STANDARD_CLASSES):
        await callback.answer("Этот вариант больше не актуален.", show_alert=True)
        return
    data = await state.get_data()
    if not _check_context(data) or train_number not in data["trains"]:
        await callback.answer(STALE_CONTEXT_MSG, show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=pet_choice_keyboard(train_number, idx))
    await callback.answer()


@router.callback_query(F.data.startswith("trackfinal:"))
async def track_final(callback: CallbackQuery, state: FSMContext) -> None:
    _, train_number, idx_str, pet_flag = callback.data.split(":", 3)
    idx = int(idx_str)
    if idx >= len(STANDARD_CLASSES):
        await callback.answer("Этот вариант больше не актуален.", show_alert=True)
        return

    data = await state.get_data()
    if not _check_context(data) or train_number not in data["trains"]:
        await callback.answer(STALE_CONTEXT_MSG, show_alert=True)
        return

    base_name = STANDARD_CLASSES[idx]
    has_pets = pet_flag == "1"
    car_class = f"{base_name} 🐾" if has_pets else base_name

    cars = data["trains"][train_number].get("cars", [])
    match = next((c for c in cars if c["type_name"].strip().lower() == car_class.lower()), None)
    initial_seats = match["free_seats"] if match else 0

    await _finalize_tracking(callback, state, train_number, car_class, initial_seats, car_class)


@router.callback_query(F.data.startswith("trackcustom:"))
async def track_custom_start(callback: CallbackQuery, state: FSMContext) -> None:
    train_number = callback.data.split(":", 1)[1]
    data = await state.get_data()

    if not _check_context(data) or train_number not in data["trains"]:
        await callback.answer(STALE_CONTEXT_MSG, show_alert=True)
        return

    await state.update_data(track_train_number=train_number)
    await state.set_state(TrackStates.waiting_custom_class)
    await callback.answer()
    await callback.message.answer(
        "Введите точное название класса вагона, как на сайте РЖД — "
        "на случай, если нужного нет в списке стандартных (редкий/особый класс)."
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
    train_info = data["trains"][train_number]

    item_id = await db.add_tracked(
        chat_id=message.chat.id,
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
    await message.answer(
        f"🔔 Слежу за поездом {train_number} ({data['name_from']} → {data['name_to']}, "
        f"{display_date(data['date'])}), класс: {html.escape(car_class)}.\n"
        f"Сейчас свободно: {initial_seats}.",
        reply_markup=stop_tracking_button(item_id),
    )
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
        await message.answer(
            text,
            reply_markup=tracked_item_keyboard(item.id, item.code_from, item.code_to, item.date),
        )


@router.callback_query(F.data.startswith("untrack:"))
async def untrack(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":", 1)[1])
    item = await db.get_tracked(item_id)
    ok = await db.deactivate(item_id, chat_id=callback.message.chat.id)
    if not ok:
        await callback.answer("Не найдено", show_alert=True)
        return

    await callback.answer("Остановлено")
    base_text = callback.message.html_text or ""
    new_text = base_text + "\n\n🛑 Отслеживание остановлено."

    # Если это сообщение было карточкой поезда из того же /search (данные
    # ещё в памяти) — возвращаем кнопки выбора класса, а не оставляем
    # сообщение совсем без кнопок.
    markup = None
    if item:
        data = await state.get_data()
        cars = data.get("trains", {}).get(item.train_number, {}).get("cars")
        if cars:
            car_rows = [(c["type_name"], c["free_seats"]) for c in cars]
            markup = build_track_keyboard(item.train_number, car_rows)

    await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=markup)
