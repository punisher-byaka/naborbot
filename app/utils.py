import re
from urllib.parse import quote

# официальный алфавит тегов Clash Royale
ALLOWED = set("0289PYLQGRJCUV")

TAG_RE = re.compile(r"^[0289PYLQGRJCUV]{3,15}$")

def normalize_player_tag(raw: str) -> str:
    s = (raw or "").upper().replace(" ", "")
    if s.startswith("#"):
        s = s[1:]

    # ❗ заменяем O на 0 автоматически
    s = s.replace("O", "0")
    return s

def is_valid_tag(tag: str) -> bool:
    return bool(TAG_RE.match(tag))

def encode_tag_for_url(tag: str) -> str:
    return quote(f"#{tag}", safe="")
