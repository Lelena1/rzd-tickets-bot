from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from bot.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    code_from TEXT NOT NULL,
    name_from TEXT NOT NULL,
    code_to TEXT NOT NULL,
    name_to TEXT NOT NULL,
    express_from TEXT NOT NULL DEFAULT '',
    express_to TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL,
    train_number TEXT NOT NULL,
    train_brand TEXT NOT NULL,
    departure TEXT NOT NULL,
    car_class TEXT NOT NULL DEFAULT '',
    last_seats INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Колонки, добавленные после первого релиза — на случай, если у кого-то
# уже есть bot.db со старой схемой.
MIGRATIONS = {
    "car_class": "TEXT NOT NULL DEFAULT ''",
    "express_from": "TEXT NOT NULL DEFAULT ''",
    "express_to": "TEXT NOT NULL DEFAULT ''",
}


@dataclass
class TrackedItem:
    id: int
    chat_id: int
    code_from: str
    name_from: str
    code_to: str
    name_to: str
    express_from: str
    express_to: str
    date: str
    train_number: str
    train_brand: str
    departure: str
    car_class: str
    last_seats: int
    active: int
    created_at: str


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(SCHEMA)
        cursor = await conn.execute("PRAGMA table_info(tracked)")
        columns = {row[1] for row in await cursor.fetchall()}
        for col, ddl in MIGRATIONS.items():
            if col not in columns:
                await conn.execute(f"ALTER TABLE tracked ADD COLUMN {col} {ddl}")
        await conn.commit()


async def add_tracked(
    chat_id: int,
    code_from: str,
    name_from: str,
    code_to: str,
    name_to: str,
    express_from: str,
    express_to: str,
    date: str,
    train_number: str,
    train_brand: str,
    departure: str,
    initial_seats: int,
    car_class: str = "",
) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            """
            INSERT INTO tracked (
                chat_id, code_from, name_from, code_to, name_to,
                express_from, express_to, date,
                train_number, train_brand, departure, car_class, last_seats
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                code_from,
                name_from,
                code_to,
                name_to,
                express_from,
                express_to,
                date,
                train_number,
                train_brand,
                departure,
                car_class,
                initial_seats,
            ),
        )
        await conn.commit()
        return cursor.lastrowid


async def get_tracked(item_id: int) -> TrackedItem | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM tracked WHERE id = ?", (item_id,))
        row = await cursor.fetchone()
        return TrackedItem(**dict(row)) if row else None


async def list_tracked_for_chat(chat_id: int) -> list[TrackedItem]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM tracked WHERE chat_id = ? AND active = 1 ORDER BY date",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [TrackedItem(**dict(row)) for row in rows]


async def list_active_tracked() -> list[TrackedItem]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM tracked WHERE active = 1")
        rows = await cursor.fetchall()
        return [TrackedItem(**dict(row)) for row in rows]


async def update_last_seats(item_id: int, seats: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE tracked SET last_seats = ? WHERE id = ?", (seats, item_id)
        )
        await conn.commit()


async def deactivate(item_id: int, chat_id: int | None = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        if chat_id is not None:
            cursor = await conn.execute(
                "UPDATE tracked SET active = 0 WHERE id = ? AND chat_id = ?",
                (item_id, chat_id),
            )
        else:
            cursor = await conn.execute(
                "UPDATE tracked SET active = 0 WHERE id = ?", (item_id,)
            )
        await conn.commit()
        return cursor.rowcount > 0
