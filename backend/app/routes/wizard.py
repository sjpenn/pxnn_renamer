from typing import Optional
import json
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File as UploadFormFile, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..core.security import get_current_user
from ..database.models import ActivityLog, File as StoredFile, FileCollection, User
from ..database.session import get_db

router = APIRouter(tags=["wizard"])

SESSION_ROOT = Path(tempfile.gettempdir()) / "pxnn_it_sessions"
SESSION_ROOT.mkdir(parents=True, exist_ok=True)

DELIMITER_MAP = {
    "dash": "-",
    "underscore": "_",
    "space": " ",
    "dot": ".",
}

MIX_TYPE_ALIASES = {
    "full": "FULL",
    "main": "MAIN",
    "instrumental": "INSTRUMENTAL",
    "inst": "INSTRUMENTAL",
    "acapella": "ACAPELLA",
    "acappella": "ACAPELLA",
    "acap": "ACAPELLA",
    "vocal": "VOCAL",
    "tvmix": "TV_MIX",
    "tvmixclean": "TV_MIX_CLEAN",
    "tv": "TV_MIX",
    "clean": "CLEAN",
    "dirty": "DIRTY",
    "radioedit": "RADIO_EDIT",
    "radio": "RADIO_EDIT",
    "preview": "PREVIEW",
    "beatpreview": "PREVIEW",
    "stereo": "STEREO",
    "mono": "MONO",
}

TOKEN_ALIASES = {
    "ARTIST": "artist",
    "ARTIST_NAME": "artist",
    "TITLE": "title",
    "SONG": "title",
    "SONG_TITLE": "title",
    "PRODUCER": "producers",
    "PRODUCERS": "producers",
    "PROD": "producers",
    "MIX": "mix",
    "MIXTYPE": "mix",
    "MIX_TYPE": "mix",
    "VERSION": "version",
    "VER": "version",
    "BPM": "bpm",
    "DATE": "date",
    "DATE_CREATED": "date",
    "KEY": "key",
    "INDEX": "index",
    "TRACK": "index",
    "ORIGINAL": "original",
    "EXT": "ext",
    "EXTENSION": "ext",
}

