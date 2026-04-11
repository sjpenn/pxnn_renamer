"""Admin analytics aggregation queries.

All functions take a SQLAlchemy Session and return plain dicts. No routing,
no templating — just aggregation. The router layer in routes/admin.py calls
these and renders the results.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database.models import (
    ActivityLog,
    PaymentRecord,
    User,
    UserSession,
)

ACTIVE_NOW_WINDOW = timedelta(minutes=5)
IDLE_TIMEOUT = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.utcnow()


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
def user_counts(db: Session) -> dict:
    now = _now()
    total = db.query(func.count(User.id)).scalar() or 0

    def _new_since(delta: timedelta) -> int:
        cutoff = now - delta
        return db.query(func.count(User.id)).filter(User.created_at >= cutoff).scalar() or 0

    def _active_since(delta: timedelta) -> int:
        cutoff = now - delta
        return (
            db.query(func.count(func.distinct(ActivityLog.user_id)))
            .filter(ActivityLog.created_at >= cutoff)
            .scalar()
            or 0
        )

    return {
        "total": total,
        "new_today": _new_since(timedelta(days=1)),
        "new_week": _new_since(timedelta(days=7)),
        "new_month": _new_since(timedelta(days=30)),
        "active_today": _active_since(timedelta(days=1)),
        "active_week": _active_since(timedelta(days=7)),
    }


# --------------------------------------------------------------------------- #
# Revenue
# --------------------------------------------------------------------------- #
def revenue_stats(db: Session) -> dict:
    now = _now()

    def _sum_since(delta) -> int:
        q = db.query(func.coalesce(func.sum(PaymentRecord.amount_cents), 0)).filter(
            PaymentRecord.status == "paid"
        )
        if delta is not None:
            q = q.filter(PaymentRecord.completed_at >= now - delta)
        return int(q.scalar() or 0)

    by_plan_rows = (
        db.query(
            PaymentRecord.plan_key,
            func.count(PaymentRecord.id),
            func.coalesce(func.sum(PaymentRecord.amount_cents), 0),
        )
        .filter(PaymentRecord.status == "paid")
        .group_by(PaymentRecord.plan_key)
        .all()
    )

    return {
        "total_cents": _sum_since(None),
        "today_cents": _sum_since(timedelta(days=1)),
        "week_cents": _sum_since(timedelta(days=7)),
        "month_cents": _sum_since(timedelta(days=30)),
        "by_plan": [
            {"plan_key": row[0], "count": int(row[1]), "amount_cents": int(row[2])}
            for row in by_plan_rows
        ],
    }


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #
def plan_breakdown(db: Session) -> dict:
    rows = (
        db.query(User.active_plan, User.plan_status, func.count(User.id))
        .group_by(User.active_plan, User.plan_status)
        .all()
    )
    buckets = {"free": 0, "trial": 0, "paid": 0, "by_key": {}}
    for active_plan, plan_status, count in rows:
        count = int(count)
        key = f"{active_plan or 'unknown'}::{plan_status or 'unknown'}"
        buckets["by_key"][key] = buckets["by_key"].get(key, 0) + count
        if plan_status == "trialing":
            buckets["trial"] += count
        elif plan_status == "active" and (active_plan or "free") != "free":
            buckets["paid"] += count
        else:
            buckets["free"] += count
    return buckets


# --------------------------------------------------------------------------- #
# Credits
# --------------------------------------------------------------------------- #
def credit_stats(db: Session) -> dict:
    now = _now()
    outstanding = int(
        db.query(func.coalesce(func.sum(User.credit_balance), 0)).scalar() or 0
    )

    def _consumed(delta: timedelta) -> int:
        cutoff = now - delta
        return (
            db.query(func.count(ActivityLog.id))
            .filter(
                ActivityLog.event_type == "batch_downloaded",
                ActivityLog.created_at >= cutoff,
            )
            .scalar()
            or 0
        )

    return {
        "outstanding": outstanding,
        "consumed_today": _consumed(timedelta(days=1)),
        "consumed_week": _consumed(timedelta(days=7)),
        "consumed_month": _consumed(timedelta(days=30)),
    }


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #
def _close_stale_sessions(db: Session) -> None:
    cutoff = _now() - IDLE_TIMEOUT
    stale = (
        db.query(UserSession)
        .filter(
            UserSession.ended_at.is_(None),
            UserSession.last_seen_at < cutoff,
        )
        .all()
    )
    for s in stale:
        s.ended_at = s.last_seen_at
        s.duration_seconds = int(max(0, (s.last_seen_at - s.started_at).total_seconds()))
    if stale:
        db.commit()


def session_stats(db: Session) -> dict:
    _close_stale_sessions(db)
    now = _now()

    active_now = (
        db.query(func.count(UserSession.id))
        .filter(
            UserSession.ended_at.is_(None),
            UserSession.last_seen_at >= now - ACTIVE_NOW_WINDOW,
        )
        .scalar()
        or 0
    )

    def _sessions_since(delta: timedelta) -> int:
        return (
            db.query(func.count(UserSession.id))
            .filter(UserSession.started_at >= now - delta)
            .scalar()
            or 0
        )

    def _avg_duration_since(delta: timedelta) -> int:
        avg = (
            db.query(func.avg(UserSession.duration_seconds))
            .filter(
                UserSession.duration_seconds.isnot(None),
                UserSession.started_at >= now - delta,
            )
            .scalar()
        )
        return int(avg or 0)

    return {
        "active_now": int(active_now),
        "sessions_today": _sessions_since(timedelta(days=1)),
        "sessions_week": _sessions_since(timedelta(days=7)),
        "sessions_month": _sessions_since(timedelta(days=30)),
        "avg_duration_today_s": _avg_duration_since(timedelta(days=1)),
        "avg_duration_week_s": _avg_duration_since(timedelta(days=7)),
        "avg_duration_month_s": _avg_duration_since(timedelta(days=30)),
    }


# --------------------------------------------------------------------------- #
# Activity feed
# --------------------------------------------------------------------------- #
def recent_activity(db: Session, limit: int = 50) -> List[dict]:
    rows = (
        db.query(ActivityLog, User.username, User.email)
        .join(User, ActivityLog.user_id == User.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "username": username,
            "email": email,
            "event_type": a.event_type,
            "summary": a.summary,
            "created_at": a.created_at,
        }
        for a, username, email in rows
    ]


# --------------------------------------------------------------------------- #
# Funnel
# --------------------------------------------------------------------------- #
# Map our ordered funnel stages to the event_type values that gate them.
# Some stages (registered) derive from User.created_at rather than an event.
_FUNNEL_EVENT_BY_STAGE = {
    "pricing_viewed": "pricing_viewed",
    "plan_selected": "plan_selected",
    "checkout_started": "payment_started",
    "payment_completed": "payment_completed",
}
_FUNNEL_STAGE_ORDER = (
    "registered",
    "pricing_viewed",
    "plan_selected",
    "checkout_started",
    "payment_completed",
)
# Stage priority for get_user_funnel_stage (higher wins)
_STAGE_PRIORITY = {stage: i for i, stage in enumerate(_FUNNEL_STAGE_ORDER)}


def funnel_stats(db: Session, window_days: int = 7) -> List[dict]:
    now = _now()
    cutoff = now - timedelta(days=window_days)

    counts: dict[str, int] = {}
    counts["registered"] = (
        db.query(func.count(User.id)).filter(User.created_at >= cutoff).scalar() or 0
    )
    for stage, event_type in _FUNNEL_EVENT_BY_STAGE.items():
        counts[stage] = (
            db.query(func.count(func.distinct(ActivityLog.user_id)))
            .filter(
                ActivityLog.event_type == event_type,
                ActivityLog.created_at >= cutoff,
            )
            .scalar()
            or 0
        )

    result = []
    prev = None
    for stage in _FUNNEL_STAGE_ORDER:
        users = int(counts.get(stage, 0))
        if prev is None or prev == 0:
            pct_of_prev = 100.0 if users else 0.0
            dropoff = 0.0
        else:
            pct_of_prev = round((users / prev) * 100.0, 1)
            dropoff = round(((prev - users) / prev) * 100.0, 1)
        result.append(
            {
                "stage": stage,
                "users": users,
                "pct_of_prev": pct_of_prev,
                "dropoff_pct": dropoff,
            }
        )
        prev = users

    # Final stage has no "next" — zero drop-off by definition.
    if result:
        result[-1]["dropoff_pct"] = 0.0
    return result


def stuck_at_checkout(db: Session, limit: int = 20) -> List[dict]:
    """Users whose furthest stage is plan_selected or checkout_started."""
    stuck_event_types = {"plan_selected", "payment_started"}
    completers = {
        row[0]
        for row in db.query(ActivityLog.user_id)
        .filter(ActivityLog.event_type == "payment_completed")
        .all()
    }

    candidates = (
        db.query(ActivityLog, User)
        .join(User, ActivityLog.user_id == User.id)
        .filter(ActivityLog.event_type.in_(stuck_event_types))
        .order_by(ActivityLog.created_at.desc())
        .all()
    )

    seen: set[int] = set()
    rows: list[dict] = []
    for log, user in candidates:
        if user.id in seen or user.id in completers:
            continue
        seen.add(user.id)
        rows.append(
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "last_stage": "checkout_started"
                if log.event_type == "payment_started"
                else "plan_selected",
                "last_stage_at": log.created_at,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def get_user_funnel_stage(db: Session, user_id: int) -> str:
    """Return the furthest funnel stage a given user has reached."""
    stage = "registered"
    events = (
        db.query(ActivityLog.event_type)
        .filter(ActivityLog.user_id == user_id)
        .all()
    )
    for (event_type,) in events:
        for stage_name, event_name in _FUNNEL_EVENT_BY_STAGE.items():
            if event_type == event_name:
                if _STAGE_PRIORITY[stage_name] > _STAGE_PRIORITY[stage]:
                    stage = stage_name
    return stage
