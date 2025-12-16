import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from app.keyboards import main_menu_kb
from app.services.upgrade_image import render_upgrade_image

router = Router()


@router.message(Command("upgrade"))
@router.message(F.text == "Прокачка (картинкой)")
async def upgrade_image_entry(message: Message, db, clash_api):
    user_id = message.from_user.id
    await db.ensure_user(user_id)

    accounts = await db.list_accounts(user_id)
    if not accounts:
        await message.answer(
            "Сначала привяжи аккаунт, потом смогу построить картинку прокачки.",
            reply_markup=main_menu_kb()
        )
        return

    # если аккаунт один — берём его, если несколько — позже сделаем выбор как в профиле
    tag = accounts[0]["tag"]

    player = await clash_api.get_player(tag)
    if not player:
        cached = await db.get_cached_player_json(tag)
        if cached:
            player = cached
        else:
            await message.answer("API временно недоступен и кеша нет.", reply_markup=main_menu_kb())
            return

    # сохраним кеш
    await db.cache_player_json(tag, player)

    out_path = os.path.join("cache", "renders", f"upgrade_{tag.replace('#','')}.png")
    await render_upgrade_image(player, out_path=out_path)

    await message.answer_photo(
        photo=FSInputFile(out_path),
        caption="📈 Прокачка карт (картинкой)",
        reply_markup=main_menu_kb()
    )
