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
    assert "Hurricane" in preview["preview_name"]
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
    assert "Hurricane" in preview_name
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
