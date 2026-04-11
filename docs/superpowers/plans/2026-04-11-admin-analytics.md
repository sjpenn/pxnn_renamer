# Admin Analytics & Marketing Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a live admin console at `/admin` for `sjpenn@gmail.com` showing KPIs, purchase funnel, session stats, and a site-wide announcement banner — built on the existing FastAPI/Jinja/HTMX stack with zero new runtime dependencies.

**Architecture:** New `routes/admin.py` router gated by a `require_admin` dependency. A thin service layer in `services/admin_stats.py` owns all aggregation queries so the router stays testable. Session tracking uses a `UserSession` table fed by a 60-second client heartbeat. Purchase funnel is built on top of existing `ActivityLog` events plus three new event types (`pricing_viewed`, `plan_selected`, `checkout_abandoned`). `Announcement` model ships with forward-compatible `target_funnel_stage` / `target_plan_status` columns unused in Phase 1 but ready for Phase 2 nudge targeting.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / Jinja2 / HTMX / Tailwind / pytest / PostgreSQL (prod) + SQLite (local/tests).

**Spec:** `docs/superpowers/specs/2026-04-11-admin-analytics-design.md`

**Branch:** Execute on a new branch `feat/admin-analytics` cut from `feat/studio-dark-neon-reskin`.

---

## Pre-flight

- [ ] **P1: Create feature branch**

```bash
git checkout feat/studio-dark-neon-reskin
git pull --ff-only origin feat/studio-dark-neon-reskin
git checkout -b feat/admin-analytics
```

- [ ] **P2: Confirm tests baseline passes**

Run: `python -m pytest -q`
Expected: all existing tests green (no new failures from an uncommitted state).

---

## Task 1: Foundation — `is_admin` flag, `require_admin` dependency, bootstrap promotion

**Goal:** Add the admin flag, a config-driven promotion, and the FastAPI dependency that gates every `/admin/*` route.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/database/models.py`
- Modify: `backend/app/database/bootstrap.py`
- Modify: `backend/app/core/security.py`
- Create: `tests/test_admin_access.py`

- [ ] **Step 1.1: Write failing test for `require_admin`**

Create `tests/test_admin_access.py`:

```python
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import require_admin, create_access_token, set_auth_cookie
from backend.app.core.config import settings
from backend.app.database.models import User
from backend.app.database.session import get_db
from tests.conftest import TestingSessionLocal, override_get_db


