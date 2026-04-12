from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import ActivityLog, User


def _login_as(client, db, *, is_admin: bool, email="sjpenn@gmail.com"):
    u = User(
        username="admin_x" if is_admin else "regular_x",
        email=email if is_admin else "regular@x.com",
        password_hash="x",
        is_admin=is_admin,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def _make_user(db, username, email, **kw):
    u = User(username=username, email=email, password_hash="x", **kw)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_users_page_requires_admin(client, db):
    _login_as(client, db, is_admin=False)
    r = client.get("/admin/users")
    assert r.status_code == 403


def test_users_page_lists_all_users(client, db):
    _login_as(client, db, is_admin=True)
    _make_user(db, "alice", "alice@x.com")
    _make_user(db, "bob", "bob@x.com")
    r = client.get("/admin/users")
    assert r.status_code == 200
    assert "alice" in r.text
    assert "bob" in r.text


def test_users_page_search_filters(client, db):
    _login_as(client, db, is_admin=True)
    _make_user(db, "alice", "alice@x.com")
    _make_user(db, "bob", "bob@x.com")
    r = client.get("/admin/users", params={"q": "alice"})
    assert r.status_code == 200
    assert "alice" in r.text
    assert "bob" not in r.text


def test_grant_credits_requires_admin(client, db):
    _login_as(client, db, is_admin=False)
    target = _make_user(db, "t", "t@x.com", credit_balance=0)
    r = client.post(f"/admin/users/{target.id}/credits", data={"amount": "5"})
    assert r.status_code == 403


def test_grant_credits_adds_to_balance(client, db):
    _login_as(client, db, is_admin=True)
    target = _make_user(db, "t", "t@x.com", credit_balance=2)
    r = client.post(
        f"/admin/users/{target.id}/credits",
        data={"amount": "5"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(target)
    assert target.credit_balance == 7
    logs = db.query(ActivityLog).filter(
        ActivityLog.user_id == target.id,
        ActivityLog.event_type == "admin_credit_grant",
    ).all()
    assert len(logs) == 1


def test_grant_credits_rejects_non_positive(client, db):
    _login_as(client, db, is_admin=True)
    target = _make_user(db, "t", "t@x.com", credit_balance=1)
    r = client.post(
        f"/admin/users/{target.id}/credits",
        data={"amount": "0"},
        follow_redirects=False,
    )
    assert r.status_code == 400
    db.refresh(target)
    assert target.credit_balance == 1


def test_toggle_testing_flips_flag(client, db):
    _login_as(client, db, is_admin=True)
    target = _make_user(db, "t", "t@x.com", is_testing=False)
    r = client.post(
        f"/admin/users/{target.id}/testing",
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(target)
    assert target.is_testing is True

    r = client.post(
        f"/admin/users/{target.id}/testing",
        follow_redirects=False,
    )
    db.refresh(target)
    assert target.is_testing is False

    logs = db.query(ActivityLog).filter(
        ActivityLog.user_id == target.id,
        ActivityLog.event_type == "admin_testing_toggled",
    ).all()
    assert len(logs) == 2


def test_toggle_admin_promotes_and_demotes(client, db):
    _login_as(client, db, is_admin=True)
    target = _make_user(db, "newadmin", "newadmin@x.com", is_admin=False)

    r = client.post(f"/admin/users/{target.id}/admin", follow_redirects=False)
    assert r.status_code == 303
    db.refresh(target)
    assert target.is_admin is True

    r = client.post(f"/admin/users/{target.id}/admin", follow_redirects=False)
    db.refresh(target)
    assert target.is_admin is False

    logs = db.query(ActivityLog).filter(
        ActivityLog.user_id == target.id,
        ActivityLog.event_type == "admin_role_toggled",
    ).all()
    assert len(logs) == 2


def test_cannot_toggle_own_admin(client, db):
    admin = _login_as(client, db, is_admin=True)
    r = client.post(f"/admin/users/{admin.id}/admin", follow_redirects=False)
    assert r.status_code == 400


def test_toggle_admin_requires_admin(client, db):
    _login_as(client, db, is_admin=False)
    target = _make_user(db, "t", "t@x.com")
    r = client.post(f"/admin/users/{target.id}/admin")
    assert r.status_code == 403
