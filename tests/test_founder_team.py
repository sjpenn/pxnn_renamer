"""Founder-console admin & tester management."""
from backend.app.core.config import settings
from backend.app.core.security import create_access_token, has_unlimited_access
from backend.app.database.models import User


def _login_as_admin(client, db, email="sjpenn@gmail.com"):
    admin = User(username="boss", email=email, password_hash="x", is_admin=True)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(admin.id)))
    return admin


def _make_user(db, username, email, **kw):
    u = User(username=username, email=email, password_hash="x", **kw)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_assign_admin_by_email(client, db):
    _login_as_admin(client, db)
    target = _make_user(db, "alice", "alice@x.com")
    r = client.post(
        "/admin/founder/assign-admin",
        data={"username": "alice@x.com"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(target)
    assert target.is_admin is True


def test_assign_tester_grants_unlimited_access(client, db):
    _login_as_admin(client, db)
    target = _make_user(db, "beta", "beta@x.com", credit_balance=0)
    assert has_unlimited_access(target) is False

    r = client.post(
        "/admin/founder/assign-tester",
        data={"username": "beta"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(target)
    assert target.is_testing is True
    assert has_unlimited_access(target) is True


def test_revoke_tester(client, db):
    _login_as_admin(client, db)
    target = _make_user(db, "beta", "beta@x.com", is_testing=True)
    r = client.post(
        f"/admin/founder/revoke-tester/{target.id}",
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(target)
    assert target.is_testing is False


def test_cannot_revoke_own_admin(client, db):
    admin = _login_as_admin(client, db)
    r = client.post(
        f"/admin/founder/revoke-admin/{admin.id}",
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(admin)
    assert admin.is_admin is True  # still admin


def test_assign_admin_requires_admin(client, db):
    # Non-admin logged in
    user = _make_user(db, "normie", "normie@x.com", is_admin=False)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(user.id)))
    target = _make_user(db, "alice", "alice@x.com")
    r = client.post("/admin/founder/assign-admin", data={"username": "alice"})
    assert r.status_code == 403


def test_assign_admin_unknown_user_reports_error(client, db):
    _login_as_admin(client, db)
    r = client.post(
        "/admin/founder/assign-admin",
        data={"username": "ghost@nowhere.com"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "User+not+found" in r.headers["location"]


def test_audit_page_renders_with_entries(client, db):
    from backend.app.services.audit import record_audit

    admin = _login_as_admin(client, db)
    target = _make_user(db, "alice", "alice@x.com")
    record_audit(
        db,
        action="admin.promote",
        category="admin",
        summary="Promoted alice to admin",
        actor=admin,
        target=target,
        entity_type="user",
        entity_id=target.id,
        before={"is_admin": False},
        after={"is_admin": True},
    )
    db.commit()

    r = client.get("/admin/audit")
    assert r.status_code == 200
    assert "admin.promote" in r.text
    assert "Promoted alice to admin" in r.text


def test_audit_page_filters_by_category(client, db):
    from backend.app.services.audit import record_audit

    admin = _login_as_admin(client, db)
    record_audit(db, action="auth.login", category="auth", summary="logged in", actor=admin)
    record_audit(db, action="billing.charge", category="billing", summary="charged", actor=admin)
    db.commit()

    r = client.get("/admin/audit?category=billing")
    assert r.status_code == 200
    assert "charged" in r.text
    assert "logged in" not in r.text


def test_audit_export_returns_csv(client, db):
    from backend.app.services.audit import record_audit

    admin = _login_as_admin(client, db)
    record_audit(db, action="files.export", category="files", summary="exported zip", actor=admin)
    db.commit()

    r = client.get("/admin/audit/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "files.export" in r.text
    assert "exported zip" in r.text


def test_audit_page_requires_admin(client, db):
    user = _make_user(db, "normie", "normie2@x.com", is_admin=False)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(user.id)))
    r = client.get("/admin/audit", follow_redirects=False)
    assert r.status_code in (302, 303, 403)


def test_subscriber_has_unlimited_access(db):
    """Active monthly-unlimited subscribers bypass the paywall without is_testing."""
    u = User(
        username="sub", email="sub@x.com", password_hash="x",
        is_testing=False, credit_balance=0,
        subscription_status="active", subscription_plan="monthly_unlimited",
    )
    assert has_unlimited_access(u) is True

    # Inactive subscription does not grant access.
    u.subscription_status = "canceled"
    assert has_unlimited_access(u) is False
