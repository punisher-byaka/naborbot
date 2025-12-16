import json
import aiosqlite
from typing import Optional, List, Dict, Any
from datetime import datetime

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  telegram_user_id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_user_id INTEGER NOT NULL,
  player_tag TEXT NOT NULL,
  player_name_cached TEXT,
  linked_at TEXT NOT NULL,
  last_refresh_at TEXT,
  UNIQUE(telegram_user_id, player_tag),
  FOREIGN KEY(telegram_user_id) REFERENCES users(telegram_user_id)
);

CREATE TABLE IF NOT EXISTS player_cache (
  player_tag TEXT PRIMARY KEY,
  json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(telegram_user_id);
"""

class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA_SQL)
            await db.commit()

    async def ensure_user(self, telegram_user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users(telegram_user_id, created_at) VALUES(?, ?)",
                (telegram_user_id, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def count_accounts(self, telegram_user_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM accounts WHERE telegram_user_id=?",
                (telegram_user_id,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def add_account(self, telegram_user_id: int, tag: str, name: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO accounts(
                    telegram_user_id, player_tag, player_name_cached, linked_at, last_refresh_at
                ) VALUES(?, ?, ?, ?, ?)
                """,
                (
                    telegram_user_id,
                    tag,
                    name,
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()

    async def remove_account(self, telegram_user_id: int, tag: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "DELETE FROM accounts WHERE telegram_user_id=? AND player_tag=?",
                (telegram_user_id, tag),
            )
            await db.commit()

        # ✅ чистим кеш для этого тега (чтобы не копился мусор)
        await self.delete_player_cache(tag)

        return cur.rowcount > 0

    async def list_accounts(self, telegram_user_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT player_tag, COALESCE(player_name_cached, '') as name, linked_at
                FROM accounts
                WHERE telegram_user_id=?
                ORDER BY id ASC
                """,
                (telegram_user_id,),
            )
            rows = await cur.fetchall()
            return [{"tag": r[0], "name": r[1], "linked_at": r[2]} for r in rows]

    async def get_first_account(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT player_tag, COALESCE(player_name_cached, '') as name, linked_at
                FROM accounts
                WHERE telegram_user_id=?
                ORDER BY id ASC
                LIMIT 1
                """,
                (telegram_user_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {"tag": row[0], "name": row[1], "linked_at": row[2]}

    async def update_cached_name(self, telegram_user_id: int, tag: str, name: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE accounts
                SET player_name_cached=?, last_refresh_at=?
                WHERE telegram_user_id=? AND player_tag=?
                """,
                (name, datetime.utcnow().isoformat(), telegram_user_id, tag),
            )
            await db.commit()

    # -------- player_cache --------

    async def cache_player_json(self, tag: str, data: dict) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO player_cache(player_tag, json, updated_at) VALUES(?, ?, ?)",
                (tag, json.dumps(data, ensure_ascii=False), datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def get_cached_player_json(self, tag: str) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT json FROM player_cache WHERE player_tag=?", (tag,))
            row = await cur.fetchone()
            return json.loads(row[0]) if row else None

    async def delete_player_cache(self, tag: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM player_cache WHERE player_tag=?", (tag,))
            await db.commit()
