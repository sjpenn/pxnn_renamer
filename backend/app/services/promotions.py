from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..database.models import Promotion


def get_active_promotion(db: Session, plan_key: Optional[str] = None) -> Optional[Promotion]:
    """Return the active promotion, optionally filtered by plan_key."""
    now = datetime.utcnow()
    query = (
        db.query(Promotion)
        .filter(Promotion.is_active.is_(True))
        .filter((Promotion.starts_at.is_(None)) | (Promotion.starts_at <= now))
        .filter((Promotion.ends_at.is_(None)) | (Promotion.ends_at > now))
    )
    if plan_key:
        query = query.filter(Promotion.plan_key == plan_key)
    return query.order_by(Promotion.created_at.desc()).first()


def get_all_active_promotions(db: Session) -> list[Promotion]:
    """Return all currently active promotions."""
    now = datetime.utcnow()
    return (
        db.query(Promotion)
        .filter(Promotion.is_active.is_(True))
        .filter((Promotion.starts_at.is_(None)) | (Promotion.starts_at <= now))
        .filter((Promotion.ends_at.is_(None)) | (Promotion.ends_at > now))
        .order_by(Promotion.created_at.desc())
        .all()
    )
