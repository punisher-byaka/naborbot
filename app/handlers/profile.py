from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.keyboards import (
    main_menu_kb,
    profile_accounts_picker_inline,
    profile_single_manage_inline,
)

router = Router()


def role_ru(role: str | None) -> str:
    mapping = {
        "leader": "Глава",
        "coLeader": "Соруководитель",
        "elder": "Старейшина",
        "member": "Участник",
    }
    return mapping.get(role or "", role or "—")


def safe_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def display_level(card: dict) -> int | None:
    """
    Реальный уровень карты (как в игре / RoyaleAPI):
    display = level + (16 - maxLevel)
    """
    lv = card.get("level")
    mx = card.get("maxLevel")
    if isinstance(lv, int) and isinstance(mx, int) and mx > 0:
        return lv + (16 - mx)
    return None


def count_display_levels(cards: list[dict]) -> dict[int, int]:
    levels: dict[int, int] = {}
    for c in cards or []:
        dl = display_level(c)
        if isinstance(dl, int):
            levels[dl] = levels.get(dl, 0) + 1
    return levels


def format_levels(levels: dict[int, int], total_cards: int) -> list[str]:
    out: list[str] = []
    for lv in sorted(levels.keys(), reverse=True):
        cnt = levels[lv]
        pct = (cnt / total_cards * 100) if total_cards else 0.0
        out.append(f"{lv}лвл - <b>{cnt}</b> ({pct:.2f}%)")
    return out


def build_profile_text(player: dict) -> str:
    name = player.get("name", "Без ника")
    tag = player.get("tag", "")

    trophies = safe_int(player.get("trophies"))
    best = safe_int(player.get("bestTrophies"))
    exp = player.get("expLevel")

    wins = safe_int(player.get("wins"))
    losses = safe_int(player.get("losses"))
    battle_count = safe_int(player.get("battleCount"))
    winrate = (wins / battle_count * 100) if battle_count else 0.0

    clan = player.get("clan")
    clan_name = clan.get("name") if clan else None
    clan_tag = clan.get("tag") if clan else None
    clan_role = role_ru(player.get("role") or (clan.get("role") if clan else None))

    cards = player.get("cards", []) or []
    cards_count = len(cards)

    # ✅ ПРОКАЧКА: считаем по display_level (как в игре)
    levels = count_display_levels(cards)
    levels_lines = format_levels(levels, cards_count)

    # ✅ БАШЕННЫЕ КАРТЫ (Tower Troops)
    support_cards = player.get("supportCards", []) or []

    # ✅ ГЕРОИ: это карты с heroMedium
    hero_cards = [c for c in cards if (c.get("iconUrls") or {}).get("heroMedium")]

    # ✅ ЭВОЛЮЦИИ: открытые — evolutionLevel > 0
    evo_cards_owned = [c for c in cards if safe_int(c.get("evolutionLevel"), 0) > 0]

    lines: list[str] = [
        f"👤 <b>{name}</b>",
        f"🏷 Тег: <code>{tag}</code>" if tag else "",
        "",
        f"🏆 Трофеи: <b>{trophies}</b> (best: {best})",
        f"👑 Уровень (exp): <b>{exp}</b>" if exp is not None else "",
        f"⚔️ Бои: <b>{battle_count}</b> | Победы: <b>{wins}</b> | Поражения: <b>{losses}</b>",
        f"📊 Процент побед: <b>{winrate:.2f}%</b>",
        "",
    ]

    if clan_name:
        lines += [
            f"🏰 Клан: <b>{clan_name}</b> ({clan_tag})",
            f"🎖 Роль: <b>{clan_role}</b>",
            "",
        ]
    else:
        lines += ["🏰 Клан: —", ""]

    lines += [
        f"🃏 Открыто карт: <b>{cards_count}</b>",
        "📈 Количество прокачанных карт (как в игре):",
        *levels_lines,
        "",
        f"🗼 Башенные карты: <b>{len(support_cards)}</b>",
        f"🦸 Герои (hero cards): <b>{len(hero_cards)}</b>",
        f"✨ Эволюции (открытые): <b>{len(evo_cards_owned)}</b>",
    ]

    return "\n".join([x for x in lines if x != ""])


