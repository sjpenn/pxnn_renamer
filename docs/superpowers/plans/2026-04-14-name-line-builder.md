# Name Line Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Step 2's three separate naming inputs with a single draggable, color-coded Name Line where each producer/artist is its own block, backed by autocomplete from prior rename history.

**Architecture:** Pure-function backend renderer that accepts a JSON array of blocks and walks them to produce the filename directly (bypassing the old TOKEN→single-value substitution). New `/api/wizard/preview` accepts `blocks_json` alongside legacy `format_template` (legacy keeps working). Two new `/api/suggestions/*` endpoints return distinct user-scoped prior values from `File.resolved_json`. Frontend is one vanilla-JS module (`name-line.js`) that owns the block list, renders chips, handles drag/edit/autocomplete, and serializes state to the preview endpoint.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2, HTMX, Tailwind CSS, vanilla JS (no new libraries). pytest for backend tests.

**Spec:** `docs/superpowers/specs/2026-04-14-name-line-builder-design.md`

---

## File Structure

**Create:**
- `backend/app/services/name_line.py` — pure renderer + block validation
- `backend/app/routes/suggestions.py` — `/api/suggestions/producers` and `/api/suggestions/artists`
- `frontend/static/js/name-line.js` — Name Line component (state, render, drag, edit, autocomplete, serialize)
- `frontend/static/css/name-line.css` — chip colors and layout (kept out of tailwind-input to avoid rebuild churn)
- `tests/test_name_line_render.py`
- `tests/test_wizard_blocks_preview.py`
- `tests/test_name_suggestions.py`

**Modify:**
- `backend/app/routes/wizard.py` — accept `blocks_json` + `global_separator` in `/api/wizard/preview`, fall back to legacy shape
- `backend/app/main.py` — include new `suggestions` router
- `frontend/templates/app.html` — replace Step 2 markup (lines 168–268 roughly) and the inline drag script (~1520–1610); include new JS and CSS

---

## Data Contract (used by multiple tasks)

**Block list JSON sent from client to `/api/wizard/preview` as `blocks_json`:**

```json
{
  "blocks": [
    {"type": "ARTIST", "value": "Hurricane Wisdom"},
    {"type": "PRODUCER", "value": "PMHITSS"},
    {"type": "PRODUCER", "value": "REALLYINDIG0"},
    {"type": "TEXT", "value": "@"},
    {"type": "TITLE"},
    {"type": "BPM"}
  ],
  "global_separator": "_"
}
```

**Block types:**
- Value-bearing: `ARTIST`, `PRODUCER` — require `value` (string; empty treated as skipped block).
- Singleton tokens: `TITLE`, `MIX`, `VERSION`, `BPM`, `DATE`, `KEY`, `INDEX` — no `value`; filled from the file's extracted fields.
- Literal: `TEXT` — `value` is literal text inserted in place of the surrounding separator.

**Global separator values accepted:** `"_"`, `"-"`, `" "`, `"."`. Any other value falls back to `"_"`.

**Render rule:** Walk blocks in order. Emit each block's rendered string (possibly empty). Between two *adjacent non-TEXT blocks* insert `global_separator`. A TEXT block contributes its literal value and replaces the separator on both sides (i.e. `token TEXT token` renders as `<token><text><token>` with no extra separator). Skip blocks whose rendered string is empty *and* adjust separator accordingly (do not emit back-to-back separators or trailing separators).

---

## Task 1: Backend renderer — pure function + singleton tokens

**Files:**
- Create: `backend/app/services/name_line.py`
- Test: `tests/test_name_line_render.py`

- [ ] **Step 1: Write the failing test for a singletons-only line**

```python
# tests/test_name_line_render.py
from backend.app.services.name_line import render_blocks

EXTRACTED = {
    "artist": "Hurricane Wisdom",
    "title": "Loaded Up",
    "producers": "PMHITSS; REALLYINDIG0",
    "mix": "MAIN",
    "version": "V2",
    "bpm": "140",
    "date": "2025",
    "key": "Amin",
    "index": "01",
}


def test_renders_singletons_joined_by_separator():
    blocks = [
        {"type": "TITLE"},
        {"type": "BPM"},
        {"type": "KEY"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Loaded Up_140_Amin"


def test_missing_singleton_skipped_without_double_separator():
    blocks = [
        {"type": "TITLE"},
        {"type": "BPM"},
        {"type": "KEY"},
    ]
    extracted = {**EXTRACTED, "bpm": ""}
    result = render_blocks(blocks, global_separator="_", extracted_fields=extracted)
    assert result == "Loaded Up_Amin"


def test_unknown_separator_falls_back_to_underscore():
    blocks = [{"type": "TITLE"}, {"type": "BPM"}]
    result = render_blocks(blocks, global_separator="&&", extracted_fields=EXTRACTED)
    assert result == "Loaded Up_140"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_name_line_render.py -v`
Expected: ImportError — `backend.app.services.name_line` does not exist.

- [ ] **Step 3: Implement minimal renderer**

```python
# backend/app/services/name_line.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_name_line_render.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/name_line.py tests/test_name_line_render.py
git commit -m "feat(name-line): pure block renderer for singletons"
```

---

## Task 2: Backend renderer — value-bearing tokens, TEXT overrides, edge cases

**Files:**
- Modify: `backend/app/services/name_line.py` (no new logic if Task 1 is correct; add edge-case test coverage)
- Test: `tests/test_name_line_render.py`

- [ ] **Step 1: Write failing tests for multi-value and TEXT behaviors**

