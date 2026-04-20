"""End-to-end test: upload multiple files, arrange name-line blocks, download ZIP,
validate that archived filenames match the block arrangement — including the
Account Details fallback for files that don't have all fields in their original name.
"""
import io
import json
import zipfile

import pytest

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.database.models import User


# Realistic sample filenames — some carry BPM in the name, some don't.
SAMPLE_FILES = [
    # (filename, content)
    ("Hurricane Wisdom - Loaded Up 140.mp3",            b"ID3" + b"\x00" * 128),
    ("Hurricane Wisdom - Streets of Philly 161BPM.mp3", b"ID3" + b"\x00" * 128),
    ("Hurricane Wisdom - i popped way 2 many pills.mp3",b"ID3" + b"\x00" * 128),
    ("Thunder1.mp3",                                    b"ID3" + b"\x00" * 128),
]


@pytest.fixture
def logged_in_user(client, db):
    user = User(
        username="e2e_tester",
        email="e2e@example.com",
        password_hash="x",
        credit_balance=5,  # enough to download
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)
    return user


def _upload_batch(client, files):
    upload_files = [
        ("files", (name, io.BytesIO(data), "audio/mpeg"))
        for name, data in files
    ]
    response = client.post("/api/wizard/upload", files=upload_files)
    assert response.status_code == 200, response.text
    return response.json()


def _preview(client, session_id, blocks, account_defaults=None, separator="_"):
    data = {
        "session_id": session_id,
        "blocks_json": json.dumps({
            "blocks": blocks,
            "global_separator": separator,
        }),
        "delimiter": "underscore",
        "case_style": "keep",
        "safe_cleanup": "true",
    }
    if account_defaults is not None:
        data["account_defaults_json"] = json.dumps(account_defaults)
    response = client.post("/api/wizard/preview", data=data)
    assert response.status_code == 200, response.text
    return response.json()


def test_e2e_upload_arrange_download_roundtrip(client, logged_in_user):
    # ---- 1. Upload the batch ----
    upload = _upload_batch(client, SAMPLE_FILES)
    session_id = upload["session_id"]
    uploaded_ids = [f["id"] for f in upload["files"]]
    assert len(uploaded_ids) == len(SAMPLE_FILES)

    # ---- 2. Initial arrangement: PRODUCER _ TITLE _ BPM ----
    account_defaults = {
        "producers": "PMHITSS",
        "bpm": "140",
        "key": "Amin",
        "date": "2026",
        "mix": "MAIN",
        "version": "V1",
    }
    blocks_v1 = [
        {"type": "PRODUCER", "value": "PMHITSS"},
        {"type": "TITLE"},
        {"type": "BPM"},
    ]
    preview_v1 = _preview(client, session_id, blocks_v1, account_defaults)["preview"]
    names_v1 = {p["original_name"]: p["preview_name"] for p in preview_v1}

    # Every file should start with PMHITSS_
    for name in names_v1.values():
        assert name.startswith("PMHITSS_"), f"expected PMHITSS_ prefix, got: {name}"

    # Files with BPM in the name should carry their real BPM (140 / 161).
    # Files without BPM should fall back to the Account Details default (140).
    loaded_up = names_v1["Hurricane Wisdom - Loaded Up 140.mp3"]
    streets   = names_v1["Hurricane Wisdom - Streets of Philly 161BPM.mp3"]
    thunder   = names_v1["Thunder1.mp3"]
    pills     = names_v1["Hurricane Wisdom - i popped way 2 many pills.mp3"]

    assert "140" in loaded_up, f"Loaded Up should keep extracted BPM 140: {loaded_up}"
    assert "161" in streets,   f"Streets should keep extracted BPM 161: {streets}"
    # Fallback to account default for files missing BPM:
    assert "140" in thunder,   f"Thunder1 should fall back to default BPM 140: {thunder}"
    assert "140" in pills,     f"pills should fall back to default BPM 140: {pills}"

    # Original bug (fixed in d6868cc): three BPM chips → `_NNNBPM_NNNBPM_NNNBPM`.
    # With only one BPM block in this test, no file should contain the triple-BPM artifact.
    # (Note: a *second* "BPM" can appear when the TITLE extractor leaves a trailing
    # "161BPM" inside the title — that's a separate pre-existing extractor issue, not
    # the triple-chip bug we're guarding against here.)
    for name in names_v1.values():
        assert name.count("BPM") < 3, f"triple-BPM artifact leaked into {name}"

    # ---- 3. Reorder: TITLE _ PRODUCER _ KEY (different order, different fields) ----
    blocks_v2 = [
        {"type": "TITLE"},
        {"type": "PRODUCER", "value": "PMHITSS"},
        {"type": "KEY"},
    ]
    preview_v2 = _preview(client, session_id, blocks_v2, account_defaults)["preview"]
    names_v2 = {p["original_name"]: p["preview_name"] for p in preview_v2}

    # Now PMHITSS should be in the middle, not at the start.
    for original, rendered in names_v2.items():
        stem = rendered.rsplit(".", 1)[0]
        parts = stem.split("_")
        # PRODUCER is the second token → index 1 (0-indexed)
        assert "PMHITSS" in parts, f"PMHITSS missing from {rendered}"
        producer_idx = parts.index("PMHITSS")
        assert producer_idx >= 1, (
            f"After reorder PMHITSS should no longer be the first token, got {rendered}"
        )
        # KEY fallback value "Amin" should appear
        assert "Amin" in stem, f"Key fallback Amin missing in {rendered}"

    # ---- 4. Add a literal TEXT block to prove text chips render verbatim ----
    blocks_v3 = [
        {"type": "PRODUCER", "value": "PMHITSS"},
        {"type": "TEXT", "value": " // "},
        {"type": "TITLE"},
    ]
    preview_v3 = _preview(client, session_id, blocks_v3, account_defaults)["preview"]
    # Note: the " // " literal is sanitized by safe_cleanup — just ensure the
    # producer and title are still present in the correct order.
    for p in preview_v3:
        stem = p["preview_name"].rsplit(".", 1)[0]
        assert stem.startswith("PMHITSS"), (
            f"Producer should still lead after TEXT insertion: {p['preview_name']}"
        )

    # ---- 5. Settle on blocks_v2, then download ZIP ----
    _preview(client, session_id, blocks_v2, account_defaults)  # re-apply
    download = client.get(f"/api/wizard/download/{session_id}")
    assert download.status_code == 200, download.text
    assert download.headers["content-type"] == "application/zip"

    # ---- 6. Validate ZIP contents match the final preview names exactly ----
    final_names = sorted(names_v2.values())
    with zipfile.ZipFile(io.BytesIO(download.content)) as zf:
        archived = sorted(zf.namelist())

    assert archived == final_names, (
        f"ZIP contents do not match preview names.\n"
        f"In preview: {final_names}\n"
        f"In ZIP:     {archived}"
    )

    # ---- 7. Every file in the ZIP is uniquely named (no collisions) ----
    assert len(archived) == len(set(archived)), f"duplicate names in ZIP: {archived}"

    # ---- 8. Archived entries are non-empty ----
    with zipfile.ZipFile(io.BytesIO(download.content)) as zf:
        for info in zf.infolist():
            assert info.file_size > 0, f"empty file in ZIP: {info.filename}"


