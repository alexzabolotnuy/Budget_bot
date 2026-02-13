from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from repo import Repo
from services.formatting import parse_amount_to_cents, money
from handlers.common import main_kb

router = Router()


class AddExpense(StatesGroup):
    date_choice = State()
    date_text = State()
    amount = State()
    category = State()
    comment_choice = State()
    comment_text = State()


def date_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Сьогодні", callback_data="dt:today"),
                InlineKeyboardButton(text="🗓 Інший день", callback_data="dt:other"),
            ]
        ]
    )


def categories_kb(categories) -> InlineKeyboardMarkup:
    rows = []
    for c in categories:
        rows.append([InlineKeyboardButton(text=f"{c['emoji']} {c['name']}", callback_data=f"cat:{c['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def comment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ні", callback_data="cmt:no"),
                InlineKeyboardButton(text="✍️ Додати", callback_data="cmt:yes"),
            ]
        ]
    )


def _parse_ddmmyyyy(s: str) -> str | None:
    s = (s or "").strip()
    try:
        dt = datetime.strptime(s, "%d.%m.%Y")
        return dt.date().isoformat()  # YYYY-MM-DD
    except Exception:
        return None


async def _finish_flow(message: Message, state: FSMContext):
    """
    Завершення флоу:
    - якщо додавання було з "Чи закриваємо день?" -> знов питаємо "Чи закриваємо день?"
    - інакше -> показуємо меню
    """
    data = await state.get_data()
    from_close_day = bool(data.get("from_close_day"))

    await state.clear()

    if from_close_day:
        # локально, щоб уникати циклічних імпортів
        from handlers.day_close import close_day_kb
        await message.answer("Чи закриваємо день?", reply_markup=close_day_kb())
    else:
        await message.answer("Готово ✅", reply_markup=main_kb())


async def start_add_expense_flow(message: Message, state: FSMContext, from_close_day: bool = False):
    """
    Єдиний старт флоу додавання витрати.
    Перший крок: вибір дати.
    """
    await state.clear()
    await state.update_data(from_close_day=from_close_day)
    await state.set_state(AddExpense.date_choice)
    await message.answer("За який день додаємо витрату?", reply_markup=date_choice_kb())


@router.message(F.text == "➕ Додати витрату")
async def add_expense_start(message: Message, state: FSMContext):
    await start_add_expense_flow(message, state, from_close_day=False)


# ---------- DATE ----------

@router.callback_query(AddExpense.date_choice, F.data == "dt:today")
async def pick_today(cb: CallbackQuery, state: FSMContext, tz_name: str):
    tz = ZoneInfo(tz_name)
    spent_date = datetime.now(tz).date().isoformat()

    await state.update_data(spent_date=spent_date)
    await state.set_state(AddExpense.amount)

    await cb.message.answer("Введи суму витрати:")
    await cb.answer()


@router.callback_query(AddExpense.date_choice, F.data == "dt:other")
async def pick_other(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddExpense.date_text)
    await cb.message.answer("Введи дату: DD.MM.YYYY")
    await cb.answer()


@router.message(AddExpense.date_text)
async def set_date_text(message: Message, state: FSMContext):
    spent_date = _parse_ddmmyyyy(message.text or "")
    if not spent_date:
        await message.answer("Введи дату у форматі DD.MM.YYYY")
        return

    await state.update_data(spent_date=spent_date)
    await state.set_state(AddExpense.amount)
    await message.answer("Введи суму витрати:")


# ---------- AMOUNT + CATEGORY ----------

@router.message(AddExpense.amount)
async def add_expense_amount(message: Message, state: FSMContext, repo: Repo):
    cents = parse_amount_to_cents(message.text or "")
    if cents is None or cents <= 0:
        await message.answer("Введи коректну суму:")
        return

    await state.update_data(amount_cents=cents)
    await state.set_state(AddExpense.category)

    cats = await repo.list_categories()
    await message.answer("Куди віднести витрату?", reply_markup=categories_kb(cats))


@router.callback_query(AddExpense.category, F.data.startswith("cat:"))
async def add_expense_category(cb: CallbackQuery, state: FSMContext, repo: Repo, tz_name: str):
    data = await state.get_data()

    amount_cents = int(data["amount_cents"])
    spent_date = str(data["spent_date"])  # YYYY-MM-DD

    category_id = int(cb.data.split(":", 1)[1])
    cat = await repo.get_category(category_id)

    tz = ZoneInfo(tz_name)
    created_at = datetime.now(tz).isoformat()

    expense_id = await repo.add_expense(
        amount_cents=amount_cents,
        category_id=category_id,
        spent_date=spent_date,
        created_at_iso=created_at,
        comment=None,
    )

    await cb.message.answer(f"✅ Додано: {money(amount_cents)} → {cat['name']}")
    await cb.message.answer("Хочеш додати коментар?", reply_markup=comment_kb())

    await state.update_data(expense_id=expense_id)
    await state.set_state(AddExpense.comment_choice)
    await cb.answer()


# ---------- COMMENT ----------

@router.callback_query(AddExpense.comment_choice, F.data == "cmt:no")
async def comment_no(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await _finish_flow(cb.message, state)


@router.callback_query(AddExpense.comment_choice, F.data == "cmt:yes")
async def comment_yes(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Введи коментар:")
    await state.set_state(AddExpense.comment_text)
    await cb.answer()


@router.message(AddExpense.comment_text)
async def comment_text(message: Message, state: FSMContext, repo: Repo):
    data = await state.get_data()
    expense_id = int(data["expense_id"])
    text = (message.text or "").strip()

    if text:
        await repo.set_expense_comment(expense_id, text)
        await message.answer("💬 Коментар додано")

    await _finish_flow(message, state)
