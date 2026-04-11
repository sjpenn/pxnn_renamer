from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import UIComment, User


def _login(client, db, *, is_admin: bool):
    u = User(
        username=("admin" if is_admin else "normie"),
        email=("sjpenn@gmail.com" if is_admin else "n@x.com"),
        password_hash="x",
        is_admin=is_admin,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def test_create_comment_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.post(
        "/api/admin/ui-comments",
        data={"block_key": "dropzone", "page_path": "/app", "body": "nope"},
    )
    assert r.status_code == 403


def test_create_comment_success(client, db):
    admin = _login(client, db, is_admin=True)
    r = client.post(
        "/api/admin/ui-comments",
        data={
            "block_key": "dropzone",
            "page_path": "/app",
            "body": "Dropzone label should be bigger",
        },
    )
    assert r.status_code == 204

    row = db.query(UIComment).first()
    assert row is not None
    assert row.author_id == admin.id
    assert row.block_key == "dropzone"
    assert row.page_path == "/app"
    assert row.body == "Dropzone label should be bigger"
    assert row.status == "open"


def test_list_page_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.get("/admin/ui-comments")
    assert r.status_code == 403


def test_list_page_shows_comments(client, db):
    admin = _login(client, db, is_admin=True)
    db.add(UIComment(
        author_id=admin.id,
        block_key="wizard-step-1",
        page_path="/app",
        body="Reorder steps",
    ))
    db.commit()
    r = client.get("/admin/ui-comments")
    assert r.status_code == 200
    assert "wizard-step-1" in r.text
    assert "Reorder steps" in r.text


def test_resolve_toggles_status(client, db):
    admin = _login(client, db, is_admin=True)
    c = UIComment(
        author_id=admin.id,
        block_key="dropzone",
        page_path="/app",
        body="x",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.post(f"/admin/ui-comments/{c.id}/resolve", follow_redirects=False)
    assert r.status_code == 303
    db.refresh(c)
    assert c.status == "resolved"
    assert c.resolved_at is not None

    r = client.post(f"/admin/ui-comments/{c.id}/resolve", follow_redirects=False)
    db.refresh(c)
    assert c.status == "open"
    assert c.resolved_at is None


def test_delete_removes_comment(client, db):
    admin = _login(client, db, is_admin=True)
    c = UIComment(
        author_id=admin.id,
        block_key="dropzone",
        page_path="/app",
        body="x",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.post(f"/admin/ui-comments/{c.id}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert db.query(UIComment).count() == 0