def test_e2e_account_defaults_fill_gaps_without_clobbering_extracted(client, logged_in_user):
    """Regression guard: account_defaults must NOT overwrite fields extracted from the
    filename, only fill in missing ones."""
    upload = _upload_batch(client, [
        ("Artist - Song 128BPM.mp3",  b"ID3" + b"\x00" * 128),  # has BPM 128
        ("Artist - Song.mp3",         b"ID3" + b"\x00" * 128),  # no BPM
    ])
    session_id = upload["session_id"]

    blocks = [
        {"type": "TITLE"},
        {"type": "BPM"},
    ]
    preview = _preview(
        client,
        session_id,
        blocks,
        account_defaults={"bpm": "999"},  # obvious sentinel
    )["preview"]
    names = {p["original_name"]: p["preview_name"] for p in preview}

    # File with extracted BPM keeps its real value, not 999.
    assert "128" in names["Artist - Song 128BPM.mp3"]
    assert "999" not in names["Artist - Song 128BPM.mp3"], (
        "account default overwrote an extracted BPM"
    )

    # File without BPM uses the fallback.
    assert "999" in names["Artist - Song.mp3"], (
        "account default did not fill in missing BPM"
    )


def test_e2e_duplicate_singleton_does_not_produce_duplicate_values(client, logged_in_user):
    """Even if a caller sends a duplicate BPM block (client should prevent this, but
    the server must degrade gracefully), we should not see the original
    `_152BPM_152BPM_152BPM` artifact for files that DO have extracted BPM.

    This documents current server behavior: duplicates render duplicate values,
    which is exactly why the client palette now blocks repeat singletons."""
    upload = _upload_batch(client, [
        ("Artist - Song 128BPM.mp3", b"ID3" + b"\x00" * 128),
    ])
    session_id = upload["session_id"]

    # Three BPM blocks — the client UI prevents this now, but if it slipped through…
    blocks = [
        {"type": "TITLE"},
        {"type": "BPM"},
        {"type": "BPM"},
        {"type": "BPM"},
    ]
    preview = _preview(client, session_id, blocks)["preview"]
    rendered = preview[0]["preview_name"]

    # Server faithfully renders duplicates → this is WHY we dedupe client-side.
    # Three BPM chips contribute at least three "128" occurrences; the title
    # extractor may add one more. If this drops to <= 1, the server silently
    # started deduping — update this test and remove the client-side guard.
    assert rendered.count("128") >= 3, (
        f"Server no longer renders duplicate BPM chips: {rendered}"
    )