```python
# append to tests/test_name_line_render.py

def test_multiple_producers_each_become_a_segment():
    blocks = [
        {"type": "ARTIST", "value": "Hurricane Wisdom"},
        {"type": "PRODUCER", "value": "PMHITSS"},
        {"type": "PRODUCER", "value": "REALLYINDIG0"},
        {"type": "TITLE"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Hurricane Wisdom_PMHITSS_REALLYINDIG0_Loaded Up"


def test_text_block_replaces_separator_on_both_sides():
    blocks = [
        {"type": "ARTIST", "value": "Hurricane Wisdom"},
        {"type": "TEXT", "value": " @ "},
        {"type": "TITLE"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Hurricane Wisdom @ Loaded Up"


def test_empty_value_block_is_skipped_and_separators_collapse():
    blocks = [
        {"type": "ARTIST", "value": "Hurricane Wisdom"},
        {"type": "PRODUCER", "value": ""},
        {"type": "TITLE"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Hurricane Wisdom_Loaded Up"


def test_unknown_block_type_ignored():
    blocks = [
        {"type": "TITLE"},
        {"type": "MADE_UP"},
        {"type": "BPM"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Loaded Up_140"


def test_empty_blocks_list_renders_empty_string():
    assert render_blocks([], global_separator="_", extracted_fields=EXTRACTED) == ""
```

- [ ] **Step 2: Run tests to verify they pass or fail**

Run: `pytest tests/test_name_line_render.py -v`
Expected: all 8 pass. If any fail, update `backend/app/services/name_line.py` so the failing cases pass. The Task 1 implementation should already handle these — verify, then move on.

- [ ] **Step 3: Commit**

```bash
git add tests/test_name_line_render.py
git commit -m "test(name-line): cover multi-value, text override, empty edge cases"
```

---

## Task 3: Wire renderer into `/api/wizard/preview`

**Files:**
- Modify: `backend/app/routes/wizard.py`
- Test: `tests/test_wizard_blocks_preview.py`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_wizard_blocks_preview.py
import io
import json

from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import User


def _login(client, db):
    user = User(username="namer", email="namer@example.com", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)
    return user


