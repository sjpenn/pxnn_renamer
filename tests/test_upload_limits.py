import io

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.database.models import User
from backend.app.services.site_settings import set_setting


def _login(client, db, username="uploader"):
    user = User(username=username, email=f"{username}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)
    return user


def _file(name, size=64):
    return ("files", (name, io.BytesIO(b"\x00" * size), "application/octet-stream"))


def test_upload_rejects_disallowed_extension(client, db):
    _login(client, db)
    response = client.post("/api/wizard/upload", files=[_file("malware.exe")])
    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


def test_upload_accepts_allowed_audio_extension(client, db):
    _login(client, db)
    response = client.post("/api/wizard/upload", files=[_file("track.mp3")])
    assert response.status_code == 200, response.text


def test_upload_rejects_too_many_files(client, db):
    user = _login(client, db)
    set_setting(db, "max_upload_files", "3", admin_id=user.id)
    files = [_file(f"track{i}.mp3") for i in range(4)]
    response = client.post("/api/wizard/upload", files=files)
    assert response.status_code == 400
    assert "Too many files" in response.json()["detail"]


def test_upload_rejects_oversized_file(client, db):
    user = _login(client, db)
    set_setting(db, "max_upload_file_mb", "1", admin_id=user.id)
    big = ("files", ("big.wav", io.BytesIO(b"\x00" * (1024 * 1024 + 10)), "audio/wav"))
    response = client.post("/api/wizard/upload", files=[big])
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_upload_extension_allowlist_star_allows_everything(client, db):
    user = _login(client, db)
    set_setting(db, "allowed_upload_extensions", "*", admin_id=user.id)
    response = client.post("/api/wizard/upload", files=[_file("weird.xyz")])
    assert response.status_code == 200, response.text
