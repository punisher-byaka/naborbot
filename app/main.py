import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import load_config
from app.db import Database
from app.services.clash_api import ClashApi
from app.services.cw2_history import CW2HistoryService
from app.handlers import setup_routers


def run():
    asyncio.run(main())


async def main():
    cfg = load_config()

    # ---------- DB ----------
    db = Database(cfg.db_path)
    await db.init()

    # ---------- BOT ----------
    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # ---------- SERVICES ----------
    # Supercell API (профиль, прокачка и т.п.)
    clash_api = ClashApi(
        token=cfg.clash_api_token,
        base_url=cfg.clash_api_base,
    )

    # CW2 history (ТОЛЬКО RoyaleAPI, без Supercell)
    cw2_history = CW2HistoryService(timeout=12.0)

    # ---------- DEPENDENCIES ----------
    dp["db"] = db
    dp["clash_api"] = clash_api
    dp["cw2_history"] = cw2_history

    # ---------- ROUTERS ----------
    dp.include_router(setup_routers())

    # ---------- RUN ----------
    try:
        await dp.start_polling(bot)
    finally:
        await clash_api.close()
