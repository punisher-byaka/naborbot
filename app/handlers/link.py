from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from app.keyboards import main_menu_kb
from app.utils import normalize_player_tag, is_valid_tag

router = Router()

@router.message(Command("link"))
@router.message(F.text == "Привязать аккаунт")
async def link_start(message: Message, db):
    await db.ensure_user(message.from_user.id)
    await message.answer(
        "Ок! Пришли тег аккаунта Clash Royale.\n"
        "Пример: #2ABC9PQ (можно без #).",
        reply_markup=main_menu_kb()
    )

@router.message(F.text.regexp(r"^#?[A-Za-z0-9 ]{3,20}$"))
async def try_link_by_tag(message: Message, db, clash_api):
    """
    Если сообщение похоже на тег — пробуем привязать.
    Это позволяет вводить тег сразу после /start или после кнопки.
    """
    user_id = message.from_user.id
    raw = message.text or ""
    tag = normalize_player_tag(raw)

    if not is_valid_tag(tag):
        return

    await db.ensure_user(user_id)

    cnt = await db.count_accounts(user_id)
    if cnt >= 5:
        await message.answer(
            "Лимит — 5 аккаунтов на один Telegram.\n"
            "Если нужно больше — напиши владельцу бота.",
            reply_markup=main_menu_kb()
        )
        return

    player = await clash_api.get_player(tag)
    if not player:
        await message.answer(
            "❌ Игрок не найден.\n\n"
            "Проверь тег:\n"
            "• в тегах НЕТ буквы O — используется цифра 0\n"
            "• лучше скопируй тег прямо из игры\n\n"
            "Пример: #2ABC9PQ"
    )
        return


    name = player.get("name", "Без ника")
    await db.add_account(user_id, tag, name)

    await message.answer(
        f"✅ Аккаунт привязан:\n"
        f"Ник: {name}\n"
        f"Тег: #{tag}\n\n"
        f"Жми «Профиль».",
        reply_markup=main_menu_kb()
    )
