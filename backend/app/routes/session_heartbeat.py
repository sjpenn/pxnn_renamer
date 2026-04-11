import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import get_current_user
from ..database.models import User, UserSession
from ..database.session import get_db

router = APIRouter(tags=["session"])

IDLE_TIMEOUT = timedelta(minutes=15)


def _hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    salted = f"{ip}:{settings.JWT_SECRET}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


@router.post("/api/session/heartbeat", status_code=204)
async def heartbeat(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    now = datetime.utcnow()
    cutoff = now - IDLE_TIMEOUT

    open_session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == current_user.id,
            UserSession.ended_at.is_(None),
        )
        .order_by(UserSession.last_seen_at.desc())
        .first()
    )

    if open_session and open_session.last_seen_at >= cutoff:
        open_session.last_seen_at = now
        db.commit()
        return Response(status_code=204)

    # Close any stale open sessions for this user
    stale = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == current_user.id,
            UserSession.ended_at.is_(None),
        )
        .all()
    )
    for s in stale:
        s.ended_at = s.last_seen_at
        s.duration_seconds = int(max(0, (s.last_seen_at - s.started_at).total_seconds()))

    user_agent = request.headers.get("user-agent", "")[:500] or None
    client_ip = request.client.host if request.client else None
    new_session = UserSession(
        user_id=current_user.id,
        started_at=now,
        last_seen_at=now,
        user_agent=user_agent,
        ip_hash=_hash_ip(client_ip),
    )
    db.add(new_session)
    db.commit()
    return Response(status_code=204)
