from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx


def normalize_tag(tag: str) -> str:
    tag = (tag or "").strip().upper()
    if not tag:
        return ""
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag


def encode_tag(tag: str) -> str:
    # Supercell: # -> %23
    tag = normalize_tag(tag)
    return tag.replace("#", "%23")


@dataclass
class CW2WeekEntry:
    season_id: Optional[int]
    week: Optional[int]
    medals: int
    decks_used: int
    clan_trophies: Optional[int]  # если есть
    league: Optional[int]         # 1000/2000/3000/4000...


def league_from_trophies(t: Optional[int]) -> Optional[int]:
    if t is None:
        return None
    # грубо: лиги CW2 обычно считаются тысячами трофеев
    return (t // 1000) * 1000


class CW2HistoryService:
    """
    Пытается получить CW2 историю:
    1) Supercell /riverracelog
    2) fallback: парс RoyaleAPI /clan/<tag>/war/log (Next.js JSON)
    """

    def __init__(self, supercell_base: str, supercell_token: str, timeout: float = 12.0):
        self.supercell_base = supercell_base.rstrip("/")
        self.supercell_token = supercell_token
        self.timeout = timeout

        self._headers = {
            "Authorization": f"Bearer {self.supercell_token}",
        }

    async def get_last_10_weeks(
        self,
        clan_tag: str,
        player_tag: str,
    ) -> List[CW2WeekEntry]:
        clan_tag = normalize_tag(clan_tag)
        player_tag = normalize_tag(player_tag)

        # 1) пробуем Supercell
        weeks = await self._from_supercell(clan_tag, player_tag)
        if weeks:
            return weeks[:10]

        # 2) fallback: RoyaleAPI HTML -> __NEXT_DATA__
        weeks = await self._from_royaleapi(clan_tag, player_tag)
        return weeks[:10]

    async def _from_supercell(self, clan_tag: str, player_tag: str) -> List[CW2WeekEntry]:
        url = f"{self.supercell_base}/clans/{encode_tag(clan_tag)}/riverracelog"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                r = await client.get(url, headers=self._headers)
                if r.status_code != 200:
                    return []
                data = r.json()
        except Exception:
            return []

        items = data.get("items") or []
        out: List[CW2WeekEntry] = []

        for it in items:
            # структура Supercell: it["seasonId"], it["sectionIndex"] или "warWeek"/"periodIndex" (в зависимости от версии)
            season_id = it.get("seasonId")
            week = it.get("sectionIndex") or it.get("warWeek") or it.get("periodIndex")

            standings = it.get("standings") or []
            # clan trophies для текущего клана в этом логе
            clan_trophies: Optional[int] = None

            for st in standings:
                c = st.get("clan") or {}
                if normalize_tag(c.get("tag", "")) == clan_tag:
                    clan_trophies = c.get("clanWarTrophies") or c.get("trophies") or None
                    break

            medals = 0
            decks_used = 0

            # игрок может быть в participants одного из standings (обычно в st["clan"]["participants"])
            found = False
            for st in standings:
                c = st.get("clan") or {}
                participants = c.get("participants") or []
                for p in participants:
                    if normalize_tag(p.get("tag", "")) == player_tag:
                        # у Supercell чаще fame/repairPoints/boatAttacks/decksUsed
                        medals = int(p.get("fame") or 0)
                        decks_used = int(p.get("decksUsed") or p.get("decks") or 0)
                        found = True
                        break
                if found:
                    break

            out.append(
                CW2WeekEntry(
                    season_id=season_id if isinstance(season_id, int) else None,
                    week=week if isinstance(week, int) else None,
                    medals=medals,
                    decks_used=decks_used,
                    clan_trophies=clan_trophies if isinstance(clan_trophies, int) else None,
                    league=league_from_trophies(clan_trophies if isinstance(clan_trophies, int) else None),
                )
            )

        return out

    async def _from_royaleapi(self, clan_tag: str, player_tag: str) -> List[CW2WeekEntry]:
        # RoyaleAPI использует тег без # в URL
        clan_no_hash = clan_tag.replace("#", "")
        url = f"https://royaleapi.com/clan/{clan_no_hash}/war/log"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    return []
                html = r.text
        except Exception:
            return []

        # Next.js JSON
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">\s*(\{.*?\})\s*</script>', html, re.S)
        if not m:
            return []

        try:
            blob = json.loads(m.group(1))
        except Exception:
            return []

        # Дальше самое “скользкое”: структура next-data может меняться.
        # Делаем максимально мягкий поиск: пробегаем по JSON и ищем объекты,
        # похожие на warlog items (имеют standings/participants и season/week).
        items = self._find_warlog_items(blob)
        if not items:
            return []

        out: List[CW2WeekEntry] = []
        for it in items[:10]:
            season_id = it.get("seasonId") or it.get("season")
            week = it.get("week") or it.get("sectionIndex") or it.get("warWeek") or it.get("periodIndex")

            standings = it.get("standings") or it.get("items") or it.get("clans") or []
            clan_trophies: Optional[int] = None
            medals = 0
            decks_used = 0

            # пытаемся извлечь “наш клан” и “нашего игрока”
            for st in standings:
                # варианты: st["clan"] или st сам clan-object
                clan_obj = st.get("clan") if isinstance(st, dict) else None
                if clan_obj is None and isinstance(st, dict) and "tag" in st:
                    clan_obj = st

                if not isinstance(clan_obj, dict):
                    continue

                if normalize_tag(clan_obj.get("tag", "")) == clan_tag:
                    ct = clan_obj.get("clanWarTrophies") or clan_obj.get("trophies")
                    if isinstance(ct, int):
                        clan_trophies = ct

                participants = clan_obj.get("participants") or st.get("participants") or []
                if isinstance(participants, list):
                    for p in participants:
                        if not isinstance(p, dict):
                            continue
                        if normalize_tag(p.get("tag", "")) == player_tag:
                            medals = int(p.get("fame") or p.get("medals") or 0)
                            decks_used = int(p.get("decksUsed") or p.get("decks") or p.get("decks_used") or 0)

            out.append(
                CW2WeekEntry(
                    season_id=season_id if isinstance(season_id, int) else None,
                    week=week if isinstance(week, int) else None,
                    medals=medals,
                    decks_used=decks_used,
                    clan_trophies=clan_trophies,
                    league=league_from_trophies(clan_trophies),
                )
            )

        return out

    def _find_warlog_items(self, obj: Any) -> List[Dict[str, Any]]:
        """
        Рекурсивно ищем список объектов, похожих на записи river race log.
        """
        found: List[Dict[str, Any]] = []

        def walk(x: Any):
            if isinstance(x, dict):
                # эвристика "похоже на warlog item"
                if ("standings" in x and isinstance(x.get("standings"), list)) and (
                    "seasonId" in x or "week" in x or "sectionIndex" in x or "periodIndex" in x
                ):
                    found.append(x)
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        walk(obj)

        # часто items лежат списком — сортировать “по времени” без поля сложно,
        # поэтому возвращаем как найдено; на практике Next.js хранит уже в нужном порядке.
        return found
