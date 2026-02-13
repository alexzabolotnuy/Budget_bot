from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from repo import Repo
from services.formatting import parse_amount_to_cents

router = Router()

@router.message()
async def catch_monthly_budget_if_needed(message: Message, repo: Repo):
    # Мінімальний “перший запуск”: якщо monthly_budget=0, перший числовий ввід = бюджет
    chat_id = message.chat.id
    settings = await repo.get_settings(chat_id)
    if not settings:
        return

    if int(settings["monthly_budget_cents"]) != 0:
        return

    cents = parse_amount_to_cents(message.text or "")
    if cents is None:
        return

    await repo.set_monthly_budget(chat_id, cents)
    # Після вводу бюджету просто покажемо /start екран
    await message.answer("✅ Збережено")
