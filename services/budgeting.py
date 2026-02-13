from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import calendar

from repo import Repo

@dataclass
class MonthCtx:
    year: int
    month: int
    start_date: str  # YYYY-MM-DD inclusive
    end_date: str    # YYYY-MM-DD exclusive
    days_in_month: int

def month_bounds(now: datetime, tz: ZoneInfo) -> MonthCtx:
    y, m = now.year, now.month
    days = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = start + timedelta(days=days)
    return MonthCtx(year=y, month=m, start_date=start.isoformat(), end_date=end.isoformat(), days_in_month=days)

async def planned_variable_budget_cents(repo: Repo, year: int, month: int) -> int:
    await repo.ensure_month_limits_from_category_defaults(year, month)
    limits = await repo.get_month_limits_map(year, month)
    cats = await repo.list_categories()

    total = 0
    for c in cats:
        if c["kind"] != "variable":
            continue
        lim = limits.get(int(c["id"]), c["limit_cents"])
        if lim is None:
            continue
        lim = int(lim)
        if lim > 0:
            total += lim
    return total

async def safe_spend_for_day(repo: Repo, tz: ZoneInfo, day_iso: str) -> int:
    # day_iso = YYYY-MM-DD
    y = int(day_iso[0:4]); m = int(day_iso[5:7]); d = int(day_iso[8:10])
    now = datetime(y, m, d, 12, 0, 0, tzinfo=tz)
    mctx = month_bounds(now, tz)

    planned = await planned_variable_budget_cents(repo, mctx.year, mctx.month)

    # spent variable before day_iso (month-to-date, excluding this day)
    cur = await repo.db.conn.execute(
        """
        SELECT COALESCE(SUM(e.amount_cents),0) AS s
        FROM expenses e
        JOIN categories c ON c.id=e.category_id
        WHERE e.spent_date>=? AND e.spent_date<? AND c.kind='variable' AND c.is_active=1
        """,
        (mctx.start_date, day_iso),
    )
    spent_before = int((await cur.fetchone())["s"])

    rem = (date(mctx.year, mctx.month, mctx.days_in_month) - date(mctx.year, mctx.month, d)).days + 1
    rem = max(1, rem)

    return (planned - spent_before) // rem
