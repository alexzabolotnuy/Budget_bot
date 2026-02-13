from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from repo import Repo
from services.budgeting import month_bounds
from services.formatting import money, bar_squares_5

router = Router()

MONTH_NAMES_UA = {
    1: "Січень", 2: "Лютий", 3: "Березень", 4: "Квітень", 5: "Травень", 6: "Червень",
    7: "Липень", 8: "Серпень", 9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень"
}


@router.message(F.text == "📊 Стан бюджету")
async def budget_status(message: Message, state: FSMContext, repo: Repo, tz_name: str):
    # глобальна кнопка має перебивати будь-який flow
    await state.clear()

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    mctx = month_bounds(now, tz)

    # гарантуємо, що ліміти місяця існують
    await repo.ensure_month_limits_from_category_defaults(mctx.year, mctx.month)

    cats = await repo.list_categories()
    sums_list = await repo.sum_month_by_category(mctx.start_date, mctx.end_date)
    sums = {cid: s for (cid, s) in sums_list}
    limits = await repo.get_month_limits_map(mctx.year, mctx.month)

    month_name = MONTH_NAMES_UA.get(mctx.month, str(mctx.month))

    # ---------- DETAILS FIRST ----------
    detail_lines: list[str] = [f"📊 {month_name} — стан бюджету", ""]

    exceeded = 0

    for c in cats:
        cid = int(c["id"])
        spent = int(sums.get(cid, 0))

        lim = limits.get(cid, c["limit_cents"])
        emoji = c["emoji"]
        name = c["name"]

        # Назва категорії (рядок 1)
        detail_lines.append(f"{emoji} {name}")

        if lim is None:
            # Без ліміту (як у тебе було)
            detail_lines.append(f"{money(spent)} (без ліміту)")
            detail_lines.append("")
            continue

        lim = int(lim)
        remaining = lim - spent

        if lim > 0 and spent > lim:
            exceeded += 1

        # Рядок 2: spent/limit + BAR + remaining + статус (як на твоєму скріні)
        # Бар на 5 квадратів
        p = 0.0 if lim <= 0 else (spent / lim)
        bar = bar_squares_5(p)

        status = "🔴" if remaining < 0 else "🟢"
        # показуємо remaining як є (може бути відʼємний)
        detail_lines.append(
            f"{money(spent)} / {money(lim)}  {bar}  {money(remaining)} {status}"
        )

        detail_lines.append("")

    await message.answer("\n".join(detail_lines).rstrip())

    # ---------- SUMMARY SECOND ----------
    budget = await repo.get_monthly_budget(mctx.year, mctx.month)
    spent_total = await repo.sum_month_total(mctx.start_date, mctx.end_date)
    remaining_total = budget - spent_total

    top_items = []
    for c in cats:
        cid = int(c["id"])
        spent = int(sums.get(cid, 0))
        if spent > 0:
            top_items.append((spent, c["emoji"], c["name"]))
    top_items.sort(key=lambda x: x[0], reverse=True)
    top_items = top_items[:5]

    summary_lines = [
        f"📊 Summary {month_name}",
        "",
        f"Залишок на місяць: {money(remaining_total)}",
        "",
        "Топ витрати:",
    ]

    if top_items:
        for spent, emoji, name in top_items:
            summary_lines.append(f"{emoji} {name} — {money(spent)}")
    else:
        summary_lines.append("— (поки витрат немає)")

    summary_lines.append("")
    summary_lines.append(f"Перевищено: {exceeded} 🔴")

    await message.answer("\n".join(summary_lines).rstrip())