TOKEN_PATTERN = re.compile(
    r"\{([A-Za-z_]+)\}|(?<![A-Za-z0-9])("
    + "|".join(sorted((re.escape(token) for token in TOKEN_ALIASES), key=len, reverse=True))
    + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _session_dir(session_id: str) -> Path:
    session_dir = SESSION_ROOT / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    return session_dir


def _metadata_path(session_id: str) -> Path:
    return _session_dir(session_id) / "metadata.json"


def _load_metadata(session_id: str) -> dict:
    with _metadata_path(session_id).open("r", encoding="utf-8") as metadata_file:
        return json.load(metadata_file)


def _save_metadata(session_id: str, payload: dict) -> None:
    with _metadata_path(session_id).open("w", encoding="utf-8") as metadata_file:
        json.dump(payload, metadata_file, indent=2)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _collection_name() -> str:
    return f"Rename batch {_utcnow().strftime('%b %d %Y %I:%M %p')}"


def _serialize_details(payload: Optional[dict] = None) -> str:
    return json.dumps(payload or {})


def _log_activity(
    db: Session,
    user_id: int,
    event_type: str,
    summary: str,
    collection_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    db.add(
        ActivityLog(
            user_id=user_id,
            collection_id=collection_id,
            event_type=event_type,
            summary=summary,
            details_json=_serialize_details(details),
        )
    )


def _get_user_collection(db: Session, user_id: int, session_id: str) -> FileCollection:
    collection = (
        db.query(FileCollection)
        .filter(
            FileCollection.user_id == user_id,
            FileCollection.session_id == session_id,
        )
        .first()
    )
    if not collection:
        raise HTTPException(status_code=404, detail="Rename batch not found.")
    return collection


def _format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def _display_text(value: str) -> str:
    cleaned = re.sub(r"[_-]+", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_segment(value: str, delimiter_key: str) -> str:
    if not value:
        return ""

    delimiter = DELIMITER_MAP.get(delimiter_key, "_")
    cleaned = re.sub(r"[^\w\s.-]+", " ", value, flags=re.UNICODE)
    cleaned = re.sub(r"[\s._-]+", " ", cleaned).strip()

    if not cleaned:
        return ""

    if delimiter == " ":
        return re.sub(r"\s+", " ", cleaned)

    return re.sub(r"\s+", delimiter, cleaned).strip(delimiter)


def _apply_case_style(value: str, case_style: str) -> str:
    if not value:
        return ""
    if case_style == "lower":
        return value.lower()
    if case_style == "upper":
        return value.upper()
    if case_style == "title":
        return value if value.isupper() else _title_case(value.lower())
    return value


def _clean_handle(value: str) -> str:
    cleaned = re.sub(r"^@", "", value.strip())
    cleaned = re.sub(r"[^\w.-]+", "", cleaned)
    return cleaned


def _dedupe_values(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(value)
    return ordered


def _split_user_list(value: str) -> list[str]:
    candidates = re.split(r"[;,]+", value)
    return _dedupe_values([_clean_handle(candidate) for candidate in candidates if candidate.strip()])


def _join_producers(values: list[str]) -> str:
    return "; ".join(_dedupe_values(values))


def _split_stem_segments(stem: str) -> list[str]:
    underscore_segments = [segment.strip() for segment in stem.split("_") if segment.strip()]
    if underscore_segments:
        return underscore_segments

    dash_segments = [segment.strip() for segment in re.split(r"\s+-\s+", stem) if segment.strip()]
    if len(dash_segments) > 1:
        return dash_segments

    return [stem.strip()] if stem.strip() else []


def _extract_bpm(segment: str) -> str:
    match = re.search(r"(?i)\b(\d{2,3})\s*bpm\b", segment)
    if match:
        return f"{match.group(1)}BPM"

    match = re.fullmatch(r"\s*(\d{2,3})\s*", segment)
    if match:
        return f"{match.group(1)}BPM"

    return ""


def _extract_date(segment: str) -> str:
    normalized = re.sub(r"\D", "", segment)
    if re.fullmatch(r"(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(19|20)\d{2}", normalized):
        return normalized
    return ""


def _extract_key(segment: str) -> str:
    cleaned = re.sub(r"\s+", "", segment)
    if re.fullmatch(r"(?i)[A-G](#|b)?(maj|min|m)?", cleaned):
        return cleaned.upper().replace("MIN", "min").replace("MAJ", "maj")
    return ""


def _extract_mix_type(segment: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", segment.lower())
    return MIX_TYPE_ALIASES.get(normalized, "")


def _extract_version(segment: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", segment.lower())
    if not normalized:
        return ""

    if re.fullmatch(r"v\d+", normalized):
        return normalized
    if re.fullmatch(r"ver\d+|version\d+", normalized):
        digits = re.search(r"(\d+)", normalized)
        return f"v{digits.group(1)}" if digits else ""
    if re.fullmatch(r"rev[a-z0-9]+", normalized):
        return normalized
    if normalized in {"final", "master"}:
        return normalized.upper()
    if re.fullmatch(r"(alt|mix|edit)\d+", normalized):
        return normalized
    return ""


def _extract_handle_producers(stem: str) -> tuple[list[str], str]:
    mentions = [_clean_handle(match) for match in re.findall(r"@([A-Za-z0-9_.-]+)", stem)]
    cleaned_stem = re.sub(r"@([A-Za-z0-9_.-]+)", " ", stem)
    cleaned_stem = re.sub(r"\s+[xX]\s+", " ", cleaned_stem)
    return _dedupe_values(mentions), re.sub(r"\s+", " ", cleaned_stem).strip()


def _extract_bpm_prefix(stem: str) -> tuple[str, str]:
    match = re.match(r"^\s*(\d{2,3})(?:\s*bpm)?\b[\s_-]*(.+)$", stem, flags=re.IGNORECASE)
    if not match:
        return "", stem
    return f"{match.group(1)}BPM", match.group(2).strip()


def _extract_inline_producer_pattern(stem: str, producers: list[str]) -> tuple[list[str], str]:
    pattern = re.match(
        r"^\s*(?P<producer>[A-Za-z0-9_.-]+)\s+\((?P<note>[^)]*)\)\s+(?P<title>.+)$",
        stem,
        flags=re.IGNORECASE,
    )
    if not pattern:
        return producers, stem

    note = pattern.group("note").lower()
    if "sample" not in note and "prod" not in note:
        return producers, stem

    return _dedupe_values(producers + [_clean_handle(pattern.group("producer"))]), pattern.group("title").strip()


def _parse_overrides(raw_value: str) -> dict[str, dict[str, str]]:
    if not raw_value.strip():
        return {}

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid metadata overrides.") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Invalid metadata overrides.")

    return {
        str(file_id): {
            str(field): str(value)
            for field, value in fields.items()
            if isinstance(field, str) and value is not None
        }
        for file_id, fields in parsed.items()
        if isinstance(fields, dict)
    }


def _extract_fields(stem: str, suffix: str, index: int) -> dict[str, str]:
    working_stem = stem.strip()
    extracted_producers, working_stem = _extract_handle_producers(working_stem)

    bpm_prefix, working_stem = _extract_bpm_prefix(working_stem)
    if bpm_prefix:
        bpm = bpm_prefix
    else:
        bpm = ""

    extracted_producers, working_stem = _extract_inline_producer_pattern(
        working_stem, extracted_producers
    )
    working_stem = re.sub(r"\([^)]*\)", " ", working_stem)
    working_stem = re.sub(r"\s+", " ", working_stem).strip()

    segments = _split_stem_segments(working_stem)
    remaining = segments[:]
    mix = ""
    version = ""
    date = ""
    key = ""

    while remaining:
        if not mix and len(remaining) >= 2:
            combined_mix = _extract_mix_type(f"{remaining[-2]} {remaining[-1]}")
            if combined_mix:
                mix = combined_mix
                remaining.pop()
                remaining.pop()
                continue

        segment = remaining[-1]
        if not date:
            date = _extract_date(segment)
            if date:
                remaining.pop()
                continue
        if not bpm:
            bpm = _extract_bpm(segment)
            if bpm:
                remaining.pop()
                continue
        if not key:
            key = _extract_key(segment)
            if key:
                remaining.pop()
                continue
        if not mix:
            mix = _extract_mix_type(segment)
            if mix:
                remaining.pop()
                continue
        if not version:
            version = _extract_version(segment)
            if version:
                remaining.pop()
                continue
        break

    if len(remaining) == 1:
        trailing_segment = remaining[0].strip()

        if not mix:
            preview_match = re.match(r"^(.*?)(?:\s+beat)?\s+preview\s*$", trailing_segment, flags=re.IGNORECASE)
            if preview_match:
                mix = "PREVIEW"
                trailing_segment = preview_match.group(1).strip()

        if not bpm:
            bpm_match = re.match(r"^(.*?)(?:\s+|_)(\d{2,3})\s*$", trailing_segment)
            if bpm_match:
                bpm = f"{bpm_match.group(2)}BPM"
                trailing_segment = bpm_match.group(1).strip()

        if trailing_segment:
            remaining[0] = trailing_segment

    if len(remaining) >= 2 and "_" in working_stem:
        artist = _display_text(remaining[0])
        title = " ".join(_display_text(part) for part in remaining[1:] if part)
    elif len(remaining) >= 2 and not extracted_producers:
        artist = ""
        title = " ".join(_display_text(part) for part in remaining if part)
    elif len(remaining) == 1:
        artist = ""
        title = _display_text(remaining[0])
    else:
        artist = ""
        title = _display_text(working_stem or stem)

    return {
        "artist": artist,
        "title": title,
        "producers": _join_producers(extracted_producers),
        "mix": mix,
        "version": version,
        "bpm": bpm,
        "date": date,
        "key": key,
        "index": f"{index:02d}",
        "original": _display_text(stem),
        "ext": suffix.lstrip(".").upper(),
    }


def _resolve_fields(
    extracted_fields: dict[str, str],
    defaults: dict[str, str],
    overrides: dict[str, str],
) -> dict[str, str]:
    default_artist = defaults.get("artist", "").strip()
    default_producers = _split_user_list(defaults.get("producers", ""))

    override_artist = overrides.get("artist", "").strip()
    override_producers = overrides.get("producers", "").strip()

    if override_producers:
        resolved_producers = _split_user_list(override_producers)
    else:
        resolved_producers = _dedupe_values(
            _split_user_list(extracted_fields.get("producers", ""))
            + default_producers
        )

    return {
        "artist": override_artist or default_artist or extracted_fields.get("artist", ""),
        "title": overrides.get("title", "").strip() or extracted_fields.get("title", ""),
        "producers": _join_producers(resolved_producers),
        "mix": overrides.get("mix", "").strip() or extracted_fields.get("mix", ""),
        "version": overrides.get("version", "").strip() or extracted_fields.get("version", ""),
        "bpm": overrides.get("bpm", "").strip() or extracted_fields.get("bpm", ""),
        "date": overrides.get("date", "").strip() or extracted_fields.get("date", ""),
        "key": overrides.get("key", "").strip() or extracted_fields.get("key", ""),
        "index": extracted_fields.get("index", ""),
        "original": extracted_fields.get("original", ""),
        "ext": extracted_fields.get("ext", ""),
    }


def _build_token_values(resolved_fields: dict[str, str], case_style: str) -> dict[str, str]:
    token_values = {}
    for field_name, field_value in resolved_fields.items():
        if field_name in {"mix", "bpm", "date", "key", "ext", "index", "version"}:
            token_values[field_name] = field_value
            continue
        token_values[field_name] = _apply_case_style(field_value, case_style)

    if case_style == "lower":
        token_values["mix"] = token_values["mix"].lower()
        token_values["version"] = token_values["version"].lower()
    elif case_style == "upper":
        token_values["mix"] = token_values["mix"].upper()
        token_values["version"] = token_values["version"].upper()

    return token_values


def _render_format_template(template: str, token_values: dict[str, str]) -> str:
    active_template = template.strip() or "ARTIST_TITLE_PRODUCERS_MIX_VERSION"

    def _replace_token(match: re.Match) -> str:
        raw_token = (match.group(1) or match.group(2) or "").upper()
        field_name = TOKEN_ALIASES.get(raw_token)
        if not field_name:
            return match.group(0)
        return token_values.get(field_name, "")

    return TOKEN_PATTERN.sub(_replace_token, active_template)


def _sanitize_rendered_text(rendered_text: str, delimiter_key: str, safe_cleanup: bool) -> str:
    delimiter = DELIMITER_MAP.get(delimiter_key, "_")
    cleaned = rendered_text.strip()
    cleaned = re.sub(r"[\\/]+", " ", cleaned)

    if safe_cleanup:
        cleaned = re.sub(r"[^\w\s.-]+", " ", cleaned, flags=re.UNICODE)
        cleaned = re.sub(r"[\s._-]+", " ", cleaned).strip()
        if not cleaned:
            return ""
        if delimiter == " ":
            return re.sub(r"\s+", " ", cleaned)
        return re.sub(r"\s+", delimiter, cleaned).strip(delimiter)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    if delimiter == " ":
        return cleaned
    return cleaned.replace(" ", delimiter)


def _build_preview_names(
    files: list[dict],
    format_template: str,
    delimiter: str,
    case_style: str,
    safe_cleanup: bool,
    default_artist: str,
    default_producers: str,
    file_overrides: dict[str, dict[str, str]],
) -> list[dict]:
    resolved_names = []
    seen_names: dict[str, int] = {}

    defaults = {
        "artist": default_artist,
        "producers": default_producers,
    }

    for file_item in files:
        extracted_fields = file_item["extracted_fields"]
        overrides = file_overrides.get(file_item["id"], {})
        resolved_fields = _resolve_fields(extracted_fields, defaults, overrides)
        token_values = _build_token_values(resolved_fields, case_style)
        rendered_label = _render_format_template(format_template, token_values)
        preview_stem = _sanitize_rendered_text(rendered_label, delimiter, safe_cleanup)
        preview_stem = preview_stem or _sanitize_rendered_text(
            token_values.get("original", file_item["stem"]), delimiter, True
        )
        preview_stem = preview_stem or f"file_{resolved_fields.get('index', '00')}"
        candidate_name = f"{preview_stem}{file_item['suffix']}"

        seen_count = seen_names.get(candidate_name, 0)
        if seen_count:
            duplicate_stem = f"{preview_stem}{DELIMITER_MAP.get(delimiter, '_')}{seen_count + 1}"
            candidate_name = f"{duplicate_stem}{file_item['suffix']}"
        seen_names[f"{preview_stem}{file_item['suffix']}"] = seen_count + 1

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


def _sync_collection_files(db: Session, collection: FileCollection, file_entries: list[dict]) -> None:
    existing_files = {file_record.external_id: file_record for file_record in collection.files}

    for file_entry in file_entries:
        file_record = existing_files.get(file_entry["id"])
        if not file_record:
            file_record = StoredFile(
                collection_id=collection.id,
                external_id=file_entry["id"],
                original_path=file_entry["original_name"],
                current_path=file_entry["original_name"],
                file_size=file_entry["size_bytes"],
                extension=file_entry["suffix"].lstrip(".").lower(),
                status="uploaded",
            )
            db.add(file_record)

        file_record.original_path = file_entry["original_name"]
        file_record.current_path = file_entry["original_name"]
        file_record.file_size = file_entry["size_bytes"]
        file_record.extension = file_entry["suffix"].lstrip(".").lower()
        file_record.extracted_json = _serialize_details(file_entry["extracted_fields"])
        file_record.status = "uploaded"


def _update_collection_preview(
    collection: FileCollection,
    preview_items: list[dict],
    format_template: str,
    delimiter: str,
    case_style: str,
    safe_cleanup: bool,
) -> None:
    preview_lookup = {item["id"]: item for item in preview_items}

    collection.format_template = format_template
    collection.delimiter = delimiter
    collection.case_style = case_style
    collection.safe_cleanup = safe_cleanup
    collection.status = "preview_ready"
    collection.preview_generated_at = _utcnow()

    for file_record in collection.files:
        preview_item = preview_lookup.get(file_record.external_id)
        if not preview_item:
            continue
        file_record.current_path = preview_item["preview_name"]
        file_record.resolved_json = _serialize_details(preview_item["resolved_fields"])
        file_record.status = "preview_ready"


@router.post("/api/wizard/upload")
async def upload_files(
    files: list[UploadFile] = UploadFormFile(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid_files = [file for file in files if file.filename]
    if not valid_files:
        raise HTTPException(status_code=400, detail="Select at least one file.")

    session_id = uuid.uuid4().hex
    session_dir = SESSION_ROOT / session_id
    originals_dir = session_dir / "originals"
    session_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)

    file_entries = []
    total_size = 0

    for index, upload in enumerate(valid_files, start=1):
        file_id = uuid.uuid4().hex
        original_name = Path(upload.filename).name
        suffix = Path(original_name).suffix
        stem = Path(original_name).stem
        stored_name = f"{file_id}{suffix}"
        stored_path = originals_dir / stored_name

        with stored_path.open("wb") as output_file:
            shutil.copyfileobj(upload.file, output_file)

        file_size = stored_path.stat().st_size
        total_size += file_size
        extracted_fields = _extract_fields(stem, suffix, index)
        file_entries.append(
            {
                "id": file_id,
                "original_name": original_name,
                "stored_name": stored_name,
                "stem": stem,
                "suffix": suffix,
                "size_bytes": file_size,
                "extracted_fields": extracted_fields,
            }
        )

    metadata = {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": file_entries,
        "options": {
            "format_template": "ARTIST_TITLE_PRODUCERS_MIX_VERSION",
            "delimiter": "underscore",
            "case_style": "keep",
            "safe_cleanup": True,
            "default_artist": "",
            "default_producers": "",
        },
        "preview": [],
    }
    _save_metadata(session_id, metadata)

    collection = FileCollection(
        user_id=current_user.id,
        session_id=session_id,
        name=_collection_name(),
        total_size_bytes=total_size,
        status="uploaded",
    )
    db.add(collection)
    db.flush()
    _sync_collection_files(db, collection, file_entries)
    _log_activity(
        db,
        current_user.id,
        "batch_uploaded",
        f"{len(file_entries)} files uploaded",
        collection_id=collection.id,
        details={
            "session_id": session_id,
            "file_count": len(file_entries),
            "total_size_label": _format_size(total_size),
        },
    )
    db.commit()

    return {
        "session_id": session_id,
        "file_count": len(file_entries),
        "total_size_label": _format_size(total_size),
        "files": [
            {
                "id": file_item["id"],
                "name": file_item["original_name"],
                "size_label": _format_size(file_item["size_bytes"]),
                "extracted_fields": file_item["extracted_fields"],
            }
            for file_item in file_entries
        ],
    }


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metadata = _load_metadata(session_id)
    collection = _get_user_collection(db, current_user.id, session_id)
    preview_already_logged = collection.preview_generated_at is not None
    file_overrides = _parse_overrides(file_overrides_json)
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

    metadata["options"] = {
        "format_template": format_template,
        "delimiter": delimiter,
        "case_style": case_style,
        "safe_cleanup": safe_cleanup,
        "default_artist": default_artist,
        "default_producers": default_producers,
    }
    metadata["preview"] = preview_items
    _save_metadata(session_id, metadata)

    _update_collection_preview(
        collection,
        preview_items,
        format_template=format_template,
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

    return {
        "session_id": session_id,
        "download_url": f"/api/wizard/download/{session_id}",
        "preview": preview_items,
        "options": metadata["options"],
    }


@router.get("/api/wizard/download/{session_id}")
async def download_archive(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metadata = _load_metadata(session_id)
    collection = _get_user_collection(db, current_user.id, session_id)
    if not metadata.get("preview"):
        raise HTTPException(status_code=400, detail="Generate a rename preview first.")
    from ..core.security import has_unlimited_access
    if (
        collection.download_count == 0
        and current_user.credit_balance <= 0
        and not has_unlimited_access(current_user)
    ):
        raise HTTPException(
            status_code=402,
            detail="You need at least 1 download credit before exporting this batch.",
        )

    session_dir = _session_dir(session_id)
    originals_dir = session_dir / "originals"
    archive_path = session_dir / "renamed-files.zip"

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        preview_lookup = {item["id"]: item["preview_name"] for item in metadata["preview"]}
        for file_item in metadata["files"]:
            source_path = originals_dir / file_item["stored_name"]
            archive.write(source_path, arcname=preview_lookup[file_item["id"]])

    if collection.download_count == 0 and not has_unlimited_access(current_user):
        current_user.credit_balance -= 1
        _log_activity(
            db,
            current_user.id,
            "batch_downloaded",
            "Archive exported",
            collection_id=collection.id,
            details={
                "session_id": session_id,
                "credits_remaining": current_user.credit_balance,
            },
        )

    collection.download_count += 1
    collection.downloaded_at = _utcnow()
    collection.status = "downloaded"
    for file_record in collection.files:
        file_record.status = "downloaded"
    db.commit()

    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename="pxnn-renamed-files.zip",
    )
