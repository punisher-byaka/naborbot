from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> ReplyKeyboardMarkup:
    """
    Главное меню (reply-клавиатура).
    Добавил кнопку для CW2 истории.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Профиль"), KeyboardButton(text="Привязать аккаунт")],
            [KeyboardButton(text="Прокачка (картинкой)")],
            [KeyboardButton(text="Клановые войны (10 недель)")],
            [KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
        selective=True,
    )


def profile_accounts_picker_inline(
    accounts: list[dict],
    prefix: str = "profile_open:",
    allow_unlink: bool = True,
    allow_link_more: bool = True,
) -> InlineKeyboardMarkup:
    """
    Универсальный выбор аккаунта.
    - prefix: для callback_data (например "profile_open:" или "war_open:")
    - allow_unlink: показывать кнопку отвязки
    - allow_link_more: показывать кнопку "привязать ещё"
    """
    b = InlineKeyboardBuilder()

    for a in accounts:
        name = (a.get("name") or "").strip() or "Без ника"
        tag = a.get("tag") or ""

        # Кнопка выбора
        b.button(text=f"{name}  {tag}", callback_data=f"{prefix}{tag}")

        # Кнопка отвязки (только для профиля — но можно выключить)
        if allow_unlink:
            b.button(text=f"🗑 Отвязать {tag}", callback_data=f"profile_unlink:{tag}")

    if allow_link_more:
        b.button(text="➕ Привязать ещё", callback_data="profile_link")

    b.adjust(1)
    return b.as_markup()


def profile_single_manage_inline(tag: str) -> InlineKeyboardMarkup:
    """
    Кнопки под профилем одного аккаунта.
    """
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Перепривязать", callback_data="profile_link")
    b.button(text=f"🗑 Отвязать {tag}", callback_data=f"profile_unlink:{tag}")
    b.adjust(1)
    return b.as_markup()
