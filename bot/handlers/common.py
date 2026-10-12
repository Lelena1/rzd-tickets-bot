from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards import BTN_CLEAR, BTN_FROM, BTN_TO, main_menu_keyboard
from bot.states import SearchStates

router = Router()

HELP_TEXT = (
    "Я ищу поезда и билеты РЖД.\n\n"
    "📍 Откуда / 🏁 Куда — задать города (в любом порядке), дальше спрошу дату\n"
    "🗑 Очистить историю — убрать карточки последнего поиска из чата\n"
    "/mytracking — список того, что я отслеживаю для вас\n"
    "/cancel — отменить текущий диалог\n"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer("Привет! 👋\n\n" + HELP_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Диалог отменён.")


@router.message(F.text == BTN_FROM)
async def button_from(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_from)
    await message.answer("Из какого города/станции едем? Введите название.")


@router.message(F.text == BTN_TO)
async def button_to(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_to)
    await message.answer("В какой город/станцию едем? Введите название.")


@router.message(F.text == BTN_CLEAR)
async def button_clear_history(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    message_ids = data.get("search_message_ids") or []
    if not message_ids:
        await message.answer("Нечего убирать — результатов последнего поиска нет.")
        return

    removed = 0
    for msg_id in message_ids:
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
            removed += 1
        except Exception:  # noqa: BLE001 - уже удалено вручную и т.п.
            pass

    await state.update_data(search_message_ids=[])
    await message.answer(f"Готово, убрала {removed} сообщений последнего поиска.")
