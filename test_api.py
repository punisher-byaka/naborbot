import os
import asyncio
import httpx
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("CLASH_API_TOKEN")
TAG = os.getenv("TEST_PLAYER_TAG", "").strip()  # БЕЗ #

if not TAG:
    raise SystemExit("Put TEST_PLAYER_TAG into .env (tag without #)")

URL = f"https://api.clashroyale.com/v1/players/{quote('#'+TAG, safe='')}"

async def main():
    async with httpx.AsyncClient(timeout=10, trust_env=False, http2=False) as client:
        r = await client.get(URL, headers={"Authorization": f"Bearer {TOKEN}"})
        print("status:", r.status_code)
        print("text:", r.text[:400])

asyncio.run(main())