def _make_user(db: Session, *, username: str, email: str, is_admin: bool = False) -> User:
    user = User(
        username=username,
        email=email,
        password_hash="x",
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_require_admin_rejects_non_admin(db):
    user = _make_user(db, username="normie", email="normie@example.com", is_admin=False)
    with pytest.raises(HTTPException) as exc:
        require_admin(current_user=user)
    assert exc.value.status_code == 403


def test_require_admin_allows_admin(db):
    admin = _make_user(db, username="boss", email="sjpenn@gmail.com", is_admin=True)
    result = require_admin(current_user=admin)
    assert result.id == admin.id
```

- [ ] **Step 1.2: Run — expect failure (`require_admin` does not exist yet, `is_admin` column missing)**

Run: `python -m pytest tests/test_admin_access.py -q`
Expected: FAIL — `ImportError: cannot import name 'require_admin'` OR `AttributeError: 'User' object has no attribute 'is_admin'`.

- [ ] **Step 1.3: Add `ADMIN_BOOTSTRAP_EMAIL` to settings**

Edit `backend/app/core/config.py`, inside the `Settings` class (add near the other simple fields, before `model_config`):

```python
    ADMIN_BOOTSTRAP_EMAIL: str = "sjpenn@gmail.com"
```

- [ ] **Step 1.4: Add `is_admin` column to `User` model**

Edit `backend/app/database/models.py`. In the `User` class, add this line right after `created_at`:

```python
    is_admin = Column(Boolean, default=False, nullable=False)
```

- [ ] **Step 1.5: Add `require_admin` dependency**

Edit `backend/app/core/security.py`. Append at the end of the file:

```python
def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the authenticated user to have is_admin=True."""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user
```

- [ ] **Step 1.6: Add bootstrap migration + promote admin email**

Edit `backend/app/database/bootstrap.py`. Inside `bootstrap_database()`, after the existing `# Users — new OAuth + subscription columns` block, add:

```python
    # Users — admin flag
    _ensure_column("users", "is_admin", "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
```

Then at the very end of `bootstrap_database()` add:

```python
    # Promote configured admin email (idempotent)
    from .session import SessionLocal
    from .models import User as _UserModel
    from ..core.config import settings as _settings

    email = (_settings.ADMIN_BOOTSTRAP_EMAIL or "").strip().lower()
    if email:
        db = SessionLocal()
        try:
            match = (
                db.query(_UserModel)
                .filter(_UserModel.email.ilike(email))
                .first()
            )
            if match and not match.is_admin:
                match.is_admin = True
                db.commit()
        finally:
            db.close()
```

Note: `SessionLocal` must exist in `session.py`. Check it — if the module exports `get_db` via a factory, reuse that factory name. If the module uses a different name (e.g. `TestingSessionLocal` is only in tests), fall back to importing `engine` and doing `Session(bind=engine)` from `sqlalchemy.orm`. Use whatever the file actually exports.

- [ ] **Step 1.7: Run — expect pass**

Run: `python -m pytest tests/test_admin_access.py -q`
Expected: 2 passed.

- [ ] **Step 1.8: Run full suite — expect pass**

Run: `python -m pytest -q`
Expected: all tests green (no regressions).

- [ ] **Step 1.9: Commit**

```bash
git add backend/app/core/config.py \
        backend/app/core/security.py \
        backend/app/database/models.py \
        backend/app/database/bootstrap.py \
        tests/test_admin_access.py
git commit -m "feat(admin): add is_admin flag, require_admin dependency, bootstrap promotion"
```

---

## Task 2: `Announcement` model + active-banner resolver

**Goal:** Add the announcements table (with forward-compat targeting columns) and a helper that returns the currently active banner.

**Files:**
- Modify: `backend/app/database/models.py`
- Modify: `backend/app/database/bootstrap.py`
- Create: `backend/app/services/__init__.py` (empty file, if missing)
- Create: `backend/app/services/announcements.py`
- Create: `tests/test_announcements.py`

- [ ] **Step 2.1: Write failing tests**

Create `tests/test_announcements.py`:

```python
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
```

- [ ] **Step 2.2: Run — expect failure**

Run: `python -m pytest tests/test_announcements.py -q`
Expected: FAIL — `Announcement` not defined.

- [ ] **Step 2.3: Add the `Announcement` model**

Edit `backend/app/database/models.py`. At the bottom of the file, add:

```python
class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    severity = Column(String, default="info", nullable=False)  # info | success | warn | danger
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    # Phase 2 targeting — present in schema, unused by Phase 1 UI
    target_funnel_stage = Column(String, nullable=True)
    target_plan_status = Column(String, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
```

- [ ] **Step 2.4: Bootstrap the table**

Edit `backend/app/database/bootstrap.py`. Inside `bootstrap_database()`, **before** the admin-promotion block added in Task 1, add:

```python
    # Announcements — Phase 1 admin feature
    _ensure_column("announcements", "target_funnel_stage", "ALTER TABLE announcements ADD COLUMN target_funnel_stage TEXT")
    _ensure_column("announcements", "target_plan_status", "ALTER TABLE announcements ADD COLUMN target_plan_status TEXT")
```

Note: `Base.metadata.create_all(bind=engine)` at the top of `bootstrap_database()` handles fresh table creation. The `_ensure_column` calls above are only needed for environments where an older version of this table already exists.

- [ ] **Step 2.5: Create the service module**

Create `backend/app/services/__init__.py` if it doesn't exist (empty file).

Create `backend/app/services/announcements.py`:

```python
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
```

- [ ] **Step 2.6: Run — expect pass**

Run: `python -m pytest tests/test_announcements.py -q`
Expected: 6 passed.

- [ ] **Step 2.7: Commit**

```bash
git add backend/app/database/models.py \
        backend/app/database/bootstrap.py \
        backend/app/services/__init__.py \
        backend/app/services/announcements.py \
        tests/test_announcements.py
git commit -m "feat(admin): add Announcement model and active-banner resolver"
```

---

## Task 3: `UserSession` model + heartbeat endpoint

**Goal:** Track live session duration via a 60-second client heartbeat POST. Rotate stale sessions automatically.

**Files:**
- Modify: `backend/app/database/models.py`
- Modify: `backend/app/database/bootstrap.py`
- Create: `backend/app/routes/session_heartbeat.py`
- Modify: `backend/app/main.py`
- Create: `tests/test_session_heartbeat.py`

- [ ] **Step 3.1: Write failing tests**

Create `tests/test_session_heartbeat.py`:

```python
from datetime import datetime, timedelta

from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import User, UserSession


def _login(client, db):
    user = User(username="ping_user", email="ping@example.com", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)
    return user


def test_heartbeat_requires_auth(client):
    r = client.post("/api/session/heartbeat")
    assert r.status_code == 401


def test_heartbeat_opens_new_session(client, db):
    user = _login(client, db)
    r = client.post("/api/session/heartbeat")
    assert r.status_code == 204
    sessions = db.query(UserSession).filter(UserSession.user_id == user.id).all()
    assert len(sessions) == 1
    assert sessions[0].ended_at is None


def test_second_heartbeat_extends_existing_session(client, db):
    user = _login(client, db)
    client.post("/api/session/heartbeat")
    client.post("/api/session/heartbeat")
    sessions = db.query(UserSession).filter(UserSession.user_id == user.id).all()
    assert len(sessions) == 1


def test_stale_session_rotates_on_next_heartbeat(client, db):
    user = _login(client, db)
    client.post("/api/session/heartbeat")
    # Force stale
    stale_session = db.query(UserSession).filter(UserSession.user_id == user.id).first()
    stale_session.last_seen_at = datetime.utcnow() - timedelta(minutes=30)
    db.commit()

    client.post("/api/session/heartbeat")
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id)
        .order_by(UserSession.id.asc())
        .all()
    )
    assert len(sessions) == 2
    assert sessions[0].ended_at is not None
    assert sessions[0].duration_seconds is not None
    assert sessions[1].ended_at is None
```

- [ ] **Step 3.2: Run — expect failure**

Run: `python -m pytest tests/test_session_heartbeat.py -q`
Expected: FAIL — 404 on `/api/session/heartbeat` and/or `UserSession` undefined.

- [ ] **Step 3.3: Add `UserSession` model**

Edit `backend/app/database/models.py`. At the bottom of the file, add:

```python
class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_hash = Column(String, nullable=True)
```

- [ ] **Step 3.4: Extend bootstrap (nothing to add — `create_all` handles the new table)**

No edit needed — `Base.metadata.create_all(bind=engine)` at the top of `bootstrap_database()` picks up the new table automatically. Leave a comment in bootstrap.py for clarity:

```python
    # UserSession table is handled by create_all above — no migration helper needed.
```

- [ ] **Step 3.5: Create the heartbeat route**

Create `backend/app/routes/session_heartbeat.py`:

```python
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
```

- [ ] **Step 3.6: Wire the router**

Edit `backend/app/main.py`. In the imports block near the other routers, add:

```python
from .routes.session_heartbeat import router as session_heartbeat_router
```

And with the other `app.include_router(...)` lines, add:

```python
app.include_router(session_heartbeat_router)
```

- [ ] **Step 3.7: Run — expect pass**

Run: `python -m pytest tests/test_session_heartbeat.py -q`
Expected: 4 passed.

- [ ] **Step 3.8: Run full suite**

Run: `python -m pytest -q`
Expected: all green.

- [ ] **Step 3.9: Commit**

```bash
git add backend/app/database/models.py \
        backend/app/database/bootstrap.py \
        backend/app/routes/session_heartbeat.py \
        backend/app/main.py \
        tests/test_session_heartbeat.py
git commit -m "feat(admin): add UserSession model and heartbeat endpoint"
```

---

## Task 4: Purchase funnel instrumentation

**Goal:** Emit the three missing funnel events (`pricing_viewed`, `plan_selected`, `checkout_abandoned`) with per-session dedup.

**Files:**
- Create: `backend/app/services/funnel.py`
- Create: `backend/app/routes/funnel.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routes/payments.py`
- Create: `tests/test_funnel_events.py`

- [ ] **Step 4.1: Write failing tests**

Create `tests/test_funnel_events.py`:

```python
from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import ActivityLog, User, UserSession


def _auth_client(client, db, username="funnel_user", email="f@x.com"):
    user = User(username=username, email=email, password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(user.id)))
    return user


def _events(db, user_id, event_type):
    return (
        db.query(ActivityLog)
        .filter(ActivityLog.user_id == user_id, ActivityLog.event_type == event_type)
        .all()
    )


def test_home_logs_pricing_viewed_for_authed_user(client, db):
    user = _auth_client(client, db)
    client.post("/api/session/heartbeat")  # open a UserSession so dedup has a session_id
    client.get("/")
    rows = _events(db, user.id, "pricing_viewed")
    assert len(rows) == 1


def test_pricing_viewed_dedups_within_same_session(client, db):
    user = _auth_client(client, db)
    client.post("/api/session/heartbeat")
    client.get("/")
    client.get("/")
    client.get("/")
    assert len(_events(db, user.id, "pricing_viewed")) == 1


def test_plan_selected_endpoint(client, db):
    user = _auth_client(client, db)
    client.post("/api/session/heartbeat")
    r = client.post("/api/funnel/plan-selected", data={"plan_key": "creator_pack"})
    assert r.status_code == 204
    rows = _events(db, user.id, "plan_selected")
    assert len(rows) == 1
    assert "creator_pack" in rows[0].summary


def test_checkout_abandoned_on_cancel_redirect(client, db):
    user = _auth_client(client, db)
    client.post("/api/session/heartbeat")
    client.get("/", params={"billing": "cancelled"})
    rows = _events(db, user.id, "checkout_abandoned")
    assert len(rows) == 1
```

- [ ] **Step 4.2: Run — expect failure**

Run: `python -m pytest tests/test_funnel_events.py -q`
Expected: FAIL — routes / helpers don't exist yet.

- [ ] **Step 4.3: Create the funnel service**

Create `backend/app/services/funnel.py`:

```python
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
        # Without a session anchor we can't dedup — allow the log.
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
```

- [ ] **Step 4.4: Create `/api/funnel/plan-selected` route**

Create `backend/app/routes/funnel.py`:

```python
from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session

from ..core.security import get_current_user
from ..database.models import User
from ..database.session import get_db
from ..services.funnel import log_funnel_event

router = APIRouter(tags=["funnel"])


@router.post("/api/funnel/plan-selected", status_code=204)
async def plan_selected(
    plan_key: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    log_funnel_event(
        db,
        current_user,
        event_type="plan_selected",
        summary=f"Plan selected: {plan_key}",
        extra={"plan_key": plan_key},
    )
    return Response(status_code=204)
```

- [ ] **Step 4.5: Wire the funnel router and instrument `/` for `pricing_viewed` + `checkout_abandoned`**

Edit `backend/app/main.py`.

At the imports section add:

```python
from .routes.funnel import router as funnel_router
from .services.funnel import log_funnel_event
```

At the router include section add:

```python
app.include_router(funnel_router)
```

Replace the body of the `home` route so it logs funnel events for authed users. The new body (keep the function signature and template response):

```python
@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if current_user:
        billing = request.query_params.get("billing")
        if billing == "cancelled":
            log_funnel_event(
                db,
                current_user,
                event_type="checkout_abandoned",
                summary="Checkout cancelled",
            )
            return RedirectResponse(url="/app?billing=cancelled", status_code=303)

        # Authed user landing on home = pricing_viewed (deduped per session)
        log_funnel_event(
            db,
            current_user,
            event_type="pricing_viewed",
            summary="Viewed pricing",
        )
        return RedirectResponse(url="/app", status_code=303)

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "current_user": None,
            "page": "home",
            "payment_options": get_payment_options(),
            "stripe_enabled": bool(settings.STRIPE_SECRET_KEY),
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )
```

You'll need these imports at the top of `main.py` (add if missing):

```python
from sqlalchemy.orm import Session
from .database.session import get_db
```

- [ ] **Step 4.6: Run — expect pass**

Run: `python -m pytest tests/test_funnel_events.py -q`
Expected: 4 passed.

- [ ] **Step 4.7: Run full suite — check for regressions in existing `test_routes_pages.py`**

Run: `python -m pytest -q`
Expected: all green. If `test_routes_pages.py` broke because authed GET `/` now redirects, that's a contract change — update those assertions (likely they already expect a redirect for authed users).

- [ ] **Step 4.8: Commit**

```bash
git add backend/app/services/funnel.py \
        backend/app/routes/funnel.py \
        backend/app/main.py \
        tests/test_funnel_events.py
git commit -m "feat(admin): instrument purchase funnel (pricing_viewed, plan_selected, checkout_abandoned)"
```

---

## Task 5: `admin_stats` service — user, revenue, plan, credit, session stats

**Goal:** Build the query layer the admin dashboard calls. All aggregations, no routing.

**Files:**
- Create: `backend/app/services/admin_stats.py`
- Create: `tests/test_admin_stats_core.py`

- [ ] **Step 5.1: Write failing tests**

Create `tests/test_admin_stats_core.py`:

```python
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
```

- [ ] **Step 5.2: Run — expect failure**

Run: `python -m pytest tests/test_admin_stats_core.py -q`
Expected: FAIL — `admin_stats` module missing.

- [ ] **Step 5.3: Create `admin_stats.py` (core queries)**

Create `backend/app/services/admin_stats.py`:

```python
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
    base = db.query(PaymentRecord).filter(PaymentRecord.status == "paid")

    def _sum_since(delta: timedelta | None) -> int:
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
```

- [ ] **Step 5.4: Run — expect pass**

Run: `python -m pytest tests/test_admin_stats_core.py -q`
Expected: 7 passed.

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/services/admin_stats.py \
        tests/test_admin_stats_core.py
git commit -m "feat(admin): add core admin_stats queries (users, revenue, plans, credits, sessions)"
```

---

## Task 6: `admin_stats` — funnel, stuck-at-checkout, per-user stage

**Goal:** Add the remaining admin_stats functions that read the funnel events from Task 4.

**Files:**
- Modify: `backend/app/services/admin_stats.py`
- Create: `tests/test_admin_stats_funnel.py`

- [ ] **Step 6.1: Write failing tests**

Create `tests/test_admin_stats_funnel.py`:

```python
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
    assert stages["payment_completed"]["dropoff_pct"] == 0.0  # final stage


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
```

- [ ] **Step 6.2: Run — expect failure**

Run: `python -m pytest tests/test_admin_stats_funnel.py -q`
Expected: FAIL — functions not defined.

- [ ] **Step 6.3: Add the funnel functions to `admin_stats.py`**

Append to `backend/app/services/admin_stats.py`:

```python
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
```

- [ ] **Step 6.4: Run — expect pass**

Run: `python -m pytest tests/test_admin_stats_funnel.py -q`
Expected: 3 passed.

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/services/admin_stats.py \
        tests/test_admin_stats_funnel.py
git commit -m "feat(admin): add funnel_stats, stuck_at_checkout, and per-user funnel stage helpers"
```

---

## Task 7: Admin router + dashboard page shell

**Goal:** Create `/admin` protected by `require_admin`, rendering a shell template that will host the HTMX partials.

**Files:**
- Create: `backend/app/routes/admin.py`
- Modify: `backend/app/main.py`
- Create: `frontend/templates/admin/base.html`
- Create: `frontend/templates/admin/dashboard.html`
- Create: `tests/test_admin_routes.py`

- [ ] **Step 7.1: Write failing tests**

Create `tests/test_admin_routes.py`:

```python
from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import User


def _login_as(client, db, *, is_admin: bool):
    u = User(
        username="x",
        email="sjpenn@gmail.com" if is_admin else "regular@x.com",
        password_hash="x",
        is_admin=is_admin,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def test_admin_dashboard_requires_admin(client, db):
    _login_as(client, db, is_admin=False)
    r = client.get("/admin")
    assert r.status_code == 403


def test_admin_dashboard_ok_for_admin(client, db):
    _login_as(client, db, is_admin=True)
    r = client.get("/admin")
    assert r.status_code == 200
    assert "Admin" in r.text
```

- [ ] **Step 7.2: Run — expect failure**

Run: `python -m pytest tests/test_admin_routes.py -q`
Expected: FAIL — route missing (404).

- [ ] **Step 7.3: Create the admin router**

Create `backend/app/routes/admin.py`:

```python
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..core.security import require_admin
from ..database.models import User
from ..database.session import get_db

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "current_user": admin,
            "page": "admin",
            "title": "Admin · PxNN",
        },
    )
```

- [ ] **Step 7.4: Wire the admin router**

Edit `backend/app/main.py`. Add import:

```python
from .routes.admin import router as admin_router
```

And the include:

```python
app.include_router(admin_router)
```

- [ ] **Step 7.5: Create `admin/base.html`**

Create `frontend/templates/admin/base.html`:

```html
{% extends "base.html" %}

{% block content %}
<div class="min-h-screen bg-neutral-950 text-neutral-100">
  <header class="border-b border-neutral-800 px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <span class="text-lg font-semibold tracking-tight">Admin · PxNN</span>
      <nav class="flex items-center gap-4 ml-6 text-sm text-neutral-400">
        <a href="/admin" class="hover:text-white">Dashboard</a>
        <a href="/admin/announcements" class="hover:text-white">Announcements</a>
      </nav>
    </div>
    <div class="text-sm text-neutral-400">
      {{ current_user.email or current_user.username }}
    </div>
  </header>

  <main class="p-6 space-y-6">
    {% block admin_content %}{% endblock %}
  </main>
</div>
{% endblock %}
```

Note: this assumes a `base.html` with a `content` block exists. If the real base template uses a different block name, match it — grep `frontend/templates/base.html` for `{% block` and align.

- [ ] **Step 7.6: Create `admin/dashboard.html` shell**

Create `frontend/templates/admin/dashboard.html`:

```html
{% extends "admin/base.html" %}

{% block admin_content %}
<h1 class="text-2xl font-semibold">Dashboard</h1>

<section id="admin-kpis"
         hx-get="/admin/partials/kpis"
         hx-trigger="load, every 30s"
         hx-swap="innerHTML"
         class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  <p class="text-neutral-500 col-span-full">Loading KPIs…</p>
</section>

<section id="admin-funnel"
         hx-get="/admin/partials/funnel?window=7"
         hx-trigger="load, every 60s"
         hx-swap="innerHTML"
         class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
  <p class="text-neutral-500">Loading funnel…</p>
</section>

<div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
  <section id="admin-online"
           hx-get="/admin/partials/online"
           hx-trigger="load, every 15s"
           hx-swap="innerHTML"
           class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
    <p class="text-neutral-500">Loading active users…</p>
  </section>

  <section id="admin-activity"
           hx-get="/admin/partials/activity"
           hx-trigger="load, every 15s"
           hx-swap="innerHTML"
           class="bg-neutral-900 border border-neutral-800 rounded-xl p-4 lg:col-span-2">
    <p class="text-neutral-500">Loading activity feed…</p>
  </section>
</div>

<section id="admin-stuck"
         hx-get="/admin/partials/stuck"
         hx-trigger="load, every 60s"
         hx-swap="innerHTML"
         class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
  <p class="text-neutral-500">Loading stuck-at-checkout list…</p>
</section>
{% endblock %}
```

- [ ] **Step 7.7: Run — expect pass**

Run: `python -m pytest tests/test_admin_routes.py -q`
Expected: 2 passed.

- [ ] **Step 7.8: Commit**

```bash
git add backend/app/routes/admin.py \
        backend/app/main.py \
        frontend/templates/admin/base.html \
        frontend/templates/admin/dashboard.html \
        tests/test_admin_routes.py
git commit -m "feat(admin): add /admin router, dashboard shell, and require_admin guard"
```

---

## Task 8: HTMX partial routes + templates

**Goal:** Wire the KPI cards, activity feed, online now, funnel, and stuck-at-checkout widgets.

**Files:**
- Modify: `backend/app/routes/admin.py`
- Create: `frontend/templates/admin/partials/kpi_cards.html`
- Create: `frontend/templates/admin/partials/activity_feed.html`
- Create: `frontend/templates/admin/partials/online_now.html`
- Create: `frontend/templates/admin/partials/funnel_widget.html`
- Create: `frontend/templates/admin/partials/stuck_at_checkout.html`
- Modify: `tests/test_admin_routes.py`

- [ ] **Step 8.1: Write failing tests (append to existing file)**

Append to `tests/test_admin_routes.py`:

```python
def test_partials_are_admin_only(client, db):
    _login_as(client, db, is_admin=False)
    for path in (
        "/admin/partials/kpis",
        "/admin/partials/activity",
        "/admin/partials/online",
        "/admin/partials/funnel",
        "/admin/partials/stuck",
    ):
        assert client.get(path).status_code == 403


def test_kpi_partial_renders(client, db):
    _login_as(client, db, is_admin=True)
    r = client.get("/admin/partials/kpis")
    assert r.status_code == 200
    assert "Users" in r.text
    assert "Revenue" in r.text


def test_funnel_partial_renders(client, db):
    _login_as(client, db, is_admin=True)
    r = client.get("/admin/partials/funnel?window=7")
    assert r.status_code == 200
    assert "registered" in r.text.lower()
```

- [ ] **Step 8.2: Run — expect failure**

Run: `python -m pytest tests/test_admin_routes.py -q`
Expected: the new tests fail (routes missing).

- [ ] **Step 8.3: Add partial routes to `admin.py`**

Append to `backend/app/routes/admin.py`:

```python
from ..services import admin_stats


@router.get("/partials/kpis", response_class=HTMLResponse)
async def partial_kpis(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/partials/kpi_cards.html",
        {
            "users": admin_stats.user_counts(db),
            "revenue": admin_stats.revenue_stats(db),
            "plans": admin_stats.plan_breakdown(db),
            "credits": admin_stats.credit_stats(db),
            "sessions": admin_stats.session_stats(db),
        },
    )


@router.get("/partials/activity", response_class=HTMLResponse)
async def partial_activity(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/partials/activity_feed.html",
        {"rows": admin_stats.recent_activity(db, limit=50)},
    )


@router.get("/partials/online", response_class=HTMLResponse)
async def partial_online(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/partials/online_now.html",
        {"sessions": admin_stats.session_stats(db)},
    )


@router.get("/partials/funnel", response_class=HTMLResponse)
async def partial_funnel(
    request: Request,
    window: int = 7,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    window_days = max(1, min(window, 365))
    return templates.TemplateResponse(
        request,
        "admin/partials/funnel_widget.html",
        {
            "window_days": window_days,
            "stages": admin_stats.funnel_stats(db, window_days=window_days),
        },
    )


@router.get("/partials/stuck", response_class=HTMLResponse)
async def partial_stuck(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/partials/stuck_at_checkout.html",
        {"rows": admin_stats.stuck_at_checkout(db, limit=20)},
    )
```

- [ ] **Step 8.4: Create `kpi_cards.html`**

Create `frontend/templates/admin/partials/kpi_cards.html`:

```html
<div class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
  <div class="text-xs uppercase tracking-wider text-neutral-400">Users</div>
  <div class="text-3xl font-semibold mt-1">{{ users.total }}</div>
  <div class="text-xs text-neutral-400 mt-2">
    +{{ users.new_today }} today · +{{ users.new_week }} week · +{{ users.new_month }} month
  </div>
  <div class="text-xs text-neutral-500 mt-1">
    Active: {{ sessions.active_now }} now · {{ users.active_today }} today
  </div>
</div>

<div class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
  <div class="text-xs uppercase tracking-wider text-neutral-400">Revenue</div>
  <div class="text-3xl font-semibold mt-1">${{ '%.2f' % (revenue.total_cents / 100) }}</div>
  <div class="text-xs text-neutral-400 mt-2">
    ${{ '%.2f' % (revenue.today_cents / 100) }} today ·
    ${{ '%.2f' % (revenue.week_cents / 100) }} week ·
    ${{ '%.2f' % (revenue.month_cents / 100) }} month
  </div>
</div>

<div class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
  <div class="text-xs uppercase tracking-wider text-neutral-400">Plans</div>
  <div class="text-3xl font-semibold mt-1">{{ plans.paid }}</div>
  <div class="text-xs text-neutral-400 mt-2">
    Paid · {{ plans.trial }} trial · {{ plans.free }} free
  </div>
</div>

<div class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
  <div class="text-xs uppercase tracking-wider text-neutral-400">Credits</div>
  <div class="text-3xl font-semibold mt-1">{{ credits.outstanding }}</div>
  <div class="text-xs text-neutral-400 mt-2">
    Outstanding · {{ credits.consumed_today }} today · {{ credits.consumed_week }} week
  </div>
</div>
```

- [ ] **Step 8.5: Create `activity_feed.html`**

Create `frontend/templates/admin/partials/activity_feed.html`:

```html
<h2 class="text-sm uppercase tracking-wider text-neutral-400 mb-3">Activity Feed</h2>
<ul class="divide-y divide-neutral-800 text-sm">
  {% for row in rows %}
  <li class="py-2 flex items-center gap-3">
    <span class="text-neutral-500 w-28 shrink-0">{{ row.created_at.strftime('%H:%M') if row.created_at else '' }}</span>
    <span class="text-neutral-200 w-40 shrink-0 truncate">{{ row.username }}</span>
    <span class="text-neutral-400 w-40 shrink-0 truncate">{{ row.event_type }}</span>
    <span class="text-neutral-300 truncate">{{ row.summary }}</span>
  </li>
  {% else %}
  <li class="py-2 text-neutral-500">No activity yet.</li>
  {% endfor %}
</ul>
```

- [ ] **Step 8.6: Create `online_now.html`**

Create `frontend/templates/admin/partials/online_now.html`:

```html
<h2 class="text-sm uppercase tracking-wider text-neutral-400 mb-3">Active Now</h2>
<div class="text-4xl font-semibold">{{ sessions.active_now }}</div>
<div class="text-xs text-neutral-400 mt-2">
  Sessions today: {{ sessions.sessions_today }}<br>
  Avg duration today: {{ (sessions.avg_duration_today_s // 60) }}m {{ sessions.avg_duration_today_s % 60 }}s
</div>
```

- [ ] **Step 8.7: Create `funnel_widget.html`**

Create `frontend/templates/admin/partials/funnel_widget.html`:

```html
<div class="flex items-center justify-between mb-3">
  <h2 class="text-sm uppercase tracking-wider text-neutral-400">Purchase Funnel · {{ window_days }}d</h2>
  <div class="flex gap-2 text-xs">
    {% for w in [1, 7, 30] %}
    <a class="px-2 py-1 rounded border border-neutral-700 hover:border-neutral-500"
       hx-get="/admin/partials/funnel?window={{ w }}"
       hx-target="#admin-funnel"
       hx-swap="innerHTML">{{ w }}d</a>
    {% endfor %}
  </div>
</div>

<div class="space-y-2">
  {% set max_users = stages[0].users if stages and stages[0].users > 0 else 1 %}
  {% for stage in stages %}
  <div class="flex items-center gap-3 text-sm">
    <span class="w-40 text-neutral-300 capitalize">{{ stage.stage.replace('_', ' ') }}</span>
    <div class="flex-1 bg-neutral-800 rounded h-4 relative overflow-hidden">
      <div class="bg-emerald-500 h-4"
           style="width: {{ (stage.users / max_users * 100) | round(1) }}%"></div>
    </div>
    <span class="w-12 text-right text-neutral-200">{{ stage.users }}</span>
    <span class="w-16 text-right text-neutral-500">{{ stage.pct_of_prev }}%</span>
    <span class="w-16 text-right text-red-400">-{{ stage.dropoff_pct }}%</span>
  </div>
  {% endfor %}
</div>
```

- [ ] **Step 8.8: Create `stuck_at_checkout.html`**

Create `frontend/templates/admin/partials/stuck_at_checkout.html`:

```html
<h2 class="text-sm uppercase tracking-wider text-neutral-400 mb-3">Stuck at Checkout</h2>
<ul class="divide-y divide-neutral-800 text-sm">
  {% for row in rows %}
  <li class="py-2 flex items-center gap-3">
    <span class="text-neutral-200 w-40 truncate">{{ row.username }}</span>
    <span class="text-neutral-400 w-56 truncate">{{ row.email }}</span>
    <span class="text-neutral-500 w-40">{{ row.last_stage }}</span>
    <span class="text-neutral-500 w-40">{{ row.last_stage_at.strftime('%Y-%m-%d %H:%M') if row.last_stage_at else '' }}</span>
    <button class="text-xs text-emerald-400 hover:text-emerald-300"
            onclick="navigator.clipboard.writeText('{{ row.email }}')">copy email</button>
  </li>
  {% else %}
  <li class="py-2 text-neutral-500">Nobody stuck right now.</li>
  {% endfor %}
</ul>
```

- [ ] **Step 8.9: Run — expect pass**

Run: `python -m pytest tests/test_admin_routes.py -q`
Expected: all pass (previous 2 + 3 new = 5 passed).

- [ ] **Step 8.10: Commit**

```bash
git add backend/app/routes/admin.py \
        frontend/templates/admin/partials/ \
        tests/test_admin_routes.py
git commit -m "feat(admin): add HTMX partial routes and templates for KPIs/activity/funnel/stuck"
```

---

## Task 9: Announcement composer + user-side banner

**Goal:** Let the admin create/publish/delete announcements, and render the active banner on `/app`.

**Files:**
- Modify: `backend/app/routes/admin.py`
- Create: `frontend/templates/admin/announcements.html`
- Create: `frontend/templates/partials/announcement_banner.html`
- Modify: `frontend/templates/app.html`
- Modify: `backend/app/main.py`
- Create: `tests/test_admin_announcements.py`

- [ ] **Step 9.1: Write failing tests**

Create `tests/test_admin_announcements.py`:

```python
from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import Announcement, User


def _login(client, db, *, is_admin: bool):
    u = User(
        username="a", email="admin@x.com", password_hash="x", is_admin=is_admin
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def test_create_announcement_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.post("/admin/announcements", data={"title": "T", "body": "B", "severity": "info"})
    assert r.status_code == 403


def test_admin_can_create_publish_delete(client, db):
    _login(client, db, is_admin=True)
    r = client.post(
        "/admin/announcements",
        data={"title": "Launch", "body": "We're live", "severity": "success"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)

    created = db.query(Announcement).first()
    assert created is not None
    assert created.is_published is False  # draft by default

    # Publish
    r = client.post(f"/admin/announcements/{created.id}/publish", follow_redirects=False)
    assert r.status_code in (200, 303)
    db.refresh(created)
    assert created.is_published is True

    # Delete
    r = client.post(f"/admin/announcements/{created.id}/delete", follow_redirects=False)
    assert r.status_code in (200, 303)
    assert db.query(Announcement).count() == 0
```

- [ ] **Step 9.2: Run — expect failure**

Run: `python -m pytest tests/test_admin_announcements.py -q`
Expected: FAIL — endpoints missing.

- [ ] **Step 9.3: Add announcement endpoints to `admin.py`**

Append to `backend/app/routes/admin.py`:

```python
from fastapi import Form
from fastapi.responses import RedirectResponse

from ..database.models import Announcement


@router.get("/announcements", response_class=HTMLResponse)
async def admin_announcements_page(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Announcement)
        .order_by(Announcement.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/announcements.html",
        {
            "current_user": admin,
            "announcements": rows,
            "title": "Announcements · PxNN",
        },
    )


@router.post("/announcements")
async def admin_announcements_create(
    title: str = Form(...),
    body: str = Form(...),
    severity: str = Form("info"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.add(
        Announcement(
            title=title,
            body=body,
            severity=severity,
            is_published=False,
            created_by_id=admin.id,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/announcements", status_code=303)


@router.post("/announcements/{announcement_id}/publish")
async def admin_announcements_publish(
    announcement_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if row:
        row.is_published = not row.is_published
        db.commit()
    return RedirectResponse(url="/admin/announcements", status_code=303)


@router.post("/announcements/{announcement_id}/delete")
async def admin_announcements_delete(
    announcement_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if row:
        db.delete(row)
        db.commit()
    return RedirectResponse(url="/admin/announcements", status_code=303)
```

- [ ] **Step 9.4: Create `admin/announcements.html`**

Create `frontend/templates/admin/announcements.html`:

```html
{% extends "admin/base.html" %}

{% block admin_content %}
<h1 class="text-2xl font-semibold">Announcements</h1>

<section class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
  <h2 class="text-sm uppercase tracking-wider text-neutral-400 mb-3">Publish new</h2>
  <form method="post" action="/admin/announcements" class="space-y-3">
    <input name="title" placeholder="Title" required
           class="w-full bg-neutral-950 border border-neutral-800 rounded px-3 py-2" />
    <textarea name="body" placeholder="Body" rows="3" required
              class="w-full bg-neutral-950 border border-neutral-800 rounded px-3 py-2"></textarea>
    <select name="severity"
            class="bg-neutral-950 border border-neutral-800 rounded px-3 py-2">
      <option value="info">Info</option>
      <option value="success">Success</option>
      <option value="warn">Warning</option>
      <option value="danger">Danger</option>
    </select>
    <button type="submit"
            class="px-4 py-2 bg-emerald-500 text-neutral-950 rounded font-medium">
      Save draft
    </button>
  </form>
</section>

<section class="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
  <h2 class="text-sm uppercase tracking-wider text-neutral-400 mb-3">All announcements</h2>
  <ul class="divide-y divide-neutral-800 text-sm">
    {% for a in announcements %}
    <li class="py-3 flex items-center gap-3">
      <span class="w-64 truncate">{{ a.title }}</span>
      <span class="w-24 text-xs text-neutral-500">{{ a.severity }}</span>
      <span class="w-24 text-xs {% if a.is_published %}text-emerald-400{% else %}text-neutral-500{% endif %}">
        {{ 'published' if a.is_published else 'draft' }}
      </span>
      <form method="post" action="/admin/announcements/{{ a.id }}/publish">
        <button class="text-xs text-emerald-400 hover:text-emerald-300">
          {{ 'unpublish' if a.is_published else 'publish' }}
        </button>
      </form>
      <form method="post" action="/admin/announcements/{{ a.id }}/delete">
        <button class="text-xs text-red-400 hover:text-red-300">delete</button>
      </form>
    </li>
    {% else %}
    <li class="py-3 text-neutral-500">No announcements yet.</li>
    {% endfor %}
  </ul>
</section>
{% endblock %}
```

- [ ] **Step 9.5: Create user-side banner partial**

Create `frontend/templates/partials/announcement_banner.html`:

```html
{% if announcement %}
<div id="announcement-banner-{{ announcement.id }}"
     data-announcement-id="{{ announcement.id }}"
     class="announcement-banner announcement-{{ announcement.severity }}
            px-4 py-3 text-sm flex items-center justify-between
            {% if announcement.severity == 'success' %}bg-emerald-950 text-emerald-200 border-b border-emerald-800
            {% elif announcement.severity == 'warn' %}bg-amber-950 text-amber-200 border-b border-amber-800
            {% elif announcement.severity == 'danger' %}bg-red-950 text-red-200 border-b border-red-800
            {% else %}bg-sky-950 text-sky-200 border-b border-sky-800{% endif %}">
  <div>
    <strong class="mr-2">{{ announcement.title }}</strong>
    <span>{{ announcement.body }}</span>
  </div>
  <button type="button"
          onclick="localStorage.setItem('dismissed_announcement_id','{{ announcement.id }}'); this.closest('.announcement-banner').remove();"
          class="text-xs opacity-70 hover:opacity-100">dismiss</button>
</div>
<script>
(function() {
  var id = '{{ announcement.id }}';
  if (localStorage.getItem('dismissed_announcement_id') === id) {
    var el = document.getElementById('announcement-banner-' + id);
    if (el) el.remove();
  }
})();
</script>
{% endif %}
```

- [ ] **Step 9.6: Include banner on `/app`**

Edit `frontend/templates/app.html`. Find the first child of the main content area and insert immediately above it:

```html
{% include "partials/announcement_banner.html" %}
```

- [ ] **Step 9.7: Pass `announcement` into `/app` context**

Edit `backend/app/main.py`. In the `workspace` handler, add:

```python
from .services.announcements import get_active_announcement
```

(at the top with other service imports), then extend the `workspace` route's `TemplateResponse` context dict with:

```python
            "announcement": get_active_announcement(db, current_user),
```

You'll also need `db: Session = Depends(get_db)` as a parameter on `workspace` — add it if missing.

- [ ] **Step 9.8: Run — expect pass**

Run: `python -m pytest tests/test_admin_announcements.py -q`
Expected: 2 passed.

- [ ] **Step 9.9: Commit**

```bash
git add backend/app/routes/admin.py \
        backend/app/main.py \
        frontend/templates/admin/announcements.html \
        frontend/templates/partials/announcement_banner.html \
        frontend/templates/app.html \
        tests/test_admin_announcements.py
git commit -m "feat(admin): announcement composer + site-wide banner render"
```

---

## Task 10: Nav link + heartbeat client JS + final wiring

**Goal:** Expose `/admin` to admins from the main app nav, and actually start sending heartbeats from the browser.

**Files:**
- Modify: `frontend/templates/app.html`
- Create: `tests/test_app_nav.py`

- [ ] **Step 10.1: Write failing test**

Create `tests/test_app_nav.py`:

```python
from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import User


def _login(client, db, is_admin: bool):
    u = User(username="u", email="u@x.com", password_hash="x", is_admin=is_admin)
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def test_app_shows_admin_link_for_admin(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/app")
    assert r.status_code == 200
    assert "/admin" in r.text


def test_app_hides_admin_link_for_non_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.get("/app")
    assert r.status_code == 200
    assert 'href="/admin"' not in r.text
```

- [ ] **Step 10.2: Run — expect failure**

Run: `python -m pytest tests/test_app_nav.py -q`
Expected: FAIL — no admin link.

- [ ] **Step 10.3: Add conditional admin link to `app.html`**

Edit `frontend/templates/app.html`. Locate the primary user nav / menu. Inside it, add:

```html
{% if current_user and current_user.is_admin %}
  <a href="/admin" class="admin-nav-link">Admin</a>
{% endif %}
```

Style classes should match the existing nav link styles in that template — use whatever class the sibling links use rather than inventing a new class.

- [ ] **Step 10.4: Add inline heartbeat JS to `app.html`**

Still in `frontend/templates/app.html`, before `</body>` (or inside an existing `{% block scripts %}` if the base template has one) add:

```html
<script>
(function() {
  var HEARTBEAT_URL = '/api/session/heartbeat';
  var INTERVAL_MS = 60 * 1000;
  var timer = null;

  function ping() {
    try {
      fetch(HEARTBEAT_URL, { method: 'POST', credentials: 'same-origin', keepalive: true });
    } catch (e) { /* best effort */ }
  }

  function start() {
    if (timer) return;
    ping();
    timer = setInterval(ping, INTERVAL_MS);
  }
  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
  }

  document.addEventListener('visibilitychange', function() {
    if (document.hidden) { stop(); } else { start(); }
  });

  if (!document.hidden) start();
  window.addEventListener('beforeunload', ping);
})();
</script>
```

- [ ] **Step 10.5: Run — expect pass**

Run: `python -m pytest tests/test_app_nav.py -q`
Expected: 2 passed.

- [ ] **Step 10.6: Full suite**

Run: `python -m pytest -q`
Expected: all green.

- [ ] **Step 10.7: Commit**

```bash
git add frontend/templates/app.html tests/test_app_nav.py
git commit -m "feat(admin): expose /admin link to admins and wire heartbeat JS"
```

---

## Task 11: End-to-end smoke + manual verification

**Goal:** Final sanity pass before merge.

- [ ] **Step 11.1: Boot the app locally**

Run: `docker-compose up --build` (or `uvicorn backend.app.main:app --reload` if you prefer host-level).

- [ ] **Step 11.2: Verify admin promotion**

Sign in / register as `sjpenn@gmail.com`. Restart the app once (so `bootstrap_database` runs post-registration). Confirm `is_admin` flipped:

```bash
sqlite3 pxnn_it.db "SELECT email, is_admin FROM users WHERE email='sjpenn@gmail.com';"
```
Expected: `sjpenn@gmail.com|1`.

- [ ] **Step 11.3: Visit `/admin`**

Open `http://localhost:8000/admin` as the admin user. Verify:
- KPI cards render with real numbers
- Funnel widget shows stages (at minimum `registered`)
- "Active now" shows 1 (you)
- Activity feed shows recent events
- Stuck-at-checkout shows "Nobody stuck right now" or real rows

- [ ] **Step 11.4: Verify non-admin lockout**

In a separate browser / incognito, register a second account. Hit `/admin` — should 403. Hit `/admin/partials/kpis` — should 403.

- [ ] **Step 11.5: Publish an announcement**

From `/admin/announcements`: create a draft, hit "publish", then load `/app` as a non-admin user. The banner should render. Click dismiss — reload — it stays dismissed (localStorage).

- [ ] **Step 11.6: Exercise the funnel**

Log in as the non-admin test user, land on `/`, click into pricing (should redirect `/app`), open the plans drawer, click a plan (should hit `/api/funnel/plan-selected`), cancel checkout (visit `/?billing=cancelled`). Reload `/admin` — funnel widget should show all five stages populated.

Note: wiring the `/api/funnel/plan-selected` POST from the actual plans drawer is **out of scope for Phase 1's plan** unless the drawer already uses HTMX — if it does, add `hx-post="/api/funnel/plan-selected" hx-vals='{"plan_key":"<plan>"}' hx-swap="none"` to the plan-card click. Otherwise log it as a Phase 2 follow-up.

- [ ] **Step 11.7: Final commit (if any doc/README touches)**

If you touched `README.md` or `DESIGN.md` during smoke testing, commit those now:

```bash
git add README.md DESIGN.md 2>/dev/null || true
git diff --cached --quiet || git commit -m "docs(admin): note admin console in README"
```

- [ ] **Step 11.8: Open PR**

```bash
git push -u origin feat/admin-analytics
gh pr create --base feat/studio-dark-neon-reskin \
  --title "feat(admin): analytics & marketing console (Phase 1)" \
  --body "$(cat <<'EOF'
## Summary
- New /admin console gated by is_admin + require_admin
- Live KPIs: users, revenue, plans, credits, sessions
- Purchase funnel with 3 new event types + dedup
- UserSession heartbeat for accurate presence + avg duration
- Announcement composer + site-wide banner
- Forward-compatible targeting columns on Announcement for Phase 2 nudge engine

Spec: docs/superpowers/specs/2026-04-11-admin-analytics-design.md
Plan: docs/superpowers/plans/2026-04-11-admin-analytics.md

## Test plan
- [ ] pytest -q
- [ ] /admin renders for sjpenn@gmail.com
- [ ] /admin returns 403 for any other user
- [ ] Announcement publish shows banner on /app
- [ ] Funnel populates as new user signs up → views pricing → selects plan → completes/cancels checkout
EOF
)"
```

---

## Notes & Gotchas

- **Import of `SessionLocal` in `bootstrap.py` (Task 1.6):** if `backend/app/database/session.py` doesn't export `SessionLocal`, inspect the file and either add it (`SessionLocal = sessionmaker(bind=engine)`) or use `Session(bind=engine)` directly from `sqlalchemy.orm`. Don't invent an import.

- **Jinja base template block names (Task 7.5):** the placeholder `{% block content %}` assumes that's what the real `base.html` uses. Grep `frontend/templates/base.html` for `{% block ` before implementing — match the real block name.

- **Existing `test_routes_pages.py` (Task 4.7):** authed `GET /` behavior may already be tested there. If Task 4 changes the response type (adds funnel event logging + potentially a redirect), update those tests rather than weakening the new funnel tests.

- **Plan-card client wiring (Task 11.6):** the `POST /api/funnel/plan-selected` endpoint exists but nothing in the current UI calls it. A brief HTMX attribute on the plan cards is a minimal add — if the drawer's structure makes this messy, punt it to a Phase 2 micro-follow-up and note it in the PR description.

- **Credit consumption event name:** confirmed as `batch_downloaded` (seen at `backend/app/routes/wizard.py:841`). If a future task renames it, `admin_stats.credit_stats` is the single place to update.

- **Postgres vs SQLite in bootstrap:** the existing `_ensure_column` helper already handles both. Follow its pattern; don't write raw `ALTER TABLE` outside it.
