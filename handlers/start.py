from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from repo import Repo
from services.formatting import parse_amount_to_cents, money
from handlers.common import main_kb
from config import cfg
from services.budgeting import month_bounds

router = Router()


class SetMonthlyBudget(StatesGroup):
    amount = State()


async def _ensure_bootstrap(repo: Repo, tz_name: str) -> tuple[int, int]:
    """
    Гарантує, що:
    - дефолтні категорії створені
    - на поточний місяць створені category_limits з дефолтів
    """
    await repo.ensure_default_categories()

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    mctx = month_bounds(now, tz)
    await repo.ensure_month_limits_from_category_defaults(mctx.year, mctx.month)
    return mctx.year, mctx.month


async def send_home(message: Message, repo: Repo, tz_name: str):
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)

    year, month = await _ensure_bootstrap(repo, tz_name)

    budget = await repo.get_monthly_budget(year, month)

    if budget <= 0:
        await message.answer("Введи місячний бюджет:", reply_markup=main_kb())
        return

    # month bounds for totals
    mctx = month_bounds(now, tz)
    spent = await repo.sum_month_total(mctx.start_date, mctx.end_date)
    remaining = budget - spent

    # Місяць (людська назва)
    month_name = now.strftime("%B")

    await message.answer(
        f"Активний місяць: {month_name}\n"
        f"Залишок на місяць: {money(remaining)}",
        reply_markup=main_kb(),
    )


@router.message(F.text == "/start")
@router.message(F.text == "🏠 Головний екран")
async def start_cmd(message: Message, state: FSMContext, repo: Repo, tz_name: str):
    await state.clear()

    year, month = await _ensure_bootstrap(repo, tz_name)
    budget = await repo.get_monthly_budget(year, month)

    if budget <= 0:
        await state.set_state(SetMonthlyBudget.amount)
        await message.answer("Введи місячний бюджет:", reply_markup=main_kb())
        return

    await send_home(message, repo, tz_name)


@router.message(SetMonthlyBudget.amount)
async def set_budget_amount(message: Message, state: FSMContext, repo: Repo, tz_name: str):
    cents = parse_amount_to_cents(message.text or "")
    if cents is None or cents <= 0:
        await message.answer("Введи коректну суму:")
        return

    year, month = await _ensure_bootstrap(repo, tz_name)

    # 1) зберігаємо бюджет
    await repo.set_monthly_budget(year, month, cents)

    # 2) очищаємо state ВСІМ користувачам
    for uid in cfg.users:
        await state.storage.set_state(chat=uid, user=uid, state=None)

    # 3) очищаємо локальний state
    await state.clear()

    # 4) повідомляємо обох
    for uid in cfg.users:
        if uid == message.from_user.id:
            await message.bot.send_message(
                uid,
                f"✅ Бюджет на місяць встановлено: {money(cents)}",
                reply_markup=main_kb(),
            )
        else:
            await message.bot.send_message(
                uid,
                f"ℹ️ Інший користувач встановив бюджет на місяць: {money(cents)}",
                reply_markup=main_kb(),
            )
