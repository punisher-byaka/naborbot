from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


def normalize_player_tag(tag: str) -> str:
    tag = (tag or "").strip().upper()
    if not tag:
        return ""
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag


@dataclass
class CW2PlayerWeekEntry:
    clan_name: str
    clan_tag: str
    season: int
    week: int
    medals: int
    decks_used: int


class CW2HistoryService:
    """
    История CW2 ИГРОКА (как в RoyaleAPI профиле игрока).
    ВАЖНО: Supercell API не умеет дать историю кланов игрока, если он менял кланы.
    Поэтому берём RoyaleAPI и парсим __NEXT_DATA__ со страницы игрока.
    """

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    async def get_player_last_weeks(self, player_tag: str, limit: int = 10) -> List[CW2PlayerWeekEntry]:
        player_tag = normalize_player_tag(player_tag)
        if not player_tag:
            return []

        weeks = await self._from_royaleapi_player_page(player_tag)
        return weeks[:limit]

    async def _from_royaleapi_player_page(self, player_tag: str) -> List[CW2PlayerWeekEntry]:
        # RoyaleAPI: /player/<TAG without #>
        tag_no_hash = player_tag.replace("#", "")
        url = f"https://royaleapi.com/player/{tag_no_hash}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    return []
                html = r.text
        except Exception:
            return []

        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">\s*(\{.*?\})\s*</script>',
            html,
            re.S,
        )
        if not m:
            return []

        try:
            blob = json.loads(m.group(1))
        except Exception:
            return []

        # На RoyaleAPI структура меняется, поэтому делаем “мягкий” поиск:
        # находим список объектов, похожих на CW2 history item:
        # - есть season/week
        # - есть medals/fame
        # - есть decksUsed
        # - есть clan {name, tag} или clanName/clanTag
        candidates = self._find_player_cw2_items(blob)

        out: List[CW2PlayerWeekEntry] = []
        for it in candidates:
            parsed = self._parse_player_cw2_item(it)
            if parsed:
                out.append(parsed)

        # Часто там уже отсортировано по убыванию, но на всякий:
        out.sort(key=lambda x: (x.season, x.week), reverse=True)

        # Убираем дубли (иногда в next-data встречаются повторения)
        uniq: List[CW2PlayerWeekEntry] = []
        seen = set()
        for w in out:
            key = (w.clan_tag, w.season, w.week, w.medals, w.decks_used)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(w)

        return uniq

    def _parse_player_cw2_item(self, it: Dict[str, Any]) -> Optional[CW2PlayerWeekEntry]:
        # season/week
        season = it.get("season") or it.get("seasonId")
        week = it.get("week") or it.get("sectionIndex") or it.get("warWeek") or it.get("periodIndex")

        # medals/fame
        medals = it.get("medals")
        if medals is None:
            medals = it.get("fame")
        if medals is None:
            medals = it.get("fameEarned") or it.get("fame_earned")

        # decks
        decks = it.get("decks_used") or it.get("decksUsed") or it.get("decks")

        # clan info
        clan_name = ""
        clan_tag = ""

        clan_obj = it.get("clan")
        if isinstance(clan_obj, dict):
            clan_name = str(clan_obj.get("name") or "")
            clan_tag = str(clan_obj.get("tag") or "")
        else:
            clan_name = str(it.get("clanName") or it.get("clan_name") or "")
            clan_tag = str(it.get("clanTag") or it.get("clan_tag") or "")

        # Валидация + приведение
        if not isinstance(season, int) or not isinstance(week, int):
            return None
        if medals is None:
            medals = 0
        if decks is None:
            decks = 0

        try:
            medals_i = int(medals)
        except Exception:
            medals_i = 0
        try:
            decks_i = int(decks)
        except Exception:
            decks_i = 0

        clan_tag = normalize_player_tag(clan_tag) if clan_tag else ""
        if clan_tag and not clan_tag.startswith("#"):
            clan_tag = "#" + clan_tag

        # Бывает, что clan name/tag пустые — тогда такое пропускаем
        if not clan_name or not clan_tag:
            return None

        return CW2PlayerWeekEntry(
            clan_name=clan_name,
            clan_tag=clan_tag,
            season=season,
            week=week,
            medals=medals_i,
            decks_used=decks_i,
        )

    def _find_player_cw2_items(self, obj: Any) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []

        def looks_like_cw2_item(d: Dict[str, Any]) -> bool:
            has_time = any(k in d for k in ("season", "seasonId")) and any(
                k in d for k in ("week", "sectionIndex", "warWeek", "periodIndex")
            )
            has_scores = any(k in d for k in ("medals", "fame", "fameEarned", "fame_earned")) and any(
                k in d for k in ("decksUsed", "decks_used", "decks")
            )
            has_clan = (
                isinstance(d.get("clan"), dict)
                and ("name" in d["clan"])
                and ("tag" in d["clan"])
            ) or (("clanName" in d and "clanTag" in d) or ("clan_name" in d and "clan_tag" in d))
            return has_time and has_scores and has_clan

        def walk(x: Any):
            if isinstance(x, dict):
                if looks_like_cw2_item(x):
                    found.append(x)
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        walk(obj)
        return found
