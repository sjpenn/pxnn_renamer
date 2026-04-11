from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import User


def _login(client, db, is_admin: bool):
    u = User(username="u", email="u@x.com", password_hash="x", is_admin=is_admin)
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def test_app_shows_admin_link_for_admin(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/app")
    assert r.status_code == 200
    assert 'href="/admin"' in r.text


def test_app_hides_admin_link_for_non_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.get("/app")
    assert r.status_code == 200
    assert 'href="/admin"' not in r.text
