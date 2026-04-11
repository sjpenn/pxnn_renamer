from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import User


def _login_as(client, db, *, is_admin: bool):
    u = User(
        username="x",
        email="sjpenn@gmail.com" if is_admin else "regular@x.com",
        password_hash="x",
        is_admin=is_admin,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def test_admin_dashboard_requires_admin(client, db):
    _login_as(client, db, is_admin=False)
    r = client.get("/admin")
    assert r.status_code == 403


def test_admin_dashboard_ok_for_admin(client, db):
    _login_as(client, db, is_admin=True)
    r = client.get("/admin")
    assert r.status_code == 200
    assert "Admin" in r.text
