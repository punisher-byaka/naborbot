from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, List, Tuple

import aiofiles
import httpx
from PIL import Image, ImageDraw, ImageFont


@dataclass
class RenderConfig:
    icon_size: int = 56
    pad: int = 16
    col_gap: int = 10
    row_gap: int = 10
    max_cols: int = 16

    header_h: int = 36
    section_gap: int = 18
    block_gap: int = 24

    bg: Tuple[int, int, int] = (245, 247, 250)
    text: Tuple[int, int, int] = (20, 20, 24)
    sub: Tuple[int, int, int] = (80, 80, 90)


def _safe_font(size: int) -> ImageFont.ImageFont:
    for path in [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def display_level(card: Dict[str, Any]) -> int | None:
    lv = card.get("level")
    mx = card.get("maxLevel")
    if isinstance(lv, int) and isinstance(mx, int) and mx > 0:
        return lv + (16 - mx)
    return None


async def _download_bytes(url: str, client: httpx.AsyncClient) -> bytes:
    r = await client.get(url, timeout=20, follow_redirects=True)
    r.raise_for_status()
    return r.content


async def _get_icon_cached(url: str, cache_dir: str, client: httpx.AsyncClient) -> Image.Image:
    os.makedirs(cache_dir, exist_ok=True)

    # ✅ уникальное имя = hash от полного URL (исключает путаницу cards vs cardevolutions vs cardheroes)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    fpath = os.path.join(cache_dir, f"{key}.png")

    if os.path.exists(fpath):
        async with aiofiles.open(fpath, "rb") as f:
            data = await f.read()
        return Image.open(BytesIO(data)).convert("RGBA")

    data = await _download_bytes(url, client)
    async with aiofiles.open(fpath, "wb") as f:
        await f.write(data)

    return Image.open(BytesIO(data)).convert("RGBA")


def _icons(card: Dict[str, Any]) -> Dict[str, str]:
    return card.get("iconUrls") or {}


def _icon_normal(card: Dict[str, Any]) -> str | None:
    return _icons(card).get("medium")


def _icon_evo(card: Dict[str, Any]) -> str | None:
    icons = _icons(card)
    return icons.get("evolutionMedium") or icons.get("medium")


def _icon_hero(card: Dict[str, Any]) -> str | None:
    return _icons(card).get("heroMedium")


def _is_evo_owned(card: Dict[str, Any]) -> bool:
    # как у тебя уже работает: эво "открыта" если evolutionLevel int и >0
    return isinstance(card.get("evolutionLevel"), int) and card["evolutionLevel"] > 0


def _is_real_hero_owned(card: Dict[str, Any]) -> bool:
    """
    ТВОЙ КЕЙС (по JSON):
    - Giant и Mini P.E.K.K.A: heroMedium есть, evolutionMedium НЕТ, evolutionLevel > 0
    - Knight и Musketeer: heroMedium есть, НО evolutionMedium ЕСТЬ, evolutionLevel отсутствует/0
      -> их НЕ показываем в Hero Card Collection.
    """
    icons = _icons(card)
    return (
        bool(icons.get("heroMedium"))
        and not bool(icons.get("evolutionMedium"))
        and _is_evo_owned(card)
    )


def _pick_icon_for_levels(card: Dict[str, Any]) -> str | None:
    # ✅ если эво открыта — показываем evolutionMedium (с fallback на medium)
    if _is_evo_owned(card):
        return _icon_evo(card) or _icon_normal(card)
    return _icon_normal(card)


def _group_by_display_level(cards: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    groups: Dict[int, List[Dict[str, Any]]] = {}
    for c in cards or []:
        dl = display_level(c)
        if isinstance(dl, int):
            groups.setdefault(dl, []).append(c)
    for lv in list(groups.keys()):
        groups[lv] = sorted(groups[lv], key=lambda x: x.get("name", ""))
    return groups


def _count_ge(groups: Dict[int, List[Dict[str, Any]]], level: int) -> int:
    return sum(len(groups.get(lv, [])) for lv in groups.keys() if lv >= level)


async def _render_icon_grid(img: Image.Image, x0: int, y0: int, icons: List[Image.Image], cfg: RenderConfig) -> int:
    cols = cfg.max_cols
    if not icons:
        return cfg.icon_size

    for i, ic in enumerate(icons):
        r = i // cols
        c = i % cols
        x = x0 + c * (cfg.icon_size + cfg.col_gap)
        y = y0 + r * (cfg.icon_size + cfg.row_gap)
        ic_resized = ic.resize((cfg.icon_size, cfg.icon_size))
        img.paste(ic_resized, (x, y), ic_resized)

    rows = (len(icons) + cols - 1) // cols
    return rows * cfg.icon_size + (rows - 1) * cfg.row_gap


async def render_upgrade_image(
    player: Dict[str, Any],
    out_path: str,
    cache_dir: str = "cache/icons",
    levels_to_show: List[int] | None = None,
) -> str:
    cfg = RenderConfig()
    font_h = _safe_font(18)
    font_s = _safe_font(14)

    cards = player.get("cards", []) or []
    total_cards = len(cards)
    groups = _group_by_display_level(cards)

    # Верхние коллекции
    support_cards = player.get("supportCards", []) or []

    # ✅ Герои — только реально открытые hero-карты
    hero_cards = [c for c in cards if _is_real_hero_owned(c)]

    # ✅ ЭВО — только реально открытые эволюции
    evo_cards_owned = [c for c in cards if _is_evo_owned(c)]

    if levels_to_show is None:
        levels_to_show = list(range(16, 8, -1))  # 16..9

    cols = cfg.max_cols
    icon_block_w = cols * cfg.icon_size + (cols - 1) * cfg.col_gap
    canvas_w = cfg.pad * 2 + icon_block_w

    def rows_for(n: int) -> int:
        return max(1, (n + cols - 1) // cols)

    # высота
    h = cfg.pad
    for n in (len(support_cards), len(hero_cards), len(evo_cards_owned)):
        h += cfg.header_h
        h += rows_for(n) * cfg.icon_size + (rows_for(n) - 1) * cfg.row_gap
        h += cfg.block_gap

    for lv in levels_to_show:
        n = len(groups.get(lv, []))
        h += cfg.header_h
        h += rows_for(n) * cfg.icon_size + (rows_for(n) - 1) * cfg.row_gap
        h += cfg.section_gap

    h += cfg.pad

    img = Image.new("RGB", (canvas_w, h), cfg.bg)
    draw = ImageDraw.Draw(img)

    async with httpx.AsyncClient() as client:
        y = cfg.pad

        async def render_collection(title: str, items: List[Dict[str, Any]], icon_picker) -> None:
            nonlocal y
            draw.text((cfg.pad, y), title, font=font_h, fill=cfg.text)
            draw.text((cfg.pad + 320, y + 2), f"Открыто: {len(items)}", font=font_s, fill=cfg.sub)
            y += cfg.header_h

            icons_img: List[Image.Image] = []
            for it in sorted(items, key=lambda x: x.get("name", "")):
                url = icon_picker(it)
                if url:
                    icons_img.append(await _get_icon_cached(url, cache_dir, client))

            y += await _render_icon_grid(img, cfg.pad, y, icons_img, cfg)
            y += cfg.block_gap

        # Верх
        # Если хочешь убрать Tower Card Collection — просто закомментируй следующую строку:
        await render_collection("Tower Card Collection", support_cards, _icon_normal)

        await render_collection("Hero Card Collection", hero_cards, _icon_hero)
        await render_collection("Evo Card Collection", evo_cards_owned, _icon_evo)

        # Уровни
        for lv in levels_to_show:
            exact_cards = groups.get(lv, [])
            count_eq = len(exact_cards)
            total_ge = _count_ge(groups, lv)
            over = max(0, total_ge - count_eq)
            pct = (total_ge / total_cards * 100) if total_cards else 0.0

            draw.text((cfg.pad, y), f"Level {lv}", font=font_h, fill=cfg.text)
            draw.text(
                (cfg.pad + 170, y + 2),
                f"Total {total_ge} ({pct:.0f}%)   Count {count_eq}   Overleveled {over}",
                font=font_s,
                fill=cfg.sub,
            )
            y += cfg.header_h

            icons_img: List[Image.Image] = []
            for c in exact_cards:
                url = _pick_icon_for_levels(c)
                if url:
                    icons_img.append(await _get_icon_cached(url, cache_dir, client))

            y += await _render_icon_grid(img, cfg.pad, y, icons_img, cfg)
            y += cfg.section_gap

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)
    return out_path
