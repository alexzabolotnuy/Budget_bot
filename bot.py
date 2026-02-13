from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import cfg
from db import Database
from repo import Repo
from middlewares import AccessAndDIMiddleware
from scheduler import setup_scheduler

from handlers import start, expenses, categories, budget, day_close, limits

logging.basicConfig(level=logging.INFO)

async def main():
    # cfg = load_config()

    db = Database(cfg.db_path)
    await db.connect()
    repo = Repo(db)

    bot = Bot(token=cfg.token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(AccessAndDIMiddleware(repo, cfg.tz, cfg.users))

    dp.include_router(start.router)
    dp.include_router(expenses.router)
    dp.include_router(categories.router)
    dp.include_router(limits.router)   # ✅ new
    dp.include_router(budget.router)
    dp.include_router(day_close.router)

    scheduler = setup_scheduler(bot, repo, cfg.tz, cfg.users, dp.storage)
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
