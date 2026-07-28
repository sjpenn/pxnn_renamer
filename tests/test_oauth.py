import pytest
from backend.app.database.models import User, ActivityLog
from backend.app.routes.oauth import _resolve_or_create_google_user


def test_creates_new_user_from_google(db):
    user, is_new = _resolve_or_create_google_user(
        db, google_sub="sub_new", email="new@example.com", email_verified=True
    )
    assert is_new is True
    assert user.id is not None
    assert user.google_sub == "sub_new"
    assert user.email == "new@example.com"
    assert user.password_hash is None


def test_returns_existing_user_by_google_sub(db):
    existing = User(username="existing", google_sub="sub_exists", email="e@x.com", password_hash=None)
    db.add(existing)
    db.commit()

    result, is_new = _resolve_or_create_google_user(
        db, google_sub="sub_exists", email="e@x.com", email_verified=True
    )
    assert is_new is False
    assert result.id == existing.id


def test_links_google_to_existing_email_user(db):
    existing = User(username="emailuser", password_hash="hashed", email="link@x.com", google_sub=None)
    db.add(existing)
    db.commit()

    result, is_new = _resolve_or_create_google_user(
        db, google_sub="sub_link", email="link@x.com", email_verified=True
    )
    assert is_new is False
    assert result.id == existing.id
    assert result.google_sub == "sub_link"


def test_does_not_link_unverified_email_to_existing_user(db):
    """An unverified Google email must NOT link to an existing account
    (account-takeover guard) — a new, separate user is created instead."""
    existing = User(username="victim", password_hash="hashed", email="victim@x.com", google_sub=None)
    db.add(existing)
    db.commit()

    result, is_new = _resolve_or_create_google_user(
        db, google_sub="sub_attacker", email="victim@x.com", email_verified=False
    )
    assert is_new is True
    assert result.id != existing.id
    assert existing.google_sub is None


def test_creates_unique_username_on_collision(db):
    # Create a user that will collide with the derived username
    db.add(User(username="artist", password_hash="hashed", email="other@x.com"))
    db.commit()

    user, is_new = _resolve_or_create_google_user(
        db, google_sub="sub_coll", email="artist@example.com", email_verified=True
    )
    assert is_new is True
    # Should not be exactly "artist" since that's taken
    assert user.username != "artist"
    assert "artist" in user.username


def test_logs_account_created_activity(db):
    _resolve_or_create_google_user(db, google_sub="sub_log", email="log@x.com", email_verified=True)
    log = db.query(ActivityLog).filter(ActivityLog.event_type == "account_created").first()
    assert log is not None


def test_resolve_creates_new_user_no_email(db):
    """When email is None or empty, creates a user with a fallback username."""
    user, is_new = _resolve_or_create_google_user(db, google_sub="sub_noemail", email=None)
    assert is_new is True
    assert user is not None
    assert user.google_sub == "sub_noemail"
    assert user.password_hash is None
    assert user.username is not None
