from __future__ import annotations

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import calendar

from repo import Repo
from services.formatting import money
from services.budgeting import safe_spend_for_day

async def build_daily_report(repo: Repo, tz: ZoneInfo, day_iso: str) -> str:
    y = int(day_iso[0:4]); m = int(day_iso[5:7]); d = int(day_iso[8:10])

    total_day = await repo.sum_by_date(day_iso)
    var_day = await repo.sum_by_date_and_kind(day_iso, "variable")

    plan_today = await safe_spend_for_day(repo, tz, day_iso)
    delta = var_day - plan_today
    res = f"🔴 {money(delta)}" if delta > 0 else f"🟢 {money(abs(delta))}"

    tomorrow = (date(y, m, d) + timedelta(days=1))
    if tomorrow.month != m:
        ss_tomorrow = 0
    else:
        ss_tomorrow = await safe_spend_for_day(repo, tz, tomorrow.isoformat())

    top2 = await repo.top_categories_in_range(day_iso, day_iso, limit=2)
    top_lines = "\n".join([f"{e} {n} — {money(s)}" for (e, n, s) in top2]) if top2 else "—"

    ddmm = f"{d:02d}.{m:02d}"
    return (
        f"📊 Daily Report ({ddmm})\n\n"
        f"Витрати за день: {money(total_day)}\n"
        f"Змінні витрати: {money(var_day)}\n\n"
        "Safe-spend:\n"
        f"План: {money(plan_today)}\n"
        f"Факт: {money(var_day)}\n"
        f"Результат: {res}\n"
        f"Safe-spend на завтра: {money(ss_tomorrow)}\n\n"
        "Топ категорії:\n"
        f"{top_lines}"
    )

async def build_weekly_report(repo: Repo, tz: ZoneInfo, now: datetime) -> str:
    today = date(now.year, now.month, now.day)
    start = today - timedelta(days=today.isoweekday() - 1)  # Monday
    end = start + timedelta(days=6)  # Sunday

    start_iso = start.isoformat()
    end_iso = end.isoformat()

    cur_total = await repo.db.conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) AS s FROM expenses WHERE spent_date>=? AND spent_date<=?",
        (start_iso, end_iso),
    )
    total = int((await cur_total.fetchone())["s"])

    cur_var = await repo.db.conn.execute(
        """
        SELECT COALESCE(SUM(e.amount_cents),0) AS s
        FROM expenses e
        JOIN categories c ON c.id=e.category_id
        WHERE e.spent_date>=? AND e.spent_date<=? AND c.kind='variable' AND c.is_active=1
        """,
        (start_iso, end_iso),
    )
    var_total = int((await cur_var.fetchone())["s"])

    plan_week = (await safe_spend_for_day(repo, tz, start_iso)) * 7
    delta = var_total - plan_week
    res = f"🔴 {money(delta)}" if delta > 0 else f"🟢 {money(abs(delta))}"

    top = await repo.top_categories_in_range(start_iso, end_iso, limit=3)
    top_lines = "\n".join([f"{e} {n} — {money(s)}" for (e, n, s) in top]) if top else "—"

    daily = await repo.daily_totals_in_range(start_iso, end_iso)
    if daily:
        max_day, max_sum = max(daily, key=lambda x: x[1])
        y = int(max_day[0:4]); m = int(max_day[5:7]); d = int(max_day[8:10])
        pricey = f"{d:02d}.{m:02d} — {money(max_sum)}"
    else:
        pricey = "—"

    return (
        "📊 Weekly Report\n\n"
        f"Витрати: {money(total)}\n"
        f"Змінні витрати: {money(var_total)}\n\n"
        "Safe-spend:\n"
        f"План: {money(plan_week)}\n"
        f"Факт: {money(var_total)}\n"
        f"Результат: {res}\n\n"
        "Топ категорії:\n"
        f"{top_lines}\n\n"
        f"Найдорожчий день: {pricey}"
    )

async def build_monthly_report(repo: Repo, tz: ZoneInfo, year: int, month: int) -> str:
    month_names = {
        1:"Січень",2:"Лютий",3:"Березень",4:"Квітень",5:"Травень",6:"Червень",
        7:"Липень",8:"Серпень",9:"Вересень",10:"Жовтень",11:"Листопад",12:"Грудень"
    }
    mname = month_names.get(month, str(month))
    days = calendar.monthrange(year, month)[1]
    start = date(year, month, 1).isoformat()
    end = (date(year, month, 1) + timedelta(days=days)).isoformat()  # exclusive

    budget = await repo.get_monthly_budget(year, month)
    total = await repo.sum_month_total(start, end)

    remaining = budget - total
    rem_icon = "🟢" if remaining >= 0 else "🔴"

    top = await repo.top_categories_in_range(start, (date(year, month, days).isoformat()), limit=5)
    top_lines = "\n".join([f"{e} {n} — {money(s)}" for (e, n, s) in top]) if top else "—"

    # Перевищення лімітів: показуємо -200 zł 🔴
    cats = await repo.list_categories()
    sums = dict(await repo.sum_month_by_category(start, end))
    over_lines = []
    for c in cats:
        if c["limit_cents"] is None:
            continue
        lim = int(c["limit_cents"])
        if lim <= 0:
            continue
        spent = sums.get(int(c["id"]), 0)
        diff = lim - spent
        if diff < 0:
            over_lines.append(f"{c['emoji']} {c['name']} — {money(diff)} 🔴")
    over_text = "\n".join(over_lines) if over_lines else "—"

    return (
        f"📅 Monthly Report — {mname}\n\n"
        f"Витрати: {money(total)}\n"
        f"{rem_icon} Залишок: {money(remaining)}\n\n"
        "Топ категорії:\n"
        f"{top_lines}\n\n"
        "Перевищення лімітів:\n"
        f"{over_text}"
    )
