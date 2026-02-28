from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, date
from zoneinfo import ZoneInfo

from repo import Repo


@dataclass
class MonthContext:
    year: int
    month: int
    start_date: str  # YYYY-MM-DD inclusive
    end_date: str    # YYYY-MM-DD exclusive


def month_bounds(now: datetime, tz: ZoneInfo) -> MonthContext:
    local = now.astimezone(tz)
    y, m = local.year, local.month
    days = calendar.monthrange(y, m)[1]
    start = date(y, m, 1).isoformat()
    end_iso = date(y, m, days).toordinal() + 1  # exclusive
    end = date.fromordinal(end_iso).isoformat()
    return MonthContext(year=y, month=m, start_date=start, end_date=end)


async def safe_spend_for_day(repo: Repo, tz: ZoneInfo, day_iso: str) -> int:
    """
    Safe-spend (оновлена логіка):
    - Fixed ліміти завжди "резервуємо" (навіть якщо їх ще не оплатили)
    - Витрати беремо "всі", але знімаємо fixed витрати (бо fixed вже врахували через резерв)

    planned_fixed = sum(fixed limits)
    spent_nonfixed_so_far = spent_total_so_far - spent_fixed_so_far

    safe_spend(day) =
        max(0, (monthly_budget - planned_fixed - spent_nonfixed_so_far) / remaining_days_including_day)

    Важливо для daily:
    - so_far беремо ДО day_iso (spent_date < day_iso), щоб план не "зʼїдав" витрати цього дня.
    """
    y = int(day_iso[0:4])
    m = int(day_iso[5:7])
    d = int(day_iso[8:10])

    monthly_budget = await repo.get_monthly_budget(y, m)
    if monthly_budget <= 0:
        return 0

    start_iso = date(y, m, 1).isoformat()

    # Суми ДО day_iso (exclusive) по категоріях
    sums_before = dict(await repo.sum_month_by_category(start_iso, day_iso))

    cats = await repo.list_categories()
    limits = await repo.get_month_limits_map(y, m)

    planned_fixed_cents = 0
    spent_total_so_far = 0
    spent_fixed_so_far = 0

    for c in cats:
        cid = int(c["id"])
        spent_cat = int(sums_before.get(cid, 0))
        spent_total_so_far += spent_cat

        kind = c["kind"]
        lim = limits.get(cid, c["limit_cents"])

        if kind == "fixed":
            spent_fixed_so_far += spent_cat
            if lim is not None:
                planned_fixed_cents += max(0, int(lim))

    spent_nonfixed_so_far = spent_total_so_far - spent_fixed_so_far

    days_in_month = calendar.monthrange(y, m)[1]
    remaining_days = max(1, days_in_month - d + 1)  # включно з day_iso

    safe_spend_cents = int(round((monthly_budget - planned_fixed_cents - spent_nonfixed_so_far) / remaining_days))
    if safe_spend_cents < 0:
        safe_spend_cents = 0

    return safe_spend_cents
