from __future__ import annotations

import re


def normalize_player_tag(tag: str) -> str:
    if not tag:
        return ""
    tag = tag.strip().upper()
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag


def is_valid_tag(tag: str) -> bool:
    if not tag:
        return False
    tag = normalize_player_tag(tag)
    return bool(re.fullmatch(r"#[A-Z0-9]{6,}", tag))


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
    t = normalize_tag(tag)
    return f"%23{t}" if t else ""
