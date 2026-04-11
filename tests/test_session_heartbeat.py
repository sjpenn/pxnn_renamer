from datetime import datetime, timedelta

from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import User, UserSession


def _login(client, db):
    user = User(username="ping_user", email="ping@example.com", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)
    return user


def test_heartbeat_requires_auth(client):
    r = client.post("/api/session/heartbeat")
    assert r.status_code == 401


def test_heartbeat_opens_new_session(client, db):
    user = _login(client, db)
    r = client.post("/api/session/heartbeat")
    assert r.status_code == 204
    sessions = db.query(UserSession).filter(UserSession.user_id == user.id).all()
    assert len(sessions) == 1
    assert sessions[0].ended_at is None


def test_second_heartbeat_extends_existing_session(client, db):
    user = _login(client, db)
    client.post("/api/session/heartbeat")
    client.post("/api/session/heartbeat")
    sessions = db.query(UserSession).filter(UserSession.user_id == user.id).all()
    assert len(sessions) == 1


def test_stale_session_rotates_on_next_heartbeat(client, db):
    user = _login(client, db)
    client.post("/api/session/heartbeat")
    stale_session = db.query(UserSession).filter(UserSession.user_id == user.id).first()
    stale_session.last_seen_at = datetime.utcnow() - timedelta(minutes=30)
    db.commit()

    client.post("/api/session/heartbeat")
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id)
        .order_by(UserSession.id.asc())
        .all()
    )
    assert len(sessions) == 2
    assert sessions[0].ended_at is not None
    assert sessions[0].duration_seconds is not None
    assert sessions[1].ended_at is None
