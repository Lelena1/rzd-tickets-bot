from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router()

HELP_TEXT = (
    "Я ищу поезда и билеты РЖД.\n\n"
    "/search — найти поезда между городами на дату\n"
    "/mytracking — список того, что я отслеживаю для вас\n"
    "/cancel — отменить текущий диалог\n"
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
