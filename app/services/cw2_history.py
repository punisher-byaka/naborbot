from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List

import httpx

from app.utils import normalize_player_tag


@dataclass
class CW2WeekEntry:
    season_id: Optional[int]        # 127
    week: Optional[int]             # 2
    medals: int                     # 2200
    decks_used: int                 # 16
    clan_name: str                  # "! Rus Team!"
    clan_tag: str                   # "#L0GJ9PYP"
    clan_trophies: Optional[int]    # 2200 (если найдём)


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_season_week(cell_text: str) -> tuple[Optional[int], Optional[int]]:
    # формат "127-2"
    m = re.search(r"(\d{2,3})\s*-\s*(\d)", cell_text)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


class CW2HistoryService:
    """
    Достаём CW2 историю игрока из RoyaleAPI страницы игрока:
    https://royaleapi.com/player/<TAG>
    """

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def get_last_10_weeks_player(self, player_tag: str) -> List[CW2WeekEntry]:
        player_tag = normalize_player_tag(player_tag)
        player_no_hash = player_tag.replace("#", "")

        url = f"https://royaleapi.com/player/{player_no_hash}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    return []
                html = r.text
        except Exception:
            return []

        # Ищем таблицу CW2 history (на странице она реально есть)
        m = re.search(
            r'(<table[^>]+player_cw2_history_table[^>]*>.*?</table>)',
            html,
            re.S
        )
        if not m:
            return []

        table_html = m.group(1)

        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S)
        out: List[CW2WeekEntry] = []

        for row_html in rows:
            # вытащим season-week
            row_text = _strip_tags(row_html)
            season_id, week = _parse_season_week(row_text)
            if season_id is None:
                continue

            # clan tag из ссылки /clan/L0GJ9PYP
            clan_tag = ""
            cm = re.search(r"/clan/([A-Z0-9]+)", row_html)
            if cm:
                clan_tag = "#" + cm.group(1)

            # clan name — попробуем вытащить текст ссылки на клан
            clan_name = ""
            # найдём <a ... href="/clan/...">NAME</a>
            am = re.search(r'<a[^>]+href="/clan/[A-Z0-9]+"[^>]*>(.*?)</a>', row_html, re.S)
            if am:
                clan_name = _strip_tags(am.group(1))

            # вытащим все числа, но аккуратно:
            # убираем дату вида 2025-12-15 чтобы она не мешала
            tmp = re.sub(r"\d{4}-\d{2}-\d{2}", "", row_text)

            nums = [int(x) for x in re.findall(r"\b\d+\b", tmp)]

            # выкинем season и week из списка (если они там есть)
            # season/week могут встречаться как отдельные числа — убираем первые совпадения
            def remove_first(lst: list[int], val: int):
                try:
                    lst.remove(val)
                except ValueError:
                    pass

            remove_first(nums, season_id)
            if week is not None:
                remove_first(nums, week)

            # эвристика:
            # decks_used обычно <= 16
            decks_used = 0
            small = [n for n in nums if 0 <= n <= 16]
            if small:
                decks_used = max(small)

            # medals (fame) обычно большие (100..4000+)
            medals = 0
            big = [n for n in nums if n >= 50]
            if big:
                medals = max(big)

            # clan_trophies часто тоже >= 1000 и обычно последний столбец
            clan_trophies: Optional[int] = None
            if nums:
                cand = nums[-1]
                if cand >= 1000:
                    clan_trophies = cand

            out.append(
                CW2WeekEntry(
                    season_id=season_id,
                    week=week,
                    medals=medals,
                    decks_used=decks_used,
                    clan_name=clan_name or "—",
                    clan_tag=clan_tag or "—",
                    clan_trophies=clan_trophies,
                )
            )

        # на всякий: сортировка по season/week по убыванию
        out.sort(key=lambda x: ((x.season_id or 0), (x.week or 0)), reverse=True)
        return out[:10]
