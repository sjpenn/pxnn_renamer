from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..database.models import Announcement, User


def get_active_announcement(db: Session, user: Optional[User] = None) -> Optional[Announcement]:
    """Return the newest announcement that is currently published and in-window.

    Phase 1: ignores target_* columns — every published announcement in its
    time window is shown to everyone. Phase 2 will filter by user state.
    """
    now = datetime.utcnow()
    query = (
        db.query(Announcement)
        .filter(Announcement.is_published.is_(True))
        .filter((Announcement.starts_at.is_(None)) | (Announcement.starts_at <= now))
        .filter((Announcement.ends_at.is_(None)) | (Announcement.ends_at >= now))
        .order_by(Announcement.created_at.desc())
    )
    return query.first()
