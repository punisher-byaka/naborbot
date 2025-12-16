from typing import Any, Dict, List, Optional, Tuple
import time
import httpx
from app.utils import encode_tag_for_url


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

        self._player_cache: Dict[str, Tuple[float, dict]] = {}

    async def close(self):
        await self.client.aclose()

    async def _get(self, path: str) -> Tuple[Optional[Any], Optional[str]]:
        url = f"{self.base_url}{path}"
        try:
            r = await self.client.get(url, headers=self.headers)
            if r.status_code != 200:
                return None, f"{r.status_code}: {r.text[:200]}"
            return r.json(), None
        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            return None, "timeout"
        except httpx.HTTPError as e:
            return None, str(e)

    async def get_player(self, tag: str) -> Optional[Dict[str, Any]]:
        data, _ = await self.get_player_with_error(tag)
        return data

    async def get_player_with_error(self, tag: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        now = time.time()
        cached = self._player_cache.get(tag)
        if cached and cached[0] > now:
            return cached[1], None

        enc = encode_tag_for_url(tag)
        data, err = await self._get(f"/players/{enc}")

        if data:
            self._player_cache[tag] = (now + 30.0, data)

        return data, err
