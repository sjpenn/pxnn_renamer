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
TEXT_TYPE = "TEXT"


def _segment_for_block(block: dict, extracted_fields: dict) -> tuple[str, str]:
    """Return (kind, text) where kind is 'token', 'text', or 'empty'."""
    block_type = (block.get("type") or "").upper()
    if block_type == TEXT_TYPE:
        text = str(block.get("value") or "")
        return ("text", text) if text else ("empty", "")
    if block_type in VALUE_TYPES:
        text = str(block.get("value") or "").strip()
        return ("token", text) if text else ("empty", "")
    if block_type in SINGLETON_TYPES:
        field_name = SINGLETON_TYPES[block_type]
        text = str(extracted_fields.get(field_name) or "").strip()
        return ("token", text) if text else ("empty", "")
    return ("empty", "")


def render_blocks(
    blocks: Iterable[dict],
    *,
    global_separator: str,
    extracted_fields: dict,
) -> str:
    separator = global_separator if global_separator in ALLOWED_SEPARATORS else "_"
    segments = [_segment_for_block(block, extracted_fields) for block in blocks]
    segments = [segment for segment in segments if segment[0] != "empty"]

    parts: list[str] = []
    previous_kind: str | None = None
    for kind, text in segments:
        if previous_kind == "token" and kind == "token":
            parts.append(separator)
        parts.append(text)
        previous_kind = kind
    return "".join(parts)
