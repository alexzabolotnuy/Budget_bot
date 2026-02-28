from __future__ import annotations

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from aiogram import Bot

from config import cfg
from repo import Repo
from services.reports import build_daily_report, build_weekly_report, build_monthly_report


def _tz() -> ZoneInfo:
    # Правильний прод-варіант: завжди timezone-aware "Europe/Warsaw" (або cfg.timezone)
    return ZoneInfo(getattr(cfg, "timezone", "Europe/Warsaw") or "Europe/Warsaw")


async def _send_to_all_users(bot: Bot, text: str):
    for uid in cfg.users:
        try:
            await bot.send_message(uid, text)
        except Exception:
            # Не валимо scheduler через одного юзера
            pass


async def send_daily_report(bot: Bot, repo: Repo):
    tz = _tz()
    now = datetime.now(tz)
    day_iso = now.date().isoformat()

    text = await build_daily_report(repo, tz, day_iso)
    await _send_to_all_users(bot, text)


async def send_weekly_report(bot: Bot, repo: Repo):
    tz = _tz()
    now = datetime.now(tz)

    text = await build_weekly_report(repo, tz, now)
    await _send_to_all_users(bot, text)


async def send_monthly_report_for_previous_month(bot: Bot, repo: Repo):
    """
    Відправляємо місячний репорт за попередній місяць на 1 число.
    Наприклад, 1 березня -> репорт за лютий.
    """
    tz = _tz()
    now = datetime.now(tz)
    first_day = date(now.year, now.month, 1)
    prev_last_day = first_day - timedelta(days=1)

    y = prev_last_day.year
    m = prev_last_day.month

    text = await build_monthly_report(repo, tz, y, m)
    await _send_to_all_users(bot, text)


def setup_scheduler(bot: Bot, repo: Repo) -> AsyncIOScheduler:
    tz = _tz()

    sched = AsyncIOScheduler(timezone=tz)

    # Daily report (22:00 Warsaw) - приклад
    sched.add_job(
        send_daily_report,
        trigger=CronTrigger(hour=22, minute=0, timezone=tz),
        args=[bot, repo],
        id="daily_report",
        replace_existing=True,
    )

    # Weekly report (Sunday 20:00 Warsaw) - приклад
    sched.add_job(
        send_weekly_report,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=tz),
        args=[bot, repo],
        id="weekly_report",
        replace_existing=True,
    )

    # Monthly report (1st day 09:00 Warsaw) - приклад
    sched.add_job(
        send_monthly_report_for_previous_month,
        trigger=CronTrigger(day=1, hour=9, minute=0, timezone=tz),
        args=[bot, repo],
        id="monthly_report",
        replace_existing=True,
    )

    sched.start()
    return sched