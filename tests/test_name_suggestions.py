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
        session_id=f"seed-{user.id}",
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
            external_id=f"ext-{user.id}-{index}",
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

    other = User(username="b_user", email="b@x.com", password_hash="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    _seed_history(db, other, [("Artist B", [], datetime.utcnow())])

    response = client.get("/api/suggestions/artists")
    assert response.status_code == 200
    values = response.json()["values"]
    assert values == ["Artist A"]
