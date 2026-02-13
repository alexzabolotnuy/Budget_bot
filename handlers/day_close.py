from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from repo import Repo
from handlers.expenses import start_add_expense_flow

router = Router()


def close_day_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Додати витрати", callback_data="day:add"),
                InlineKeyboardButton(text="✅ Закрити день", callback_data="day:close"),
            ]
        ]
    )


@router.callback_query(F.data == "day:close")
async def close_day_pressed(cb: CallbackQuery, repo: Repo, tz_name: str):
    """
    ✅ Закрити день:
    - записуємо натискання
    - відповідаємо "✅ Прийнято"
    - прибираємо інлайн-кнопки з цього повідомлення
    """
    tz = ZoneInfo(tz_name)
    day_iso = datetime.now(tz).date().isoformat()
    user_id = cb.from_user.id

    await repo.record_user_close(day_iso, user_id, datetime.now(tz).isoformat())

    await cb.message.answer("✅ Прийнято")

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await cb.answer()


@router.callback_query(F.data == "day:add")
async def add_expense_from_close_day(cb: CallbackQuery, state):
    """
    ➕ Додати витрати з повідомлення закриття дня:
    запускаємо стандартний flow з прапорцем from_close_day=True,
    щоб після завершення бот знову спитав "Чи закриваємо день?"
    """
    await cb.answer()
    await start_add_expense_flow(cb.message, state, from_close_day=True)
