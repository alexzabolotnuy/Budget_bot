from __future__ import annotations

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from services.reports import build_daily_report, build_weekly_report, build_monthly_report


# ✅ PROD-варіант: завжди Europe/Warsaw
WARSAW_TZ = ZoneInfo("Europe/Warsaw")


async def _send_to_users(bot: Bot, users: list[int], text: str):
    for uid in users:
        try:
            await bot.send_message(uid, text)
        except Exception:
            pass


async def send_daily_report(bot: Bot, repo, users: list[int]):
    now = datetime.now(WARSAW_TZ)  # timezone-aware Warsaw
    day_iso = now.date().isoformat()
    text = await build_daily_report(repo, WARSAW_TZ, day_iso)
    await _send_to_users(bot, users, text)


async def send_weekly_report(bot: Bot, repo, users: list[int]):
    now = datetime.now(WARSAW_TZ)  # timezone-aware Warsaw
    text = await build_weekly_report(repo, WARSAW_TZ, now)
    await _send_to_users(bot, users, text)


async def send_monthly_report_for_previous_month(bot: Bot, repo, users: list[int]):
    now = datetime.now(WARSAW_TZ)  # timezone-aware Warsaw
    first_day = date(now.year, now.month, 1)
    prev_last_day = first_day - timedelta(days=1)
    y = prev_last_day.year
    m = prev_last_day.month
    text = await build_monthly_report(repo, WARSAW_TZ, y, m)
    await _send_to_users(bot, users, text)


def setup_scheduler(
    bot: Bot,
    repo,
    tz_name: str | None = None,     # сумісність зі старим викликом (ігноруємо)
    users: list[int] | None = None,
    storage=None,                   # сумісність зі старим викликом
) -> AsyncIOScheduler:
    users = users or []

    # ✅ Scheduler теж у Warsaw (не UTC)
    sched = AsyncIOScheduler(timezone=WARSAW_TZ)

    print("[SCHED] timezone:", sched.timezone)  # має бути Europe/Warsaw

    # Daily 22:00 Warsaw
    sched.add_job(
        send_daily_report,
        trigger=CronTrigger(hour=22, minute=0, timezone=WARSAW_TZ),
        args=[bot, repo, users],
        id="daily_report",
        replace_existing=True,
    )

    # Weekly Sun 20:00 Warsaw
    sched.add_job(
        send_weekly_report,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=WARSAW_TZ),
        args=[bot, repo, users],
        id="weekly_report",
        replace_existing=True,
    )

    # Monthly 1st day 09:00 Warsaw
    sched.add_job(
        send_monthly_report_for_previous_month,
        trigger=CronTrigger(day=1, hour=9, minute=0, timezone=WARSAW_TZ),
        args=[bot, repo, users],
        id="monthly_report",
        replace_existing=True,
    )

    return sched  # старт робиться в bot.py (scheduler.start())