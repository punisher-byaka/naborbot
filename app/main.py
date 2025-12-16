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

    db = Database(cfg.db_path)
    await db.init()

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    clash_api = ClashApi(cfg.clash_api_token, cfg.clash_api_base)

    cw2_history = CW2HistoryService(
        supercell_base=cfg.clash_api_base,
        supercell_token=cfg.clash_api_token,
        timeout=12.0,
    )

    dp["db"] = db
    dp["clash_api"] = clash_api
    dp["cw2_history"] = cw2_history

    dp.include_router(setup_routers())

    try:
        await dp.start_polling(bot)
    finally:
        await clash_api.close()
