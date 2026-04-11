from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import ActivityLog, User


def _auth_client(client, db, username="funnel_user", email="f@x.com"):
    user = User(username=username, email=email, password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(user.id)))
    return user


def _events(db, user_id, event_type):
    return (
        db.query(ActivityLog)
        .filter(ActivityLog.user_id == user_id, ActivityLog.event_type == event_type)
        .all()
    )


def test_home_logs_pricing_viewed_for_authed_user(client, db):
    user = _auth_client(client, db)
    client.post("/api/session/heartbeat")
    client.get("/")
    rows = _events(db, user.id, "pricing_viewed")
    assert len(rows) == 1


def test_pricing_viewed_dedups_within_same_session(client, db):
    user = _auth_client(client, db)
    client.post("/api/session/heartbeat")
    client.get("/")
    client.get("/")
    client.get("/")
    assert len(_events(db, user.id, "pricing_viewed")) == 1


def test_plan_selected_endpoint(client, db):
    user = _auth_client(client, db)
    client.post("/api/session/heartbeat")
    r = client.post("/api/funnel/plan-selected", data={"plan_key": "creator_pack"})
    assert r.status_code == 204
    rows = _events(db, user.id, "plan_selected")
    assert len(rows) == 1
    assert "creator_pack" in rows[0].summary


def test_checkout_abandoned_on_cancel_redirect(client, db):
    user = _auth_client(client, db)
    client.post("/api/session/heartbeat")
    client.get("/", params={"billing": "cancelled"})
    rows = _events(db, user.id, "checkout_abandoned")
    assert len(rows) == 1
