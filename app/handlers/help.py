from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from app.keyboards import main_menu_kb

router = Router()

HELP_TEXT = (
    "Команды naborbot:\n"
    "/start — запуск\n"
    "/help — помощь\n"
    "/link — привязать аккаунт (пришли тег)\n"
    "/profile — профиль (если аккаунтов несколько — выбор)\n\n"
    "Также можно пользоваться кнопками меню."
)

@router.message(Command("help"))
@router.message(F.text == "Помощь")
async def help_cmd(message: Message):
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())
