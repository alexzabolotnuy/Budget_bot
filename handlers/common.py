from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Головний екран")],
            [KeyboardButton(text="➕ Додати витрату"), KeyboardButton(text="📊 Стан бюджету")],
            [KeyboardButton(text="➕ Додати категорію"), KeyboardButton(text="✏️ Ліміти")],
            [KeyboardButton(text="💰 Змінити бюджет")],
        ],
        resize_keyboard=True,
    )
