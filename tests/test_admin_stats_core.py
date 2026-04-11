from datetime import datetime, timedelta

from backend.app.database.models import (
    ActivityLog,
    PaymentRecord,
    User,
    UserSession,
)
from backend.app.services import admin_stats


def _user(db, *, username, email, active_plan="free", plan_status="inactive",
          credit_balance=0, created_at=None):
    user = User(
        username=username,
        email=email,
        password_hash="x",
        active_plan=active_plan,
        plan_status=plan_status,
        credit_balance=credit_balance,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_user_counts_basic(db):
    _user(db, username="a", email="a@x.com")
    _user(db, username="b", email="b@x.com",
          created_at=datetime.utcnow() - timedelta(days=40))
    result = admin_stats.user_counts(db)
    assert result["total"] == 2
    assert result["new_today"] >= 1
    assert result["new_month"] >= 1


def test_revenue_stats_counts_paid_only(db):
    u = _user(db, username="buyer", email="b@x.com")
    db.add(PaymentRecord(
        user_id=u.id, plan_key="creator_pack", plan_type="one_time",
        amount_cents=1900, currency="usd", credits=10, status="paid",
        completed_at=datetime.utcnow(),
    ))
    db.add(PaymentRecord(
        user_id=u.id, plan_key="creator_pack", plan_type="one_time",
        amount_cents=1900, currency="usd", credits=10, status="pending",
    ))
    db.commit()
    result = admin_stats.revenue_stats(db)
    assert result["total_cents"] == 1900
    assert any(row["plan_key"] == "creator_pack" for row in result["by_plan"])


def test_plan_breakdown(db):
    _user(db, username="f1", email="f1@x.com", active_plan="free", plan_status="inactive")
    _user(db, username="p1", email="p1@x.com", active_plan="creator_pack", plan_status="active")
    _user(db, username="p2", email="p2@x.com", active_plan="label_monthly", plan_status="active")
    result = admin_stats.plan_breakdown(db)
    assert result["free"] == 1
    assert result["paid"] == 2


def test_credit_stats_sums_outstanding(db):
    _user(db, username="c1", email="c1@x.com", credit_balance=5)
    _user(db, username="c2", email="c2@x.com", credit_balance=7)
    result = admin_stats.credit_stats(db)
    assert result["outstanding"] == 12


def test_credit_stats_counts_batch_downloaded(db):
    u = _user(db, username="downloader", email="d@x.com", credit_balance=0)
    db.add(ActivityLog(
        user_id=u.id, event_type="batch_downloaded",
        summary="Archive exported", details_json="{}",
    ))
    db.commit()
    result = admin_stats.credit_stats(db)
    assert result["consumed_today"] == 1


def test_session_stats_counts_active_now(db):
    u = _user(db, username="live", email="live@x.com")
    db.add(UserSession(
        user_id=u.id,
        started_at=datetime.utcnow() - timedelta(minutes=2),
        last_seen_at=datetime.utcnow() - timedelta(seconds=30),
    ))
    db.commit()
    result = admin_stats.session_stats(db)
    assert result["active_now"] == 1


def test_session_stats_closes_stale_sessions(db):
    u = _user(db, username="stale", email="stale@x.com")
    db.add(UserSession(
        user_id=u.id,
        started_at=datetime.utcnow() - timedelta(hours=2),
        last_seen_at=datetime.utcnow() - timedelta(minutes=30),
    ))
    db.commit()
    admin_stats.session_stats(db)
    rotated = db.query(UserSession).first()
    assert rotated.ended_at is not None
    assert rotated.duration_seconds is not None