def _upload_one(client):
    # Upload a file with a predictable stem so extraction yields known fields.
    file_bytes = b"ID3" + b"\x00" * 128
    upload = ("Hurricane Wisdom - Loaded Up (prod. PMHITSS) 140.mp3", io.BytesIO(file_bytes), "audio/mpeg")
    response = client.post("/api/wizard/upload", files={"files": upload})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def test_preview_accepts_blocks_json_and_renders_multi_producer(client, db):
    _login(client, db)
    session_id = _upload_one(client)

    blocks_payload = json.dumps({
        "blocks": [
            {"type": "ARTIST", "value": "Hurricane Wisdom"},
            {"type": "PRODUCER", "value": "PMHITSS"},
            {"type": "PRODUCER", "value": "REALLYINDIG0"},
            {"type": "TITLE"},
            {"type": "BPM"},
        ],
        "global_separator": "_",
    })

    response = client.post(
        "/api/wizard/preview",
        data={
            "session_id": session_id,
            "blocks_json": blocks_payload,
            "delimiter": "underscore",
            "case_style": "keep",
            "safe_cleanup": "true",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    preview = body["preview"][0]
    assert "Hurricane Wisdom" in preview["preview_name"]
    assert preview["preview_name"].count("PMHITSS") == 1
    assert preview["preview_name"].count("REALLYINDIG0") == 1


def test_preview_falls_back_to_legacy_format_template(client, db):
    _login(client, db)
    session_id = _upload_one(client)

    response = client.post(
        "/api/wizard/preview",
        data={
            "session_id": session_id,
            "format_template": "ARTIST_TITLE_PRODUCERS",
            "default_artist": "Hurricane Wisdom",
            "default_producers": "PMHITSS",
            "delimiter": "underscore",
            "case_style": "keep",
            "safe_cleanup": "true",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    preview_name = body["preview"][0]["preview_name"]
    assert "Hurricane Wisdom" in preview_name
    assert "PMHITSS" in preview_name


def test_preview_rejects_malformed_blocks_json(client, db):
    _login(client, db)
    session_id = _upload_one(client)

    response = client.post(
        "/api/wizard/preview",
        data={"session_id": session_id, "blocks_json": "not-json"},
    )
    assert response.status_code == 400
    assert "blocks_json" in response.json()["detail"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_wizard_blocks_preview.py -v`
Expected: first test fails because `/api/wizard/preview` does not accept `blocks_json`.

- [ ] **Step 3: Extend `/api/wizard/preview` to accept `blocks_json`**

In `backend/app/routes/wizard.py`:

Near the other helper imports at top, add:
```python
from ..services.name_line import render_blocks as _render_blocks_line
```

Replace the `preview_renames` signature and body (the `@router.post("/api/wizard/preview")` function around line 745) with the block-aware version below. Keep `_build_preview_names` for legacy shape reuse.

```python
@router.post("/api/wizard/preview")
async def preview_renames(
    session_id: str = Form(...),
    format_template: str = Form("ARTIST_TITLE_PRODUCERS_MIX_VERSION"),
    delimiter: str = Form("underscore"),
    case_style: str = Form("keep"),
    safe_cleanup: bool = Form(True),
    default_artist: str = Form(""),
    default_producers: str = Form(""),
    file_overrides_json: str = Form(""),
    blocks_json: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metadata = _load_metadata(session_id)
    collection = _get_user_collection(db, current_user.id, session_id)
    preview_already_logged = collection.preview_generated_at is not None
    file_overrides = _parse_overrides(file_overrides_json)

    blocks_payload = None
    if blocks_json.strip():
        try:
            blocks_payload = json.loads(blocks_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid blocks_json: {exc}") from exc
        if not isinstance(blocks_payload, dict) or not isinstance(blocks_payload.get("blocks"), list):
            raise HTTPException(status_code=400, detail="blocks_json must contain a 'blocks' array")

    if blocks_payload is not None:
        preview_items = _build_preview_names_from_blocks(
            metadata["files"],
            blocks=blocks_payload["blocks"],
            global_separator=str(blocks_payload.get("global_separator") or "_"),
            delimiter=delimiter,
            case_style=case_style,
            safe_cleanup=safe_cleanup,
            file_overrides=file_overrides,
        )
        effective_format_template = _legacy_template_from_blocks(blocks_payload["blocks"])
    else:
        preview_items = _build_preview_names(
            metadata["files"],
            format_template=format_template,
            delimiter=delimiter,
            case_style=case_style,
            safe_cleanup=safe_cleanup,
            default_artist=default_artist,
            default_producers=default_producers,
            file_overrides=file_overrides,
        )
        effective_format_template = format_template

    metadata["options"] = {
        "format_template": effective_format_template,
        "delimiter": delimiter,
        "case_style": case_style,
        "safe_cleanup": safe_cleanup,
        "default_artist": default_artist,
        "default_producers": default_producers,
        "blocks_json": blocks_json,
    }
    metadata["preview"] = preview_items
    _save_metadata(session_id, metadata)

    _update_collection_preview(
        collection,
        preview_items,
        format_template=effective_format_template,
        delimiter=delimiter,
        case_style=case_style,
        safe_cleanup=safe_cleanup,
    )
    if not preview_already_logged:
        _log_activity(
            db,
            current_user.id,
            "preview_ready",
            f"Preview generated for {len(preview_items)} files",
            collection_id=collection.id,
            details={"session_id": session_id, "file_count": len(preview_items)},
        )
    db.commit()

    return {"session_id": session_id, "preview": preview_items}
```

Add the two new helper functions somewhere above `preview_renames` (e.g. just after `_build_preview_names`):

```python
def _legacy_template_from_blocks(blocks: list[dict]) -> str:
    """Produce a legacy-shape template string for persistence/display."""
    parts: list[str] = []
    for block in blocks:
        block_type = (block.get("type") or "").upper()
        if block_type == "TEXT":
            parts.append(str(block.get("value") or ""))
        elif block_type == "PRODUCER":
            parts.append("PRODUCER")
        elif block_type == "ARTIST":
            parts.append("ARTIST")
        elif block_type in {"TITLE", "MIX", "VERSION", "BPM", "DATE", "KEY", "INDEX"}:
            parts.append(block_type)
    return "_".join(parts) if parts else "ARTIST_TITLE_PRODUCERS_MIX_VERSION"


def _build_preview_names_from_blocks(
    files: list[dict],
    *,
    blocks: list[dict],
    global_separator: str,
    delimiter: str,
    case_style: str,
    safe_cleanup: bool,
    file_overrides: dict[str, dict[str, str]],
) -> list[dict]:
    resolved_names: list[dict] = []
    seen_names: dict[str, int] = {}

    for file_item in files:
        extracted_fields = file_item["extracted_fields"]
        overrides = file_overrides.get(file_item["id"], {})
        # Apply case style to extracted + blocks' value fields.
        shaped_extracted = _build_token_values(
            {**extracted_fields, **{k: v for k, v in overrides.items() if v}},
            case_style,
        )
        shaped_blocks = [
            {
                **block,
                "value": _apply_case_style(str(block.get("value") or ""), case_style)
                if (block.get("type") or "").upper() in {"ARTIST", "PRODUCER"}
                else block.get("value"),
            }
            for block in blocks
        ]
        rendered_label = _render_blocks_line(
            shaped_blocks,
            global_separator=global_separator,
            extracted_fields=shaped_extracted,
        )
        preview_stem = _sanitize_rendered_text(rendered_label, delimiter, safe_cleanup)
        preview_stem = preview_stem or _sanitize_rendered_text(
            shaped_extracted.get("original", file_item["stem"]), delimiter, True
        )
        preview_stem = preview_stem or f"file_{shaped_extracted.get('index', '00')}"
        candidate_name = f"{preview_stem}{file_item['suffix']}"

        seen_count = seen_names.get(candidate_name, 0)
        if seen_count:
            duplicate_stem = f"{preview_stem}{DELIMITER_MAP.get(delimiter, '_')}{seen_count + 1}"
            candidate_name = f"{duplicate_stem}{file_item['suffix']}"
        seen_names[f"{preview_stem}{file_item['suffix']}"] = seen_count + 1

        resolved_fields = {
            "artist": _first_block_value(blocks, "ARTIST"),
            "title": shaped_extracted.get("title", ""),
            "producers": "; ".join(_all_block_values(blocks, "PRODUCER")),
            "mix": shaped_extracted.get("mix", ""),
            "version": shaped_extracted.get("version", ""),
            "bpm": shaped_extracted.get("bpm", ""),
            "date": shaped_extracted.get("date", ""),
            "key": shaped_extracted.get("key", ""),
            "index": shaped_extracted.get("index", ""),
            "original": shaped_extracted.get("original", ""),
            "ext": shaped_extracted.get("ext", ""),
        }

        resolved_names.append(
            {
                "id": file_item["id"],
                "original_name": file_item["original_name"],
                "preview_name": candidate_name,
                "rendered_label": rendered_label,
                "size_bytes": file_item["size_bytes"],
                "size_label": _format_size(file_item["size_bytes"]),
                "extracted_fields": extracted_fields,
                "resolved_fields": resolved_fields,
            }
        )

    return resolved_names


def _first_block_value(blocks: list[dict], block_type: str) -> str:
    for block in blocks:
        if (block.get("type") or "").upper() == block_type:
            value = str(block.get("value") or "").strip()
            if value:
                return value
    return ""


def _all_block_values(blocks: list[dict], block_type: str) -> list[str]:
    values: list[str] = []
    for block in blocks:
        if (block.get("type") or "").upper() == block_type:
            value = str(block.get("value") or "").strip()
            if value:
                values.append(value)
    return values
```

Also ensure `_apply_case_style` is visible at module scope — if it's a local helper, leave it as is since both callers live in the same module.

- [ ] **Step 4: Run the integration tests**

Run: `pytest tests/test_wizard_blocks_preview.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full suite to confirm legacy still works**

Run: `pytest -v`
Expected: all tests pass (no regressions in existing rename/preview tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/wizard.py tests/test_wizard_blocks_preview.py
git commit -m "feat(wizard): accept blocks_json in preview endpoint with legacy fallback"
```

---

## Task 4: Suggestions endpoints (autocomplete data source)

**Files:**
- Create: `backend/app/routes/suggestions.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_name_suggestions.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_name_suggestions.py
import json
from datetime import datetime, timedelta

from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import (
    File as StoredFile,
    FileCollection,
    User,
)


def _login(client, db, username="sugg_user", email="sugg@example.com"):
    user = User(username=username, email=email, password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)
    return user


def _seed_history(db, user, entries):
    """entries is a list of (artist, producers_list, created_at)."""
    collection = FileCollection(
        user_id=user.id,
        session_id="seed",
        name="seed",
        total_size_bytes=0,
        status="complete",
    )
    db.add(collection)
    db.flush()
    for index, (artist, producers, created_at) in enumerate(entries):
        resolved = {"artist": artist, "producers": "; ".join(producers)}
        stored = StoredFile(
            collection_id=collection.id,
            external_id=f"ext-{index}",
            original_path=f"f{index}.mp3",
            current_path=f"f{index}.mp3",
            file_size=1,
            extension="mp3",
            status="renamed",
            resolved_json=json.dumps(resolved),
            created_at=created_at,
        )
        db.add(stored)
    db.commit()


def test_suggestions_requires_auth(client):
    assert client.get("/api/suggestions/producers").status_code == 401
    assert client.get("/api/suggestions/artists").status_code == 401


def test_producers_returns_distinct_recent_first(client, db):
    user = _login(client, db)
    now = datetime.utcnow()
    _seed_history(
        db,
        user,
        [
            ("Hurricane Wisdom", ["PMHITSS"], now - timedelta(days=2)),
            ("Hurricane Wisdom", ["PMHITSS", "REALLYINDIG0"], now - timedelta(days=1)),
            ("Other Artist", ["REALLYINDIG0"], now),
        ],
    )
    response = client.get("/api/suggestions/producers")
    assert response.status_code == 200
    values = response.json()["values"]
    assert values == ["REALLYINDIG0", "PMHITSS"]


def test_artists_returns_distinct_user_scoped(client, db):
    user_a = _login(client, db, username="a_user", email="a@x.com")
    _seed_history(db, user_a, [("Artist A", [], datetime.utcnow())])

    # Second user should not see first user's history.
    other = User(username="b_user", email="b@x.com", password_hash="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    _seed_history(db, other, [("Artist B", [], datetime.utcnow())])

    response = client.get("/api/suggestions/artists")
    assert response.status_code == 200
    values = response.json()["values"]
    assert values == ["Artist A"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_name_suggestions.py -v`
Expected: 404 responses (routes do not exist).

- [ ] **Step 3: Implement the suggestions router**

```python
# backend/app/routes/suggestions.py
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.security import get_current_user
from ..database.models import File as StoredFile, FileCollection, User
from ..database.session import get_db

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])


def _collect_field(db: Session, user_id: int, field: str, multivalued: bool) -> list[str]:
    rows = (
        db.query(StoredFile.resolved_json, StoredFile.created_at)
        .join(FileCollection, StoredFile.collection_id == FileCollection.id)
        .filter(FileCollection.user_id == user_id)
        .filter(StoredFile.resolved_json.isnot(None))
        .order_by(StoredFile.created_at.desc())
        .all()
    )

    ranking: dict[str, tuple[int, int]] = {}  # name -> (-first_seen_idx, count)
    for index, (resolved_json, _created_at) in enumerate(rows):
        try:
            resolved = json.loads(resolved_json) or {}
        except (TypeError, ValueError):
            continue
        raw = resolved.get(field) or ""
        candidates = (
            [part.strip() for part in raw.split(";") if part.strip()]
            if multivalued
            else [raw.strip()] if raw.strip() else []
        )
        for name in candidates:
            if name not in ranking:
                ranking[name] = (-index, 1)
            else:
                first_seen, count = ranking[name]
                ranking[name] = (first_seen, count + 1)

    return sorted(ranking.keys(), key=lambda name: (ranking[name][0], -ranking[name][1]))


@router.get("/producers")
def list_producers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"values": _collect_field(db, current_user.id, "producers", multivalued=True)}


@router.get("/artists")
def list_artists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"values": _collect_field(db, current_user.id, "artist", multivalued=False)}
```

- [ ] **Step 4: Register the router**

Open `backend/app/main.py` and add alongside the other `app.include_router(...)` calls (grep for an existing include, e.g. `wizard.router`):

```python
from .routes import suggestions as suggestions_routes
app.include_router(suggestions_routes.router)
```

- [ ] **Step 5: Run the suggestions tests**

Run: `pytest tests/test_name_suggestions.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/suggestions.py backend/app/main.py tests/test_name_suggestions.py
git commit -m "feat(suggestions): user-scoped producer/artist autocomplete endpoints"
```

---

## Task 5: Frontend — Name Line module (state + serialize, no UI yet)

**Files:**
- Create: `frontend/static/js/name-line.js`

- [ ] **Step 1: Write the module with state + serialization**

```javascript
// frontend/static/js/name-line.js
(function () {
  "use strict";

  const TOKEN_CATEGORIES = {
    ARTIST: { family: "identity", icon: "person", label: "ARTIST", hasValue: true, repeatable: true },
    PRODUCER: { family: "identity", icon: "graphic_eq", label: "PRODUCER", hasValue: true, repeatable: true },
    TITLE: { family: "content", icon: "music_note", label: "TITLE", hasValue: false, repeatable: false },
    BPM: { family: "metadata", icon: "speed", label: "BPM", hasValue: false, repeatable: false },
    KEY: { family: "metadata", icon: "piano", label: "KEY", hasValue: false, repeatable: false },
    DATE: { family: "metadata", icon: "calendar_today", label: "DATE", hasValue: false, repeatable: false },
    INDEX: { family: "metadata", icon: "tag", label: "INDEX", hasValue: false, repeatable: false },
    MIX: { family: "variant", icon: "tune", label: "MIX", hasValue: false, repeatable: false },
    VERSION: { family: "variant", icon: "layers", label: "VERSION", hasValue: false, repeatable: false },
    TEXT: { family: "literal", icon: "text_fields", label: "TEXT", hasValue: true, repeatable: true, literal: true },
  };

  const DEFAULT_BLOCKS = [
    { type: "ARTIST", value: "" },
    { type: "TITLE" },
    { type: "PRODUCER", value: "" },
    { type: "MIX" },
    { type: "VERSION" },
  ];

  const STORAGE_KEY = "pxnn.nameLine.v1";

  function newId() {
    return "b_" + Math.random().toString(36).slice(2, 9);
  }

  function normalizeBlock(block) {
    const type = String(block.type || "").toUpperCase();
    const meta = TOKEN_CATEGORIES[type];
    if (!meta) return null;
    const out = { id: block.id || newId(), type };
    if (meta.hasValue) out.value = String(block.value || "");
    return out;
  }

  function createState(initial) {
    const rawBlocks = Array.isArray(initial && initial.blocks) ? initial.blocks : DEFAULT_BLOCKS;
    const blocks = rawBlocks.map(normalizeBlock).filter(Boolean);
    const globalSeparator = (initial && initial.globalSeparator) || "_";
    return { blocks, globalSeparator };
  }

  function serialize(state) {
    return {
      blocks: state.blocks.map((block) => {
        const meta = TOKEN_CATEGORIES[block.type];
        return meta && meta.hasValue
          ? { type: block.type, value: block.value || "" }
          : { type: block.type };
      }),
      global_separator: state.globalSeparator,
    };
  }

  function loadPersisted() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_err) {
      return null;
    }
  }

  function persist(state) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (_err) {
      // ignore
    }
  }

  window.NameLine = {
    TOKEN_CATEGORIES,
    DEFAULT_BLOCKS,
    createState,
    serialize,
    loadPersisted,
    persist,
    newId,
    normalizeBlock,
  };
})();
```

- [ ] **Step 2: Smoke-check the module from the browser console**

Include the script manually in any template temporarily (or run `python -c "print(open('frontend/static/js/name-line.js').read()[:200])"` just to confirm it's in place). For now the test is: open `http://localhost:8000/app` after wiring in Task 8 and paste into the console:

```js
const s = NameLine.createState();
JSON.stringify(NameLine.serialize(s));
```

Defer this smoke-check until Task 8 wires the script in. For now, only confirm the file parses with Node:

Run: `node --check frontend/static/js/name-line.js`
Expected: no output (parse OK).

- [ ] **Step 3: Commit**

```bash
git add frontend/static/js/name-line.js
git commit -m "feat(name-line-js): state model and serialization"
```

---

## Task 6: Frontend — rendering, palette, inline edit, autocomplete

**Files:**
- Modify: `frontend/static/js/name-line.js`
- Create: `frontend/static/css/name-line.css`

- [ ] **Step 1: Add the CSS for chip families**

```css
/* frontend/static/css/name-line.css */
.nl-legend { display: flex; gap: 14px; font-size: 11px; color: var(--ink-dim, #6b6257); }
.nl-legend .nl-legend-item { display: inline-flex; align-items: center; gap: 6px; }
.nl-legend .nl-swatch { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }

.nl-palette { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.nl-palette button {
  border: 1px solid var(--hairline, #dcd4c8);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  background: var(--stage-raised, #fff);
  cursor: pointer;
}
.nl-palette button:hover { background: var(--stage-sunken, #f3eee6); }

.nl-line {
  display: flex; flex-wrap: wrap; align-items: center; gap: 4px;
  min-height: 52px;
  padding: 10px;
  border: 2px dashed var(--hairline, #dcd4c8);
  border-radius: 14px;
}

.nl-chip {
  position: relative;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  cursor: grab;
  user-select: none;
  border: 1px solid transparent;
}
.nl-chip[draggable="true"]:active { cursor: grabbing; }
.nl-chip .nl-chip-swatch { width: 3px; align-self: stretch; border-radius: 2px; margin-right: 4px; }
.nl-chip .nl-chip-icon { font-size: 14px; opacity: 0.7; }
.nl-chip .nl-chip-remove {
  opacity: 0; margin-left: 4px; border: none; background: transparent; cursor: pointer; font-size: 14px;
}
.nl-chip:hover .nl-chip-remove { opacity: 0.7; }
.nl-chip .nl-chip-input { border: none; outline: none; background: transparent; font: inherit; min-width: 80px; }

.nl-family-identity { background: rgba(204, 112, 68, 0.10); color: #8a4a2a; }
.nl-family-identity .nl-chip-swatch { background: #cc7044; }
.nl-family-content  { background: rgba(60, 55, 50, 0.06);  color: #3c3732; }
.nl-family-content  .nl-chip-swatch { background: #6b6257; }
.nl-family-metadata { background: rgba(71, 125, 120, 0.10); color: #305854; }
.nl-family-metadata .nl-chip-swatch { background: #477d78; }
.nl-family-variant  { background: rgba(120, 80, 115, 0.10); color: #5a3a55; }
.nl-family-variant  .nl-chip-swatch { background: #785073; }
.nl-family-literal  { background: transparent; color: var(--ink-dim, #6b6257); border-color: var(--hairline, #dcd4c8); }
.nl-family-literal  .nl-chip-swatch { display: none; }

.nl-chip[data-empty="true"] { border-color: #cc4a3d; }

.nl-autocomplete {
  position: absolute; top: calc(100% + 4px); left: 0; z-index: 20;
  background: #fff; border: 1px solid var(--hairline, #dcd4c8); border-radius: 8px;
  max-height: 180px; overflow-y: auto; min-width: 160px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.nl-autocomplete-item { padding: 6px 10px; font-size: 12px; cursor: pointer; }
.nl-autocomplete-item:hover, .nl-autocomplete-item.is-active { background: var(--stage-sunken, #f3eee6); }

.nl-drop-before { box-shadow: -2px 0 0 0 #cc7044; }
.nl-drop-after  { box-shadow:  2px 0 0 0 #cc7044; }
```

- [ ] **Step 2: Extend `name-line.js` with rendering, palette, edit, autocomplete**

Append to `frontend/static/js/name-line.js` *inside the existing IIFE* (before the `window.NameLine = {...}` assignment), then add the new public methods to that object. Show both: the new internal helpers plus the updated `window.NameLine` block.

```javascript
// --- Rendering ---

function familyFor(type) {
  const meta = TOKEN_CATEGORIES[type];
  return meta ? meta.family : "literal";
}

function renderChip(block, handlers) {
  const meta = TOKEN_CATEGORIES[block.type] || { family: "literal", label: block.type, icon: "help" };
  const chip = document.createElement("span");
  chip.className = "nl-chip nl-family-" + meta.family;
  chip.setAttribute("draggable", "true");
  chip.dataset.blockId = block.id;
  chip.dataset.blockType = block.type;

  const swatch = document.createElement("span");
  swatch.className = "nl-chip-swatch";
  chip.appendChild(swatch);

  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined nl-chip-icon";
  icon.textContent = meta.icon;
  chip.appendChild(icon);

  if (meta.hasValue) {
    const valueText = block.value || "";
    if (!valueText) chip.dataset.empty = "true";

    const label = document.createElement("span");
    label.textContent = meta.label + (meta.literal ? "" : ": ");
    if (!meta.literal) chip.appendChild(label);

    const valueNode = document.createElement("span");
    valueNode.className = "nl-chip-value";
    valueNode.textContent = valueText || (meta.literal ? "…" : "empty");
    chip.appendChild(valueNode);

    chip.addEventListener("click", (event) => {
      if (event.target.classList.contains("nl-chip-remove")) return;
      handlers.onEdit(block.id, chip);
    });
  } else {
    const label = document.createElement("span");
    label.textContent = meta.label;
    chip.appendChild(label);
  }

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "nl-chip-remove";
  removeBtn.textContent = "×";
  removeBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    handlers.onRemove(block.id);
  });
  chip.appendChild(removeBtn);

  return chip;
}

function renderPalette(container, handlers) {
  container.innerHTML = "";
  Object.keys(TOKEN_CATEGORIES).forEach((type) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "+ " + TOKEN_CATEGORIES[type].label;
    btn.addEventListener("click", () => handlers.onAdd(type));
    container.appendChild(btn);
  });
}

function renderLegend(container) {
  container.innerHTML = "";
  const families = [
    ["identity", "Identity"],
    ["content", "Content"],
    ["metadata", "Metadata"],
    ["variant", "Variant"],
    ["literal", "Literal"],
  ];
  families.forEach(([family, label]) => {
    const item = document.createElement("span");
    item.className = "nl-legend-item";
    const swatch = document.createElement("span");
    swatch.className = "nl-swatch nl-family-" + family;
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(label));
    container.appendChild(item);
  });
}

// --- Autocomplete ---

const suggestionsCache = { ARTIST: null, PRODUCER: null };

async function fetchSuggestions(blockType) {
  if (suggestionsCache[blockType] !== null) return suggestionsCache[blockType];
  const endpoint = blockType === "ARTIST" ? "/api/suggestions/artists" : "/api/suggestions/producers";
  try {
    const response = await fetch(endpoint, { credentials: "same-origin" });
    if (!response.ok) {
      suggestionsCache[blockType] = [];
      return [];
    }
    const body = await response.json();
    const values = Array.isArray(body.values) ? body.values : [];
    suggestionsCache[blockType] = values;
    return values;
  } catch (_err) {
    suggestionsCache[blockType] = [];
    return [];
  }
}

function openEditor(chipEl, block, onCommit) {
  chipEl.innerHTML = "";
  chipEl.classList.add("nl-family-" + familyFor(block.type));
  const input = document.createElement("input");
  input.type = "text";
  input.className = "nl-chip-input";
  input.value = block.value || "";
  input.placeholder = TOKEN_CATEGORIES[block.type].label;
  chipEl.appendChild(input);

  let dropdown = null;
  let activeIndex = -1;
  let options = [];

  function closeDropdown() {
    if (dropdown) dropdown.remove();
    dropdown = null;
    activeIndex = -1;
    options = [];
  }

  function renderDropdown(values) {
    closeDropdown();
    const filtered = values.filter((v) => v.toLowerCase().includes(input.value.toLowerCase())).slice(0, 8);
    if (!filtered.length) return;
    dropdown = document.createElement("div");
    dropdown.className = "nl-autocomplete";
    filtered.forEach((value, index) => {
      const item = document.createElement("div");
      item.className = "nl-autocomplete-item";
      item.textContent = value;
      item.addEventListener("mousedown", (event) => {
        event.preventDefault();
        input.value = value;
        commit();
      });
      dropdown.appendChild(item);
    });
    chipEl.appendChild(dropdown);
    options = filtered;
  }

  function commit() {
    closeDropdown();
    onCommit(input.value.trim());
  }

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); commit(); }
    else if (event.key === "Escape") { closeDropdown(); onCommit(block.value || ""); }
    else if (event.key === "ArrowDown" && dropdown) { activeIndex = Math.min(activeIndex + 1, options.length - 1); highlightActive(); }
    else if (event.key === "ArrowUp" && dropdown)   { activeIndex = Math.max(activeIndex - 1, 0); highlightActive(); }
  });
  input.addEventListener("blur", () => { setTimeout(commit, 100); });

  function highlightActive() {
    if (!dropdown) return;
    Array.from(dropdown.children).forEach((child, index) => {
      child.classList.toggle("is-active", index === activeIndex);
    });
  }

  const meta = TOKEN_CATEGORIES[block.type];
  if (meta && !meta.literal && (block.type === "ARTIST" || block.type === "PRODUCER")) {
    fetchSuggestions(block.type).then((values) => {
      renderDropdown(values);
      input.addEventListener("input", () => renderDropdown(values));
    });
  }

  input.focus();
  input.select();
}
```

Then update the exported `window.NameLine` object to include the new helpers:

```javascript
window.NameLine = {
  TOKEN_CATEGORIES,
  DEFAULT_BLOCKS,
  createState,
  serialize,
  loadPersisted,
  persist,
  newId,
  normalizeBlock,
  renderChip,
  renderPalette,
  renderLegend,
  openEditor,
  fetchSuggestions,
};
```

- [ ] **Step 3: Parse-check**

Run: `node --check frontend/static/js/name-line.js`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add frontend/static/js/name-line.js frontend/static/css/name-line.css
git commit -m "feat(name-line-js): chip rendering, palette, inline edit, autocomplete"
```

---

## Task 7: Frontend — drag-reorder + controller (mount into a container)

**Files:**
- Modify: `frontend/static/js/name-line.js`

- [ ] **Step 1: Add the `mount` controller function**

Append before the `window.NameLine` assignment (and add `mount` to the export):

```javascript
function mount(root, options) {
  const legendEl   = root.querySelector("[data-nl-legend]");
  const paletteEl  = root.querySelector("[data-nl-palette]");
  const lineEl     = root.querySelector("[data-nl-line]");
  const separatorSelect = root.querySelector("[data-nl-separator]");
  const resetBtn   = root.querySelector("[data-nl-reset]");

  const state = createState(loadPersisted() || undefined);
  if (separatorSelect) separatorSelect.value = state.globalSeparator;

  function notifyChange() {
    persist(state);
    if (typeof options.onChange === "function") options.onChange(serialize(state));
  }

  function rerender() {
    renderLine();
    notifyChange();
  }

  function renderLine() {
    lineEl.innerHTML = "";
    state.blocks.forEach((block) => {
      const chip = renderChip(block, {
        onRemove(id) {
          state.blocks = state.blocks.filter((b) => b.id !== id);
          rerender();
        },
        onEdit(id, chipEl) {
          const target = state.blocks.find((b) => b.id === id);
          if (!target) return;
          openEditor(chipEl, target, (newValue) => {
            target.value = newValue;
            rerender();
          });
        },
      });
      attachDrag(chip);
      lineEl.appendChild(chip);
    });
  }

  function attachDrag(chipEl) {
    chipEl.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", chipEl.dataset.blockId);
      event.dataTransfer.effectAllowed = "move";
      chipEl.style.opacity = "0.4";
    });
    chipEl.addEventListener("dragend", () => {
      chipEl.style.opacity = "";
      lineEl.querySelectorAll(".nl-chip").forEach((c) => {
        c.classList.remove("nl-drop-before", "nl-drop-after");
      });
    });
    chipEl.addEventListener("dragover", (event) => {
      event.preventDefault();
      const rect = chipEl.getBoundingClientRect();
      const after = event.clientX - rect.left > rect.width / 2;
      chipEl.classList.toggle("nl-drop-after", after);
      chipEl.classList.toggle("nl-drop-before", !after);
    });
    chipEl.addEventListener("dragleave", () => {
      chipEl.classList.remove("nl-drop-before", "nl-drop-after");
    });
    chipEl.addEventListener("drop", (event) => {
      event.preventDefault();
      const sourceId = event.dataTransfer.getData("text/plain");
      if (!sourceId || sourceId === chipEl.dataset.blockId) return;
      const rect = chipEl.getBoundingClientRect();
      const after = event.clientX - rect.left > rect.width / 2;
      const targetId = chipEl.dataset.blockId;
      const sourceIndex = state.blocks.findIndex((b) => b.id === sourceId);
      const [moved] = state.blocks.splice(sourceIndex, 1);
      const targetIndex = state.blocks.findIndex((b) => b.id === targetId);
      state.blocks.splice(after ? targetIndex + 1 : targetIndex, 0, moved);
      rerender();
    });
  }

  if (legendEl) renderLegend(legendEl);
  if (paletteEl) {
    renderPalette(paletteEl, {
      onAdd(type) {
        const block = normalizeBlock({ type });
        if (!block) return;
        state.blocks.push(block);
        rerender();
        if (TOKEN_CATEGORIES[type].hasValue) {
          const chip = lineEl.querySelector('[data-block-id="' + block.id + '"]');
          if (chip) openEditor(chip, block, (newValue) => {
            block.value = newValue;
            rerender();
          });
        }
      },
    });
  }
  if (separatorSelect) {
    separatorSelect.addEventListener("change", () => {
      state.globalSeparator = separatorSelect.value || "_";
      rerender();
    });
  }
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      const fresh = createState();
      state.blocks = fresh.blocks;
      state.globalSeparator = fresh.globalSeparator;
      if (separatorSelect) separatorSelect.value = state.globalSeparator;
      rerender();
    });
  }

  rerender();

  return {
    getState: () => state,
    getSerialized: () => serialize(state),
  };
}
```

Update the export:

```javascript
window.NameLine = {
  TOKEN_CATEGORIES,
  DEFAULT_BLOCKS,
  createState,
  serialize,
  loadPersisted,
  persist,
  newId,
  normalizeBlock,
  renderChip,
  renderPalette,
  renderLegend,
  openEditor,
  fetchSuggestions,
  mount,
};
```

- [ ] **Step 2: Parse-check**

Run: `node --check frontend/static/js/name-line.js`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/static/js/name-line.js
git commit -m "feat(name-line-js): drag-reorder controller and mount entry point"
```

