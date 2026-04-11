"""Purchase funnel helpers.

Logs stage transitions as ActivityLog rows, deduped per UserSession so a user
refreshing a page doesn't spam the funnel.
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from ..database.models import ActivityLog, User, UserSession

# Stage order for the funnel — earlier stages are lower priority.
FUNNEL_STAGES = (
    "registered",
    "pricing_viewed",
    "plan_selected",
    "checkout_started",
    "checkout_abandoned",
    "payment_completed",
)


def _current_session_id(db: Session, user_id: int) -> Optional[int]:
    open_session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.ended_at.is_(None),
        )
        .order_by(UserSession.last_seen_at.desc())
        .first()
    )
    return open_session.id if open_session else None


def _already_logged_this_session(
    db: Session, user_id: int, event_type: str, session_id: Optional[int]
) -> bool:
    if session_id is None:
        return False
    q = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.user_id == user_id,
            ActivityLog.event_type == event_type,
            ActivityLog.details_json.like(f'%"session_id": {session_id}%'),
        )
    )
    return db.query(q.exists()).scalar()


def log_funnel_event(
    db: Session,
    user: User,
    event_type: str,
    summary: str,
    extra: Optional[dict] = None,
) -> bool:
    """Insert a deduped funnel ActivityLog row. Returns True if inserted."""
    session_id = _current_session_id(db, user.id)
    if _already_logged_this_session(db, user.id, event_type, session_id):
        return False

    details = {"session_id": session_id}
    if extra:
        details.update(extra)

    db.add(
        ActivityLog(
            user_id=user.id,
            event_type=event_type,
            summary=summary,
            details_json=json.dumps(details),
        )
    )
    db.commit()
    return True
