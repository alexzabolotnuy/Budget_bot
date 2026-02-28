from __future__ import annotations

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from services.reports import build_daily_report, build_weekly_report, build_monthly_report


def _resolve_tz(tz_name: str | None) -> ZoneInfo:
    return ZoneInfo(tz_name or "Europe/Warsaw")


async def _send_to_users(bot: Bot, users: list[int], text: str):
    for uid in users:
        try:
            await bot.send_message(uid, text)
        except Exception:
            pass


async def send_daily_report(bot: Bot, repo, tz: ZoneInfo, users: list[int]):
    now = datetime.now(tz)
    day_iso = now.date().isoformat()
    text = await build_daily_report(repo, tz, day_iso)
    await _send_to_users(bot, users, text)


async def send_weekly_report(bot: Bot, repo, tz: ZoneInfo, users: list[int]):
    now = datetime.now(tz)
    text = await build_weekly_report(repo, tz, now)
    await _send_to_users(bot, users, text)


async def send_monthly_report_for_previous_month(bot: Bot, repo, tz: ZoneInfo, users: list[int]):
    now = datetime.now(tz)
    first_day = date(now.year, now.month, 1)
    prev_last_day = first_day - timedelta(days=1)
    y = prev_last_day.year
    m = prev_last_day.month
    text = await build_monthly_report(repo, tz, y, m)
    await _send_to_users(bot, users, text)


def setup_scheduler(
    bot: Bot,
    repo,
    tz_name: str | None = None,
    users: list[int] | None = None,
    storage=None,  # сумісність з bot.py
) -> AsyncIOScheduler:
    tz = _resolve_tz(tz_name)
    users = users or []

    sched = AsyncIOScheduler(timezone=tz)

    print("[SCHED] timezone:", sched.timezone)

    sched.add_job(
        send_daily_report,
        trigger=CronTrigger(hour=22, minute=0, timezone=tz),
        args=[bot, repo, tz, users],
        id="daily_report",
        replace_existing=True,
    )

    sched.add_job(
        send_weekly_report,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=tz),
        args=[bot, repo, tz, users],
        id="weekly_report",
        replace_existing=True,
    )

    sched.add_job(
        send_monthly_report_for_previous_month,
        trigger=CronTrigger(day=1, hour=9, minute=0, timezone=tz),
        args=[bot, repo, tz, users],
        id="monthly_report",
        replace_existing=True,
    )

    # НЕ запускаємо тут. Запуск у bot.py (scheduler.start())
    return sched