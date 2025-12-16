from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.keyboards import main_menu_kb, profile_accounts_picker_inline
from app.utils import normalize_player_tag
from app.services.cw2_history import CW2HistoryService, CW2WeekEntry

router = Router()


def fmt_line(w: CW2WeekEntry) -> str:
    season = w.season_id if w.season_id is not None else "?"
    week = w.week if w.week is not None else "?"
    return f"{season}-{week} 🏅{w.medals} ⚔️ {w.decks_used}"


@router.message(Command("warhistory"))
@router.message(F.text == "Клановые войны (10 недель)")
async def warhistory_entry(message: Message, db, cw2_history: CW2HistoryService):
    user_id = message.from_user.id
    await db.ensure_user(user_id)

    accounts = await db.list_accounts(user_id)
    if not accounts:
        await message.answer("Сначала привяжи аккаунт (нужен тег игрока).", reply_markup=main_menu_kb())
        return

    if len(accounts) > 1:
        await message.answer("Выбери аккаунт:", reply_markup=main_menu_kb())
        await message.answer(
            "Аккаунты:",
            reply_markup=profile_accounts_picker_inline(
                accounts,
                prefix="war_open:",
                allow_unlink=False,
                allow_link_more=False,
            ),
        )
        return

    tag = accounts[0]["tag"]
    await _send_warhistory(message, tag, cw2_history)


@router.callback_query(F.data.startswith("war_open:"))
async def war_open_cb(call: CallbackQuery, cw2_history: CW2HistoryService):
    tag = call.data.split(":", 1)[1]
    await _send_warhistory(call.message, tag, cw2_history)
    await call.answer()


async def _send_warhistory(message: Message, player_tag: str, cw2_history: CW2HistoryService):
    player_tag = normalize_player_tag(player_tag)

    weeks = await cw2_history.get_last_10_weeks_player(player_tag)
    if not weeks:
        await message.answer(
            "Не смог получить историю CW2 игрока.\n"
            "Если профиль/лог закрыт на RoyaleAPI или страница недоступна — данных не будет.",
            reply_markup=main_menu_kb(),
        )
        return

    lines = ["<b>История клановых войн:</b>"]

    # печатаем “клан-строка”, а потом одну/несколько недель под ним,
    # как в твоём примере. Если клан меняется — выводим новый заголовок.
    last_clan_key = None
    for w in weeks:
        clan_key = (w.clan_name, w.clan_tag)
        if clan_key != last_clan_key:
            lines.append(f"{w.clan_name} <code>{w.clan_tag}</code>")
            last_clan_key = clan_key
        lines.append(fmt_line(w))

    await message.answer("\n".join(lines), reply_markup=main_menu_kb())
