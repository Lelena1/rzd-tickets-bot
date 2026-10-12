from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router()

HELP_TEXT = (
    "Я ищу поезда и билеты РЖД.\n\n"
    "/search — найти поезда между городами на дату\n"
    "/mytracking — список того, что я отслеживаю для вас\n"
    "/clear — убрать карточки последнего поиска из чата\n"
    "/cancel — отменить текущий диалог\n\n"
    "💡 Чтобы не искать эти команды в чате — нажмите на значок «Menu»/«☰» "
    "рядом с полем ввода сообщения (или наберите «/») — там всегда виден "
    "этот список с подсказками на русском, сколько бы сообщений ни было выше."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer("Привет! 👋\n\n" + HELP_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Диалог отменён.")


@router.message(Command("clear"))
async def cmd_clear_history(message: Message, state: FSMContext) -> None:
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
