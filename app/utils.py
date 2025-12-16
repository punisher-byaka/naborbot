# app/utils.py
from __future__ import annotations


def normalize_tag(tag: str) -> str:
    t = (tag or "").strip().upper()
    if not t:
        return ""
    if t.startswith("#"):
        t = t[1:]
    if t.startswith("%23"):
        t = t[3:]
    return t


def encode_tag_for_url(tag: str) -> str:
    """
    Всегда возвращает тег в формате '%23XXXX'.
    Защита от двойного кодирования:
      - 'UC80...' -> '%23UC80...'
      - '#UC80...' -> '%23UC80...'
      - '%23UC80...' -> '%23UC80...'
    """
    t = normalize_tag(tag)
    return f"%23{t}" if t else ""
