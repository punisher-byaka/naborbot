from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from app.keyboards import main_menu_kb

router = Router()

@router.message(CommandStart())
async def start(message: Message, db):
    await db.ensure_user(message.from_user.id)
    await message.answer(
        "Привет! Я naborbot.\n\n"
        "Чтобы показать профиль, привяжи аккаунт Clash Royale.\n"
        "Пришли тег аккаунта (пример: #2ABC9PQ). Можно без #.",
        reply_markup=main_menu_kb()
    )
