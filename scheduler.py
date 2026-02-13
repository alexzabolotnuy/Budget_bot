from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from repo import Repo
from handlers.common import main_kb
from handlers.day_close import close_day_kb
from handlers.start import SetMonthlyBudget
from handlers.limits import month_limits_reuse_prompt_text, month_limits_reuse_prompt_kb
from services.reports import build_daily_report, build_weekly_report, build_monthly_report


async def send_to_all(bot: Bot, users: list[int], text: str, reply_markup=None):
    for uid in users:
        await bot.send_message(uid, text, reply_markup=reply_markup)

async def set_budget_state_for_all(storage: BaseStorage, bot_id: int, users: list[int]) -> None:
    for uid in users:
        key = StorageKey(bot_id=bot_id, chat_id=uid, user_id=uid)
        await storage.set_state(key, SetMonthlyBudget.amount)

def setup_scheduler(bot: Bot, repo: Repo, tz_name: str, users: list[int], storage: BaseStorage) -> AsyncIOScheduler:
    tz = ZoneInfo(tz_name)
    sched = AsyncIOScheduler(timezone=tz)

    async def ask_close_day_21():
        await send_to_all(bot, users, "Чи закриваємо день?", reply_markup=close_day_kb())

    async def close_day_22_and_report():
        day_iso = datetime.now(tz).date().isoformat()

        if not await repo.is_day_closed(day_iso):
            await repo.mark_day_closed(day_iso, datetime.now(tz).isoformat())

        text = await build_daily_report(repo, tz, day_iso)
        await send_to_all(bot, users, text)

    async def weekly_sun():
        now = datetime.now(tz)
        text = await build_weekly_report(repo, tz, now)
        await send_to_all(bot, users, text)

    async def monthly_1st():
        now = datetime.now(tz)

        prev = (now.replace(day=1).date() - timedelta(days=1))
        text = await build_monthly_report(repo, tz, prev.year, prev.month)
        await send_to_all(bot, users, text)

        # budget ask
        budget = await repo.get_monthly_budget(now.year, now.month)
        if budget <= 0:
            await set_budget_state_for_all(storage, bot.id, users)
            await send_to_all(bot, users, "Введи місячний бюджет:", reply_markup=main_kb())

        # limits reuse ask (тільки якщо ще нема лімітів на поточний місяць)
        if not await repo.has_month_limits(now.year, now.month):
            await send_to_all(bot, users, month_limits_reuse_prompt_text(), reply_markup=month_limits_reuse_prompt_kb())

    async def monthly_budget_reminder_daily():
        now = datetime.now(tz)
        budget = await repo.get_monthly_budget(now.year, now.month)
        if budget <= 0:
            await set_budget_state_for_all(storage, bot.id, users)
            await send_to_all(bot, users, "Введи місячний бюджет:", reply_markup=main_kb())

    sched.add_job(ask_close_day_21, CronTrigger(hour=21, minute=00))
    sched.add_job(close_day_22_and_report, CronTrigger(hour=22, minute=00))
    sched.add_job(weekly_sun, CronTrigger(day_of_week="sun", hour=22, minute=5))
    sched.add_job(monthly_1st, CronTrigger(day=1, hour=0, minute=10))
    sched.add_job(monthly_budget_reminder_daily, CronTrigger(hour=9, minute=0))

    return sched
