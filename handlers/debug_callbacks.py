from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()

@router.callback_query(F.data & ~F.data.startswith("cat:") & ~F.data.startswith("cmt:"))
async def any_other_callback(cb: CallbackQuery):
    await cb.answer(f"CB: {cb.data}", show_alert=True)
