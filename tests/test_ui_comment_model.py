from datetime import datetime

from backend.app.database.models import UIComment, User


def _user(db, email="admin@x.com", is_admin=True):
    u = User(username="admin", email=email, password_hash="x", is_admin=is_admin)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_ui_comment_defaults(db):
    author = _user(db)
    c = UIComment(
        author_id=author.id,
        block_key="dropzone",
        page_path="/app",
        body="Make the dropzone label bigger",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    assert c.id is not None
    assert c.status == "open"
    assert c.created_at is not None
    assert c.resolved_at is None


def test_ui_comment_can_be_resolved(db):
    author = _user(db)
    c = UIComment(
        author_id=author.id,
        block_key="wizard-step-1",
        page_path="/app",
        body="Reorder the steps",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    c.status = "resolved"
    c.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(c)

    assert c.status == "resolved"
    assert c.resolved_at is not None


def test_ui_comment_required_fields(db):
    # body, block_key, page_path, author_id are all NOT NULL
    author = _user(db)
    c = UIComment(
        author_id=author.id,
        block_key="export",
        page_path="/app",
        body="Test",
    )
    db.add(c)
    db.commit()
    assert c.id is not None
