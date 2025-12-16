# app/handlers/war_history.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.keyboards import main_menu_kb, profile_accounts_picker_inline
from app.services.cw2_history import CW2HistoryService
from app.utils import normalize_tag

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
    await _send_warhistory(message, tag, db, clash_api, cw2_history)


@router.callback_query(F.data.startswith("war_open:"))
async def war_open_cb(call: CallbackQuery, db, clash_api, cw2_history: CW2HistoryService):
    tag = call.data.split(":", 1)[1]
    await _send_warhistory(call.message, tag, db, clash_api, cw2_history)
    await call.answer()


async def _send_warhistory(message: Message, player_tag: str, db, clash_api, cw2_history: CW2HistoryService):
    player_tag = normalize_tag(player_tag)
    if not player_tag:
        await message.answer("Тег пустой/неверный.", reply_markup=main_menu_kb())
        return

    # берём игрока
    player = await clash_api.get_player(player_tag)

    # если вернулась ошибка — покажем её
    if isinstance(player, dict) and player.get("__error__"):
        await message.answer(
            "❌ Не удалось получить профиль игрока.\n"
            f"Причина: {player.get('status')}: {player.get('body')}",
            reply_markup=main_menu_kb(),
        )
        return

    if not player:
        cached = await db.get_cached_player_json("#" + player_tag)
        if cached:
            player = cached
        else:
            await message.answer(
                "Не смог получить профиль игрока (и кеша нет).\n"
                "Попробуй ещё раз через 10–20 секунд.",
                reply_markup=main_menu_kb(),
            )
            return
    else:
        # сохраним кеш (в формате с #, чтобы единообразно)
        await db.cache_player_json("#" + player_tag, player)

    clan = player.get("clan") or {}
    clan_tag = clan.get("tag")
    clan_name = clan.get("name") or "—"

    if not clan_tag:
        await message.answer("Игрок сейчас без клана — CW2 истории нет.", reply_markup=main_menu_kb())
        return

    weeks = await cw2_history.get_last_10_weeks(clan_tag=clan_tag, player_tag="#" + player_tag)
    if not weeks:
        await message.answer(
            "Не смог получить CW2 историю.\n"
            "Обычно причины такие:\n"
            "• эндпоинт Supercell /riverracelog недоступен (404)\n"
            "• или RoyaleAPI не отдаёт war log для этого клана",
            reply_markup=main_menu_kb(),
        )
        return

    lines = [
        f"🛡 <b>CW2 History</b>",
        f"👤 Игрок: <code>#{player_tag}</code>",
        f"🏰 Клан: <b>{clan_name}</b> (<code>{clan_tag}</code>)",
        "",
        "<b>Последние 10 недель:</b>",
    ]

    for i, w in enumerate(weeks[:10], start=1):
        lines.append(fmt_week_line(i, w))

    await message.answer("\n".join(lines), reply_markup=main_menu_kb())
