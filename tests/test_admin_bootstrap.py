"""Founder-account auto-promotion at startup (promote_configured_admin)."""
from backend.app.core import config as config_module
from backend.app.database.bootstrap import promote_configured_admin
from backend.app.database.models import User


def _promote(monkeypatch, db, admin_identifier):
    monkeypatch.setattr(
        config_module.settings, "ADMIN_BOOTSTRAP_EMAIL", admin_identifier
    )
    promote_configured_admin(db)


def test_promotes_account_where_email_in_username_field(monkeypatch, db):
    """Password-registered founders store their email in `username` (email NULL)."""
    u = User(username="sjpenn@gmail.com", email=None, password_hash="x", is_admin=False)
    db.add(u)
    db.commit()

    _promote(monkeypatch, db, "sjpenn@gmail.com")

    db.refresh(u)
    assert u.is_admin is True


def test_promotes_account_by_email_column(monkeypatch, db):
    u = User(username="boss", email="sjpenn@gmail.com", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()

    _promote(monkeypatch, db, "sjpenn@gmail.com")

    db.refresh(u)
    assert u.is_admin is True


def test_case_insensitive_match(monkeypatch, db):
    u = User(username="SJPenn@Gmail.com", email=None, password_hash="x", is_admin=False)
    db.add(u)
    db.commit()

    _promote(monkeypatch, db, "sjpenn@gmail.com")

    db.refresh(u)
    assert u.is_admin is True


def test_does_not_promote_unrelated_account(monkeypatch, db):
    u = User(username="someoneelse", email="other@x.com", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()

    _promote(monkeypatch, db, "sjpenn@gmail.com")

    db.refresh(u)
    assert u.is_admin is False


def test_empty_identifier_is_noop(monkeypatch, db):
    u = User(username="sjpenn@gmail.com", email=None, password_hash="x", is_admin=False)
    db.add(u)
    db.commit()

    _promote(monkeypatch, db, "")

    db.refresh(u)
    assert u.is_admin is False