---

## Task 8: Template integration — replace Step 2 markup and wire preview

**Files:**
- Modify: `frontend/templates/app.html`

- [ ] **Step 1: Read the current Step 2 region**

Open `frontend/templates/app.html` and locate the span of lines 168–268 (batch defaults + token-builder). Also locate the inline drag-and-drop script around lines 1520–1610, and the preview-submission code around lines 1130–1370 (hooks for `format_template`, `default_artist`, `default_producers`).

- [ ] **Step 2: Replace the Step 2 markup**

Find the block that starts with the Step 2 "Set batch defaults first" hint (near line 168) and ends after the token-builder's `Extra tokens` row (near line 268). Replace the entire markup between (and including) the batch-defaults container and the token-builder container with:

```html
<div id="name-line-root" data-nl-root
     class="rounded-xl border border-hairline bg-stage-raised p-4 space-y-3">
  <div class="nl-legend" data-nl-legend></div>
  <div class="nl-palette" data-nl-palette></div>
  <div class="nl-line" data-nl-line></div>
  <div class="flex items-center gap-3 text-xs text-ink-dim">
    <label class="flex items-center gap-2">
      Separator:
      <select data-nl-separator class="rounded border border-hairline bg-stage-raised px-2 py-1 text-xs">
        <option value="_">_ underscore</option>
        <option value="-">- dash</option>
        <option value=" ">␣ space</option>
        <option value=".">. dot</option>
      </select>
    </label>
    <button type="button" data-nl-reset class="underline">Reset to default</button>
  </div>
</div>
```

