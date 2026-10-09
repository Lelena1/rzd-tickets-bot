import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import db
from bot.config import BOT_TOKEN, POLL_INTERVAL_MINUTES
from bot.handlers import common, search, tracking
from bot.rzd_api import RzdBrowser
from bot.scheduler import check_all_tracked

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    await db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()
    dp.include_router(common.router)
    dp.include_router(search.router)
    dp.include_router(tracking.router)

    rzd_browser = RzdBrowser()
    await rzd_browser.start()
    dp["browser_ctx"] = rzd_browser.context

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_all_tracked,
        "interval",
        minutes=POLL_INTERVAL_MINUTES,
        args=[bot, rzd_browser.context],
        id="check_tracked",
        max_instances=1,
    )
    scheduler.start()

    logger.info("Бот запущен, опрос отслеживаний каждые %s мин.", POLL_INTERVAL_MINUTES)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await rzd_browser.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
