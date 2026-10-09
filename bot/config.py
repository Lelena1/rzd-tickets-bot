import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "bot.db")
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Создайте .env (по образцу .env.example) "
        "или задайте переменную окружения BOT_TOKEN."
    )
