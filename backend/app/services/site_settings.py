from typing import Optional

from sqlalchemy.orm import Session

from ..database.models import SiteSettings


def get_setting(db: Session, key: str, default: str = "") -> str:
    """Return the value for a site setting, or default if not set."""
    row = db.query(SiteSettings).filter(SiteSettings.key == key).first()
    return row.value if row else default


def set_setting(db: Session, key: str, value: str, admin_id: Optional[int] = None) -> None:
    """Create or update a site setting."""
    row = db.query(SiteSettings).filter(SiteSettings.key == key).first()
    if row:
        row.value = value
        row.updated_by_id = admin_id
    else:
        row = SiteSettings(key=key, value=value, updated_by_id=admin_id)
        db.add(row)
    db.commit()