Remove the old `#token-builder`, `#default_artist`, `#default_producers`, and `#format_template` elements entirely. (If other JS references them — grep to confirm — replace those references in Step 4 below.)

- [ ] **Step 3: Include the module**

In the `<head>` (or just before `</body>`, matching the existing script style), add:

```html
<link rel="stylesheet" href="{{ url_for('static', path='/css/name-line.css') }}?v=name-line-1">
<script src="{{ url_for('static', path='/js/name-line.js') }}?v=name-line-1"></script>
```

- [ ] **Step 4: Wire the controller and preview call**

Find the existing inline script block in `app.html` that handles preview submission (grep for `/api/wizard/preview`). Replace the `FormData` construction that currently reads `format_template` / `default_artist` / `default_producers` with the block-list approach. Also remove the inline drag handling (lines ~1520–1610) and the legacy listeners for the old inputs.

Concretely, inside an existing `DOMContentLoaded` handler (or add one if none exists) add:

```html
<script>
  (function () {
    let latestSerialized = null;
    const root = document.getElementById("name-line-root");
    if (!root) return;

    const controller = window.NameLine.mount(root, {
      onChange(serialized) {
        latestSerialized = serialized;
        if (typeof window.refreshPreview === "function") window.refreshPreview();
      },
    });

    // Expose the serialized state to the existing preview submitter.
    window.getNameLineState = () => latestSerialized || controller.getSerialized();
  })();
</script>
```