@router.message(Command("profile"))
@router.message(F.text == "Профиль")
async def profile_entry(message: Message, db, clash_api):
    user_id = message.from_user.id
    await db.ensure_user(user_id)

    accounts = await db.list_accounts(user_id)
    if not accounts:
        await message.answer(
            "У тебя ещё нет привязанного аккаунта.\n"
            "Нажми «Привязать аккаунт» и пришли тег.",
            reply_markup=main_menu_kb(),
        )
        return

    if len(accounts) == 1:
        tag = accounts[0]["tag"]
        await _send_profile_message(message, tag, db=db, clash_api=clash_api, user_id=user_id)
        return

    await message.answer("Выбери аккаунт:", reply_markup=main_menu_kb())
    await message.answer("Аккаунты:", reply_markup=profile_accounts_picker_inline(accounts))


@router.callback_query(F.data.startswith("profile_open:"))
async def profile_open_cb(call: CallbackQuery, db, clash_api):
    user_id = call.from_user.id
    tag = call.data.split(":", 1)[1]
    await _send_profile_callback(call, tag, db=db, clash_api=clash_api, user_id=user_id)


@router.callback_query(F.data == "profile_link")
async def profile_link_cb(call: CallbackQuery):
    await call.message.answer(
        "Пришли тег аккаунта Clash Royale для привязки.\nПример: #2ABC9PQ (можно без #).",
        reply_markup=main_menu_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("profile_unlink:"))
async def profile_unlink_cb(call: CallbackQuery, db):
    user_id = call.from_user.id
    tag = call.data.split(":", 1)[1]
    ok = await db.remove_account(user_id, tag)

    await call.message.answer(
        f"🗑 Аккаунт #{tag} отвязан." if ok else "Не смог найти эту привязку.",
        reply_markup=main_menu_kb(),
    )
    await call.answer()


async def _send_profile_message(message: Message, tag: str, db, clash_api, user_id: int):
    player = await clash_api.get_player(tag)

    if not player:
        cached = await db.get_cached_player_json(tag)
        if cached:
            text = build_profile_text(cached) + "\n\n<i>⚠️ Показаны последние сохранённые данные (API временно недоступен)</i>"
            await message.answer(text, reply_markup=profile_single_manage_inline(tag))
            return

        await message.answer(
            "Не смог получить профиль (API не ответил) и кеша ещё нет.\n"
            "Попробуй ещё раз через 10–20 секунд.",
            reply_markup=main_menu_kb(),
        )
        return

    await db.cache_player_json(tag, player)

    name = player.get("name", "Без ника")
    await db.update_cached_name(user_id, tag, name)

    text = build_profile_text(player)
    await message.answer(text, reply_markup=profile_single_manage_inline(tag))


async def _send_profile_callback(call: CallbackQuery, tag: str, db, clash_api, user_id: int):
    player = await clash_api.get_player(tag)

    if not player:
        cached = await db.get_cached_player_json(tag)
        if cached:
            text = build_profile_text(cached) + "\n\n<i>⚠️ Показаны последние сохранённые данные (API временно недоступен)</i>"
            await call.message.answer(text, reply_markup=profile_single_manage_inline(tag))
            await call.answer()
            return

        await call.message.answer(
            "Не смог получить профиль (API не ответил) и кеша ещё нет.\n"
            "Попробуй ещё раз через 10–20 секунд.",
            reply_markup=main_menu_kb(),
        )
        await call.answer()
        return

    await db.cache_player_json(tag, player)

    name = player.get("name", "Без ника")
    await db.update_cached_name(user_id, tag, name)

    text = build_profile_text(player)
    await call.message.answer(text, reply_markup=profile_single_manage_inline(tag))
    await call.answer()
