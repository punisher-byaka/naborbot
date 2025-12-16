# app/services/clash_api.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import time
import httpx

from app.utils import encode_tag_for_url, normalize_tag


class ClashApi:
    def __init__(self, token: str, base_url: str = "https://api.clashroyale.com/v1"):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=4.0),
            trust_env=False,
            http2=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

        # кеш профиля на 30 секунд
        self._player_cache: Dict[str, Tuple[float, dict]] = {}

    async def close(self):
        await self.client.aclose()

    async def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            r = await self.client.get(url, headers=self.headers)
            if r.status_code == 404:
                return {"__error__": True, "status": 404, "body": r.text}
            if r.status_code >= 400:
                return {"__error__": True, "status": r.status_code, "body": r.text}
            return r.json()
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            return {"__error__": True, "status": None, "body": f"timeout: {e}"}
        except httpx.HTTPError as e:
            return {"__error__": True, "status": None, "body": f"http_error: {e}"}

    async def get_player(self, tag: str) -> Optional[Dict[str, Any]]:
        # кешируем по нормализованному тегу (без #)
        key = normalize_tag(tag)
        now = time.time()
        cached = self._player_cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

        enc = encode_tag_for_url(tag)
        if not enc:
            return None

        data = await self._get(f"/players/{enc}")
        if isinstance(data, dict) and data.get("__error__"):
            return data  # чтобы ты видел причину в сообщении

        if data:
            self._player_cache[key] = (now + 30.0, data)
        return data

    async def get_battlelog(self, tag: str) -> Optional[List[Dict[str, Any]]]:
        enc = encode_tag_for_url(tag)
        if not enc:
            return None
        data = await self._get(f"/players/{enc}/battlelog")
        if isinstance(data, dict) and data.get("__error__"):
            return None
        return data
