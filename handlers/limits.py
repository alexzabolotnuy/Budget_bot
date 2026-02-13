from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from repo import Repo
from handlers.common import main_kb
from services.formatting import parse_amount_to_cents, money
from services.budgeting import month_bounds

router = Router()

# --- inline keyboards ---
def categories_pick_kb(categories) -> InlineKeyboardMarkup:
    rows = []
    for c in categories:
        rows.append([InlineKeyboardButton(text=f"{c['emoji']} {c['name']}", callback_data=f"lim:pick:{c['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def reuse_limits_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Так", callback_data="mlim:reuse:yes"),
                InlineKeyboardButton(text="Ні", callback_data="mlim:reuse:no"),
            ]
        ]
    )

# --- FSM ---
class EditLimit(StatesGroup):
    waiting_amount = State()

class MonthLimitsWizard(StatesGroup):
    waiting_amount = State()

# state payload keys:
# - year, month
# - cat_ids: list[int]
# - idx: int

async def _current_year_month(repo: Repo, tz_name: str) -> tuple[int, int]:
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    mctx = month_bounds(now, tz)
    await repo.ensure_month_limits_from_category_defaults(mctx.year, mctx.month)
    return mctx.year, mctx.month

# --- UI: edit limit ---
@router.message(F.text == "✏️ Ліміти")
async def limits_menu(message: Message, state: FSMContext, repo: Repo, tz_name: str):
    await state.clear()
    year, month = await _current_year_month(repo, tz_name)
    cats = await repo.list_categories()
    await message.answer("Обери категорію:", reply_markup=categories_pick_kb(cats))
    await state.update_data(year=year, month=month)

@router.callback_query(F.data.startswith("lim:pick:"))
async def pick_category(cb: CallbackQuery, state: FSMContext, repo: Repo):
    data = await state.get_data()
    year = int(data["year"]); month = int(data["month"])
    category_id = int(cb.data.split(":")[2])
    cat = await repo.get_category(category_id)

    await state.clear()
    await state.set_state(EditLimit.waiting_amount)
    await state.update_data(year=year, month=month, category_id=category_id)

    await cb.message.answer(
        f"{cat['emoji']} {cat['name']} — введи ліміт (0 = без ліміту):",
        reply_markup=main_kb()
    )
    await cb.answer()

@router.message(EditLimit.waiting_amount)
async def set_limit_amount(message: Message, state: FSMContext, repo: Repo):
    cents = parse_amount_to_cents(message.text or "")
    if cents is None:
        await message.answer("Введи ліміт (0 = без ліміту):", reply_markup=main_kb())
        return

    data = await state.get_data()
    year = int(data["year"]); month = int(data["month"]); category_id = int(data["category_id"])

    limit = None if cents == 0 else cents
    await repo.set_month_limit(year, month, category_id, limit)

    await state.clear()
    await message.answer("✅ Збережено", reply_markup=main_kb())

# --- Month start: reuse or new limits flow ---
@router.callback_query(F.data.startswith("mlim:reuse:"))
async def month_limits_reuse_choice(cb: CallbackQuery, state: FSMContext, repo: Repo, tz_name: str):
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    year, month = now.year, now.month

    choice = cb.data.split(":")[2]
    if choice == "yes":
        # copy from prev month
        prev = (now.replace(day=1).date() - __import__("datetime").timedelta(days=1))
        await repo.copy_limits_from_prev_month(year, month, prev.year, prev.month)
        await state.clear()
        await cb.message.answer("✅ Ліміти застосовано", reply_markup=main_kb())
        await cb.answer()
        return

    # choice == "no" -> wizard
    cats = await repo.list_categories()
    cat_ids = [int(c["id"]) for c in cats]

    await state.clear()
    await state.set_state(MonthLimitsWizard.waiting_amount)
    await state.update_data(year=year, month=month, cat_ids=cat_ids, idx=0)

    first = await repo.get_category(cat_ids[0])
    await cb.message.answer(f"{first['emoji']} {first['name']} — введи ліміт (0 = без ліміту):", reply_markup=main_kb())
    await cb.answer()

@router.message(MonthLimitsWizard.waiting_amount)
async def month_limits_wizard_amount(message: Message, state: FSMContext, repo: Repo):
    cents = parse_amount_to_cents(message.text or "")
    if cents is None:
        await message.answer("Введи ліміт (0 = без ліміту):", reply_markup=main_kb())
        return

    data = await state.get_data()
    year = int(data["year"]); month = int(data["month"])
    cat_ids = list(map(int, data["cat_ids"]))
    idx = int(data["idx"])

    category_id = cat_ids[idx]
    limit = None if cents == 0 else cents
    await repo.set_month_limit(year, month, category_id, limit)

    idx += 1
    if idx >= len(cat_ids):
        await state.clear()
        await message.answer("✅ Ліміти на місяць збережено", reply_markup=main_kb())
        return

    await state.update_data(idx=idx)
    nxt = await repo.get_category(cat_ids[idx])
    await message.answer(f"{nxt['emoji']} {nxt['name']} — введи ліміт (0 = без ліміту):", reply_markup=main_kb())


# helper for scheduler message (no handler here; scheduler just sends keyboard)
def month_limits_reuse_prompt_text() -> str:
    return "Перевикористовувати ліміти з минулого місяця?"
def month_limits_reuse_prompt_kb() -> InlineKeyboardMarkup:
    return reuse_limits_kb()
