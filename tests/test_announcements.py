from datetime import datetime, timedelta

from backend.app.database.models import Announcement, User
from backend.app.services.announcements import get_active_announcement


def _user(db):
    u = User(username="viewer", email="v@x.com", password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_returns_none_when_nothing_published(db):
    assert get_active_announcement(db, user=_user(db)) is None


def test_returns_published_announcement(db):
    db.add(Announcement(title="Hi", body="Body", severity="info", is_published=True))
    db.commit()
    result = get_active_announcement(db, user=_user(db))
    assert result is not None
    assert result.title == "Hi"


def test_skips_unpublished(db):
    db.add(Announcement(title="Draft", body="B", is_published=False))
    db.commit()
    assert get_active_announcement(db, user=_user(db)) is None


def test_respects_start_window(db):
    future = datetime.utcnow() + timedelta(hours=1)
    db.add(Announcement(title="Later", body="B", is_published=True, starts_at=future))
    db.commit()
    assert get_active_announcement(db, user=_user(db)) is None


def test_respects_end_window(db):
    past = datetime.utcnow() - timedelta(hours=1)
    db.add(Announcement(title="Done", body="B", is_published=True, ends_at=past))
    db.commit()
    assert get_active_announcement(db, user=_user(db)) is None


def test_newest_wins_when_multiple_active(db):
    db.add(Announcement(title="Old", body="B", is_published=True))
    db.commit()
    db.add(Announcement(title="New", body="B", is_published=True))
    db.commit()
    result = get_active_announcement(db, user=_user(db))
    assert result.title == "New"
