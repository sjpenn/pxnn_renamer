from datetime import datetime, timedelta

from backend.app.database.models import ActivityLog, User
from backend.app.services import admin_stats


def _user(db, **kw):
    kw.setdefault("password_hash", "x")
    kw.setdefault("created_at", datetime.utcnow())
    u = User(**kw)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _event(db, user_id, event_type, when=None):
    db.add(ActivityLog(
        user_id=user_id,
        event_type=event_type,
        summary=event_type,
        details_json="{}",
        created_at=when or datetime.utcnow(),
    ))
    db.commit()


def test_funnel_stats_counts_stages_in_window(db):
    u1 = _user(db, username="u1", email="u1@x.com")
    u2 = _user(db, username="u2", email="u2@x.com")
    _event(db, u1.id, "pricing_viewed")
    _event(db, u1.id, "plan_selected")
    _event(db, u1.id, "payment_started")
    _event(db, u1.id, "payment_completed")
    _event(db, u2.id, "pricing_viewed")

    result = admin_stats.funnel_stats(db, window_days=7)
    stages = {row["stage"]: row for row in result}
    assert stages["registered"]["users"] == 2
    assert stages["pricing_viewed"]["users"] == 2
    assert stages["plan_selected"]["users"] == 1
    assert stages["checkout_started"]["users"] == 1
    assert stages["payment_completed"]["users"] == 1
    assert stages["payment_completed"]["dropoff_pct"] == 0.0


def test_stuck_at_checkout_lists_non_completers(db):
    stuck = _user(db, username="stuck", email="stuck@x.com")
    done = _user(db, username="done", email="done@x.com")
    _event(db, stuck.id, "payment_started")
    _event(db, done.id, "payment_started")
    _event(db, done.id, "payment_completed")

    rows = admin_stats.stuck_at_checkout(db)
    usernames = {row["username"] for row in rows}
    assert "stuck" in usernames
    assert "done" not in usernames


def test_get_user_funnel_stage_returns_furthest(db):
    u = _user(db, username="furthest", email="f@x.com")
    _event(db, u.id, "pricing_viewed")
    _event(db, u.id, "payment_started")
    assert admin_stats.get_user_funnel_stage(db, u.id) == "checkout_started"

    _event(db, u.id, "payment_completed")
    assert admin_stats.get_user_funnel_stage(db, u.id) == "payment_completed"
