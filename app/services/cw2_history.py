from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


def normalize_tag(tag: str) -> str:
    tag = (tag or "").strip().upper()
    if not tag:
        return ""
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag


def encode_tag(tag: str) -> str:
    tag = normalize_tag(tag)
    return tag.replace("#", "%23")


def _first_int(*vals: Any) -> Optional[int]:
    """Вернёт первое значение типа int (включая 0)."""
    for v in vals:
        if isinstance(v, int):
            return v
    return None


@dataclass
class CW2WeekEntry:
    season_id: Optional[int]
    week: Optional[int]
    medals: int
    decks_used: int
    clan_trophies: Optional[int]
    league: Optional[int]


def league_from_trophies(t: Optional[int]) -> Optional[int]:
    if t is None:
        return None
    return (t // 1000) * 1000


class CW2HistoryService:
    """
    1) Supercell: /clans/{tag}/riverracelog
    2) fallback: RoyaleAPI /clan/<tag>/war/log (Next.js JSON)
    """

    def __init__(self, supercell_base: str, supercell_token: str, timeout: float = 12.0):
        self.supercell_base = supercell_base.rstrip("/")
        self.supercell_token = supercell_token
        self.timeout = timeout
        self._headers = {"Authorization": f"Bearer {self.supercell_token}"}

    async def get_last_10_weeks(self, clan_tag: str, player_tag: str) -> List[CW2WeekEntry]:
        clan_tag = normalize_tag(clan_tag)
        player_tag = normalize_tag(player_tag)

        weeks = await self._from_supercell(clan_tag, player_tag)
        if weeks:
            return weeks[:10]

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
            season_id = _first_int(it.get("seasonId"), it.get("season"))
            week = _first_int(it.get("sectionIndex"), it.get("warWeek"), it.get("periodIndex"), it.get("week"))

            standings = it.get("standings") or []
            clan_trophies: Optional[int] = None
            medals = 0
            decks_used = 0

            # 1) найдём трофеи клана в standings
            for st in standings:
                clan_obj = st.get("clan") if isinstance(st, dict) else None
                if not isinstance(clan_obj, dict):
                    continue

                if normalize_tag(clan_obj.get("tag", "")) == clan_tag:
                    # важно: берём int и НЕ теряем 0
                    clan_trophies = _first_int(
                        clan_obj.get("clanWarTrophies"),
                        clan_obj.get("warTrophies"),
                        clan_obj.get("clan_war_trophies"),
                        clan_obj.get("trophies"),  # fallback (хуже, но лучше чем None)
                    )
                    break

            # 2) найдём игрока в participants
            found = False
            for st in standings:
                clan_obj = st.get("clan") if isinstance(st, dict) else None
                if not isinstance(clan_obj, dict):
                    continue

                participants = clan_obj.get("participants") or st.get("participants") or []
                if not isinstance(participants, list):
                    continue

                for p in participants:
                    if not isinstance(p, dict):
                        continue
                    if normalize_tag(p.get("tag", "")) == player_tag:
                        medals = int(p.get("fame") or p.get("medals") or 0)
                        decks_used = int(p.get("decksUsed") or p.get("decks") or p.get("decks_used") or 0)
                        found = True
                        break
                if found:
                    break

            out.append(
                CW2WeekEntry(
                    season_id=season_id,
                    week=week,
                    medals=medals,
                    decks_used=decks_used,
                    clan_trophies=clan_trophies,
                    league=league_from_trophies(clan_trophies),
                )
            )

        return out

    async def _from_royaleapi(self, clan_tag: str, player_tag: str) -> List[CW2WeekEntry]:
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

        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">\s*(\{.*?\})\s*</script>', html, re.S)
        if not m:
            return []

        try:
            blob = json.loads(m.group(1))
        except Exception:
            return []

        items = self._find_warlog_items(blob)
        if not items:
            return []

        out: List[CW2WeekEntry] = []
        for it in items[:10]:
            season_id = _first_int(it.get("seasonId"), it.get("season"))
            week = _first_int(it.get("week"), it.get("sectionIndex"), it.get("warWeek"), it.get("periodIndex"))

            standings = it.get("standings") or it.get("items") or it.get("clans") or []
            clan_trophies: Optional[int] = None
            medals = 0
            decks_used = 0

            for st in standings:
                clan_obj = st.get("clan") if isinstance(st, dict) else None
                if clan_obj is None and isinstance(st, dict) and "tag" in st:
                    clan_obj = st
                if not isinstance(clan_obj, dict):
                    continue

                if normalize_tag(clan_obj.get("tag", "")) == clan_tag:
                    clan_trophies = _first_int(
                        clan_obj.get("clanWarTrophies"),
                        clan_obj.get("warTrophies"),
                        clan_obj.get("trophies"),
                    )

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
                    season_id=season_id,
                    week=week,
                    medals=medals,
                    decks_used=decks_used,
                    clan_trophies=clan_trophies,
                    league=league_from_trophies(clan_trophies),
                )
            )

        return out

    def _find_warlog_items(self, obj: Any) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []

        def walk(x: Any):
            if isinstance(x, dict):
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
        return found
