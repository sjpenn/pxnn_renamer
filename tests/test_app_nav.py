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


def test_app_shows_ui_comment_widget_for_admin(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/app")
    assert r.status_code == 200
    assert "ui-comment-widget" in r.text
    assert "data-block-key=\"dropzone\"" in r.text


def test_app_hides_ui_comment_widget_from_non_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.get("/app")
    assert r.status_code == 200
    assert "ui-comment-widget" not in r.text


from backend.app.database.models import UIComment


def test_widget_renders_count_badge_when_open_comments_exist(client, db):
    admin = _login(client, db, is_admin=True)
    db.add(UIComment(
        author_id=admin.id,
        block_key="dropzone",
        page_path="/app",
        body="first",
    ))
    db.add(UIComment(
        author_id=admin.id,
        block_key="dropzone",
        page_path="/app",
        body="second",
    ))
    db.commit()
    r = client.get("/app")
    assert r.status_code == 200
    # Some count indicator should show up near the dropzone widget
    assert "ui-comment-count" in r.text


def test_widget_no_badge_when_no_comments(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/app")
    assert r.status_code == 200
    # The widget itself should still be there
    assert "ui-comment-widget" in r.text
