from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import CommentCluster, UIComment, User


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


def test_todos_page_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.get("/admin/todos")
    assert r.status_code == 403


def test_todos_page_renders_empty_state(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/admin/todos")
    assert r.status_code == 200
    assert "Todos" in r.text


def test_todos_page_shows_ungrouped_notes(client, db):
    admin = _login(client, db, is_admin=True)
    db.add(UIComment(
        author_id=admin.id,
        block_key="dropzone",
        page_path="/app",
        body="Make dropzone bigger",
    ))
    db.commit()
    r = client.get("/admin/todos")
    assert r.status_code == 200
    assert "Make dropzone bigger" in r.text


def test_todos_page_shows_clustered_notes(client, db):
    admin = _login(client, db, is_admin=True)
    cluster = CommentCluster(title="Dropzone feedback", summary="Users want a bigger target")
    db.add(cluster)
    db.commit()
    db.refresh(cluster)

    note = UIComment(
        author_id=admin.id,
        block_key="dropzone",
        page_path="/app",
        body="Make dropzone bigger",
        cluster_id=cluster.id,
    )
    db.add(note)
    db.commit()

    r = client.get("/admin/todos")
    assert r.status_code == 200
    assert "Dropzone feedback" in r.text
    assert "Make dropzone bigger" in r.text


def test_status_transition_open_to_in_progress(client, db):
    admin = _login(client, db, is_admin=True)
    c = UIComment(
        author_id=admin.id,
        block_key="x",
        page_path="/app",
        body="y",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.post(
        f"/admin/todos/{c.id}/status",
        data={"status": "in_progress"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(c)
    assert c.status == "in_progress"


def test_status_transition_to_done_sets_resolved_at(client, db):
    from datetime import datetime

    admin = _login(client, db, is_admin=True)
    c = UIComment(
        author_id=admin.id,
        block_key="x",
        page_path="/app",
        body="y",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.post(
        f"/admin/todos/{c.id}/status",
        data={"status": "done"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(c)
    assert c.status == "done"
    assert c.resolved_at is not None


def test_status_invalid_value_rejected(client, db):
    admin = _login(client, db, is_admin=True)
    c = UIComment(
        author_id=admin.id,
        block_key="x",
        page_path="/app",
        body="y",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.post(
        f"/admin/todos/{c.id}/status",
        data={"status": "bogus"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_old_ui_comments_url_redirects_to_todos(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/admin/ui-comments", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/todos"