In the existing preview-submission function (the one that currently builds `FormData` with `format_template` etc.), replace those field appends with:

```javascript
const nameLineState = (typeof window.getNameLineState === "function") ? window.getNameLineState() : null;
if (nameLineState) {
  formData.append("blocks_json", JSON.stringify(nameLineState));
} else {
  // Legacy fallback — keep as defensive path only; should not hit in practice.
  formData.append("format_template", "ARTIST_TITLE_PRODUCERS_MIX_VERSION");
}
```

And remove the three legacy appends:

```javascript
// delete these lines:
formData.append("format_template", document.getElementById("format_template").value);
formData.append("default_artist", document.getElementById("default_artist").value);
formData.append("default_producers", document.getElementById("default_producers").value);
```

Also delete the inline drag-handler script region that binds to `#token-builder` / `.token-chip-drag` / `.token-chip-extra` (grep for these ids/classes in `app.html`; remove the block that registers their event listeners).

- [ ] **Step 5: Run the backend test suite — nothing template-related should have regressed**

Run: `pytest -v`
Expected: all passing.

- [ ] **Step 6: Manual browser verification**

Start the app (`docker-compose up --build` or `uvicorn backend.app.main:app --reload`), sign in, upload one audio file, and verify:
1. Step 2 shows legend, palette, a dashed line with default chips, and separator dropdown.
2. Clicking `+ PRODUCER` adds an empty chip in edit mode with an autocomplete dropdown (empty if no history yet).
3. Typing a name and pressing Enter commits. The chip now shows `PRODUCER: NAME` in the warm identity color.
4. Dragging a chip to a new position reorders it; preview filename updates.
5. Changing separator updates all gaps in the preview.
6. Adding a `TEXT` chip with `@` between ARTIST and TITLE produces `Artist@Title` in the preview.
7. Refreshing the page preserves the line (localStorage).
8. Submitting to backend produces a correct preview name.

If any step fails, fix before committing.

- [ ] **Step 7: Commit**

```bash
git add frontend/templates/app.html
git commit -m "feat(app): replace Step 2 inputs with Name Line builder"
```

---

## Task 9: Final verification

- [ ] **Step 1: Full test run**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Confirm no lingering references to the removed inputs**

Run: `grep -n "default_artist\|default_producers\|token-chip-drag\|token-chip-extra\|#token-builder" frontend/templates/app.html`
Expected: no matches (all three ids and both classes removed). If any remain, remove them and re-run Step 1.

- [ ] **Step 3: Confirm `.gitignore` untouched and no stray files**

Run: `git status`
Expected: clean working tree.
