from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    waiting_from = State()
    choosing_from = State()
    waiting_to = State()
    choosing_to = State()
    waiting_date = State()


class TrackStates(StatesGroup):
    waiting_custom_class = State()
