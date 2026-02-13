from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from repo import Repo
from handlers.common import main_kb
from services.formatting import parse_amount_to_cents
from services.budgeting import month_bounds

router = Router()

class AddCategory(StatesGroup):
    name = State()
    emoji = State()
    kind = State()
    need_limit = State()
    limit_value = State()

def kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="fixed", callback_data="k:fixed"),
             InlineKeyboardButton(text="variable", callback_data="k:variable")]
        ]
    )

def need_limit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Так", callback_data="l:yes"),
             InlineKeyboardButton(text="Ні", callback_data="l:no")]
        ]
    )

@router.message(F.text == "➕ Додати категорію")
async def start_add_category(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AddCategory.name)
    await message.answer("Назва категорії:")

@router.message(AddCategory.name)
async def read_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        return
    await state.update_data(name=name)
    await state.set_state(AddCategory.emoji)
    await message.answer("Emoji категорії:")

@router.message(AddCategory.emoji)
async def read_emoji(message: Message, state: FSMContext):
    emoji = (message.text or "").strip()
    if not emoji:
        return
    await state.update_data(emoji=emoji)
    await state.set_state(AddCategory.kind)
    await message.answer("Тип категорії:", reply_markup=kind_kb())

@router.callback_query(AddCategory.kind, F.data.startswith("k:"))
async def read_kind(cb: CallbackQuery, state: FSMContext):
    kind = cb.data.split(":")[1]
    await state.update_data(kind=kind)
    await state.set_state(AddCategory.need_limit)
    await cb.message.answer("Чи потрібен ліміт?", reply_markup=need_limit_kb())
    await cb.answer()

@router.callback_query(AddCategory.need_limit, F.data == "l:no")
async def limit_no(cb: CallbackQuery, state: FSMContext, repo: Repo, tz_name: str):
    data = await state.get_data()
    new_id = await repo.add_category(data["name"], data["emoji"], data["kind"], None)

    # на поточний місяць теж "без ліміту"
    tz = ZoneInfo(tz_name)
    mctx = month_bounds(datetime.now(tz), tz)
    await repo.set_month_limit(mctx.year, mctx.month, new_id, None)

    await state.clear()
    await cb.message.answer("✅ Додано", reply_markup=main_kb())
    await cb.answer()

@router.callback_query(AddCategory.need_limit, F.data == "l:yes")
async def limit_yes(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddCategory.limit_value)
    await cb.message.answer("Введи ліміт (сума):")
    await cb.answer()

@router.message(AddCategory.limit_value)
async def read_limit(message: Message, state: FSMContext, repo: Repo, tz_name: str):
    cents = parse_amount_to_cents(message.text or "")
    if cents is None:
        return

    data = await state.get_data()
    new_id = await repo.add_category(data["name"], data["emoji"], data["kind"], cents)

    tz = ZoneInfo(tz_name)
    mctx = month_bounds(datetime.now(tz), tz)
    await repo.set_month_limit(mctx.year, mctx.month, new_id, cents)

    await state.clear()
    await message.answer("✅ Додано", reply_markup=main_kb())
