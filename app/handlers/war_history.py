from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.keyboards import main_menu_kb, profile_accounts_picker_inline
from app.services.cw2_history import CW2HistoryService, normalize_tag

router = Router()


def league_emoji(league: int | None) -> str:
    if league is None:
        return "🏁"
    if league >= 4000:
        return "🏆"
    if league >= 3000:
        return "🥇"
    if league >= 2000:
        return "🥈"
    if league >= 1000:
        return "🥉"
    return "🏁"


def fmt_week_line(i: int, w) -> str:
    s = f"S{w.season_id}" if w.season_id is not None else "S?"
    wk = f"W{w.week}" if w.week is not None else "W?"
    lg = f"{w.league}" if w.league is not None else "—"

    return (
        f"{i}) {league_emoji(w.league)} <b>{lg}</b>  {s}-{wk}\n"
        f"   🏅 Медали: <b>{w.medals}</b> | 🃏 Колод: <b>{w.decks_used}</b>"
    )


@router.message(Command("warhistory"))
@router.message(F.text == "Клановые войны (10 недель)")
async def warhistory_entry(message: Message, db, clash_api, cw2_history: CW2HistoryService):
    user_id = message.from_user.id
    await db.ensure_user(user_id)

    accounts = await db.list_accounts(user_id)
    if not accounts:
        await message.answer("Сначала привяжи аккаунт.", reply_markup=main_menu_kb())
        return

    if len(accounts) > 1:
        await message.answer("Выбери аккаунт:")
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

    await _send_warhistory(message, accounts[0]["tag"], db, clash_api, cw2_history)


@router.callback_query(F.data.startswith("war_open:"))
async def war_open_cb(call: CallbackQuery, db, clash_api, cw2_history: CW2HistoryService):
    tag = call.data.split(":", 1)[1]
    await _send_warhistory(call.message, tag, db, clash_api, cw2_history)
    await call.answer()


async def _send_warhistory(message: Message, player_tag: str, db, clash_api, cw2_history: CW2HistoryService):
    player_tag = normalize_tag(player_tag)

    player, err = await clash_api.get_player_with_error(player_tag)

    if not player:
        await message.answer(
            "❌ Не удалось получить профиль игрока.\n"
            f"Причина: <code>{err}</code>",
            reply_markup=main_menu_kb(),
        )
        return

    await db.cache_player_json(player_tag, player)

    clan = player.get("clan")
    if not clan or not clan.get("tag"):
        await message.answer(
            "Игрок сейчас без клана — CW2 истории нет.",
            reply_markup=main_menu_kb(),
        )
        return

    clan_tag = clan["tag"]
    clan_name = clan.get("name", "—")

    weeks = await cw2_history.get_last_10_weeks(clan_tag, player_tag)

    if not weeks:
        await message.answer(
            "CW2 история недоступна.\n"
            "• Supercell API может быть закрыт\n"
            "• RoyaleAPI может временно не отдавать лог",
            reply_markup=main_menu_kb(),
        )
        return

    lines = [
        "🛡 <b>CW2 History</b>",
        f"👤 <code>{player_tag}</code>",
        f"🏰 <b>{clan_name}</b> (<code>{clan_tag}</code>)",
        "",
        "<b>Последние 10 недель:</b>",
    ]

    for i, w in enumerate(weeks[:10], 1):
        lines.append(fmt_week_line(i, w))

    await message.answer("\n".join(lines), reply_markup=main_menu_kb())
