from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str
    clash_api_token: str
    clash_api_base: str = "https://api.clashroyale.com/v1"

def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is empty in .env")

    db_path = os.getenv("DB_PATH", "./data.db").strip()

    clash_api_token = os.getenv("CLASH_API_TOKEN", "").strip()
    if not clash_api_token:
        raise RuntimeError("CLASH_API_TOKEN is empty in .env")

    return Config(
        bot_token=bot_token,
        db_path=db_path,
        clash_api_token=clash_api_token
    )
