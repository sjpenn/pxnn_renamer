"""Extractor: strip parsed metadata tokens out of the TITLE candidate.

When BPM / MIX / VERSION / KEY / DATE are confidently parsed into their own
fields, their textual representations must not remain in the title. Otherwise
the rendered name line can contain the same value twice — once from the chip
and once trailing inside the TITLE block.

See the `_strip_parsed_tokens_from_title` helper in backend/app/routes/wizard.py.
"""
import io
import json

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.database.models import User
from backend.app.routes.wizard import _extract_fields


def _login(client, db, suffix="t"):
    user = User(
        username=f"title_{suffix}",
        email=f"title_{suffix}@example.com",
        password_hash="x",
        credit_balance=5,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)
    return user


def _upload(client, filename, data=b"ID3" + b"\x00" * 128):
    response = client.post(
        "/api/wizard/upload",
        files={"files": (filename, io.BytesIO(data), "audio/mpeg")},
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _preview(client, session_id, blocks, account_defaults=None, separator="_"):
    data = {
        "session_id": session_id,
        "blocks_json": json.dumps(
            {"blocks": blocks, "global_separator": separator}
        ),
        "delimiter": "underscore",
        "case_style": "keep",
        "safe_cleanup": "true",
    }
    if account_defaults:
        data["account_defaults_json"] = json.dumps(account_defaults)
    response = client.post("/api/wizard/preview", data=data)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Unit-level tests against _extract_fields — fast and focused.
# ---------------------------------------------------------------------------


def test_extractor_strips_trailing_bpm_suffix_from_title():
    fields = _extract_fields(
        "Hurricane Wisdom - Streets of Philly 161BPM", ".mp3", 0
    )
    assert fields["bpm"] == "161BPM"
    assert "161" not in fields["title"]
    assert "bpm" not in fields["title"].lower()


def test_extractor_strips_bpm_without_bpm_suffix():
    # "140" trails the song name and is already pulled into BPM via the
    # trailing-segment regex; the title should not contain 140.
    fields = _extract_fields("Hurricane Wisdom - Loaded Up 140", ".mp3", 0)
    assert fields["bpm"] == "140BPM"
    assert "140" not in fields["title"]


def test_extractor_strips_embedded_bpm_in_dash_split_segment():
    fields = _extract_fields("Artist - Song 140BPM", ".mp3", 0)
    assert fields["bpm"] == "140BPM"
    assert "140" not in fields["title"]
    assert "BPM" not in fields["title"].upper().split() or "BPM" not in fields[
        "title"
    ].upper()


def test_extractor_strips_version_and_key_and_bpm_from_underscore_name():
    fields = _extract_fields("Artist_Song_Amin_128BPM_V1", ".mp3", 0)
    assert fields["bpm"] == "128BPM"
    assert fields["key"] == "Amin"
    assert fields["version"] == "v1"
    # Title is just "Song" with extras stripped.
    assert "128" not in fields["title"]
    assert "Amin" not in fields["title"]
    assert "V1" not in fields["title"].upper()


def test_extractor_preserves_year_in_title_when_no_date_extracted():
    # "1999" looks like a year but DATE requires full MMDDYYYY — extractor
    # leaves it alone, so the title must still contain it.
    fields = _extract_fields("1999 Dreams", ".mp3", 0)
    assert fields["date"] == ""
    assert fields["bpm"] == ""
    assert "1999" in fields["title"]


def test_extractor_preserves_mix_and_version_when_not_extracted():
    # Dash splitting produces a single segment here, so MAIN/V2 don't land in
    # their own fields. The title retains them — callers rely on this so that
    # the tokens survive when no MIX/VERSION chip is arranged.
    fields = _extract_fields("Artist - Song MAIN V2", ".mp3", 0)
    # If these aren't extracted, the title must keep them so the user doesn't
    # lose information.
    if not fields["mix"]:
        assert "MAIN" in fields["title"].upper()
    if not fields["version"]:
        assert "V2" in fields["title"].upper()


# ---------------------------------------------------------------------------
# Render-level tests — ensure the full preview pipeline doesn't emit duplicates.
# ---------------------------------------------------------------------------


def test_preview_bpm_appears_exactly_once(client, db):
    _login(client, db, suffix="bpm1")
    session_id = _upload(client, "Artist - Song 140BPM.mp3")

    body = _preview(
        client,
        session_id,
        [{"type": "TITLE"}, {"type": "BPM"}],
    )
    name = body["preview"][0]["preview_name"]
    assert name.count("140") == 1, name
    assert name.count("BPM") == 1, name


def test_preview_mix_and_version_each_once_when_extracted(client, db):
    # Underscore-separated name — extractor pulls MAIN / V2 out.
    _login(client, db, suffix="mv1")
    session_id = _upload(client, "Artist_Song_MAIN_V2.mp3")

    body = _preview(
        client,
        session_id,
        [{"type": "TITLE"}, {"type": "MIX"}, {"type": "VERSION"}],
    )
    name = body["preview"][0]["preview_name"]
    assert name.upper().count("MAIN") == 1, name
    assert name.upper().count("V2") == 1, name


def test_preview_year_in_title_is_not_duplicated(client, db):
    _login(client, db, suffix="yr1")
    session_id = _upload(client, "1999 Dreams.mp3")

    body = _preview(client, session_id, [{"type": "TITLE"}])
    name = body["preview"][0]["preview_name"]
    assert "1999" in name, name
    assert name.count("1999") == 1, name


def test_preview_key_bpm_version_each_once(client, db):
    # Underscore separators make key/version/bpm extractable; title ends up as
    # "Song" only. Each metadata value should appear exactly once.
    _login(client, db, suffix="kbv1")
    session_id = _upload(client, "Artist_Song_Amin_128BPM_V1.mp3")

    body = _preview(
        client,
        session_id,
        [
            {"type": "TITLE"},
            {"type": "KEY"},
            {"type": "BPM"},
            {"type": "VERSION"},
        ],
    )
    name = body["preview"][0]["preview_name"]
    assert name.count("Amin") == 1, name
    assert name.count("128") == 1, name
    assert name.upper().count("V1") == 1, name


def test_preview_streets_of_philly_no_duplicate_bpm(client, db):
    """Regression test for the original reported bug."""
    _login(client, db, suffix="strts")
    session_id = _upload(client, "Hurricane Wisdom - Streets of Philly 161BPM.mp3")

    body = _preview(
        client,
        session_id,
        [
            {"type": "PRODUCER", "value": "PMHITSS"},
            {"type": "TITLE"},
            {"type": "BPM"},
        ],
    )
    name = body["preview"][0]["preview_name"]
    assert name.count("161") == 1, name
    assert name.count("BPM") == 1, name
