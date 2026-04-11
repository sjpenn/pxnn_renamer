from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import Announcement, User


def _login(client, db, *, is_admin: bool):
    u = User(
        username="announcer", email="announcer@x.com", password_hash="x", is_admin=is_admin
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def test_create_announcement_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.post("/admin/announcements", data={"title": "T", "body": "B", "severity": "info"})
    assert r.status_code == 403


def test_admin_can_create_publish_delete(client, db):
    _login(client, db, is_admin=True)
    r = client.post(
        "/admin/announcements",
        data={"title": "Launch", "body": "We're live", "severity": "success"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)

    created = db.query(Announcement).first()
    assert created is not None
    assert created.is_published is False

    r = client.post(f"/admin/announcements/{created.id}/publish", follow_redirects=False)
    assert r.status_code in (200, 303)
    db.refresh(created)
    assert created.is_published is True

    r = client.post(f"/admin/announcements/{created.id}/delete", follow_redirects=False)
    assert r.status_code in (200, 303)
    assert db.query(Announcement).count() == 0
