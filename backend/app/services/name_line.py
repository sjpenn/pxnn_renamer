from __future__ import annotations

from typing import Iterable

ALLOWED_SEPARATORS = {"_", "-", " ", "."}

SINGLETON_TYPES = {
    "TITLE": "title",
    "MIX": "mix",
    "VERSION": "version",
    "BPM": "bpm",
    "DATE": "date",
    "KEY": "key",
    "INDEX": "index",
}

VALUE_TYPES = {"ARTIST", "PRODUCER"}
VALUE_TYPE_DEFAULT_KEY = {"ARTIST": "artist", "PRODUCER": "producers"}
TEXT_TYPE = "TEXT"


def _segment_for_block(
    block: dict,
    extracted_fields: dict,
    account_defaults: dict | None = None,
) -> tuple[str, str]:
    """Return (kind, text) where kind is 'token', 'text', or 'empty'."""
    defaults = account_defaults or {}
    block_type = (block.get("type") or "").upper()
    if block_type == TEXT_TYPE:
        text = str(block.get("value") or "")
        return ("text", text) if text else ("empty", "")
    if block_type in VALUE_TYPES:
        text = str(block.get("value") or "").strip()
        if not text:
            fallback_key = VALUE_TYPE_DEFAULT_KEY.get(block_type, "")
            text = str(defaults.get(fallback_key) or "").strip()
        return ("token", text) if text else ("empty", "")
    if block_type in SINGLETON_TYPES:
        field_name = SINGLETON_TYPES[block_type]
        text = str(extracted_fields.get(field_name) or "").strip()
        if not text:
            text = str(defaults.get(field_name) or "").strip()
        return ("token", text) if text else ("empty", "")
    return ("empty", "")


def render_blocks(
    blocks: Iterable[dict],
    *,
    global_separator: str,
    extracted_fields: dict,
    account_defaults: dict | None = None,
) -> str:
    separator = global_separator if global_separator in ALLOWED_SEPARATORS else "_"
    segments = [_segment_for_block(block, extracted_fields, account_defaults) for block in blocks]
    segments = [segment for segment in segments if segment[0] != "empty"]

    parts: list[str] = []
    previous_kind: str | None = None
    for kind, text in segments:
        if previous_kind == "token" and kind == "token":
            parts.append(separator)
        parts.append(text)
        previous_kind = kind
    return "".join(parts)
