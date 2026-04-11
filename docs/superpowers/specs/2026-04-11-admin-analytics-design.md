# Admin Analytics & Marketing Console — Design Spec

**Date:** 2026-04-11
**Branch target:** `feat/admin-analytics` (to be cut from `feat/studio-dark-neon-reskin`)
**Author:** brainstorming session (sjpenn + Claude)
**Status:** Phase 1 approved, ready for implementation planning

---

## 1. Goal

Ship a PxNN Admin console at `/admin` that gives `sjpenn@gmail.com` (and future admins) a single live view of:

- who's using the product right now and how long they stay
- where users drop out of the purchase funnel
- paid vs trial vs free breakdown and credit consumption
- a lever to publish in-app announcements to all users

The system must be schema-ready to add targeted "nudges" (stage-aware banners, stuck-at-checkout outreach) in Phase 2 without migrations.

## 2. Scope

### Phase 1 (this spec)
1. Admin access control (`is_admin` flag + `require_admin` dependency)
2. Analytics dashboard at `/admin` with HTMX-polled live KPI cards
3. Session duration tracking via `UserSession` + heartbeat endpoint
4. Purchase funnel instrumentation (3 new events) and funnel widget
5. "Stuck at checkout" admin widget for manual outreach
6. Announcement model + admin composer + site-wide banner render
7. Forward-compatible targeting columns on `Announcement` (unused in Phase 1 UI)

### Explicitly Phase 2 (not built now)
- Broadcast email blasts (SMTP/SES/Mailgun wiring)
- UTM / campaign source tracking
- Automated nudge engine that acts on `target_funnel_stage`
- Charting library (Chart.js) on the dashboard

## 3. Architecture Overview

**Stack reuse:** FastAPI + SQLAlchemy + Jinja2 + Tailwind + HTMX. No new frameworks or client-side libraries.

**New module layout:**

```
backend/app/
  routes/
    admin.py                  # all /admin/* endpoints, gated by require_admin
    session_heartbeat.py      # POST /api/session/heartbeat
  services/
    admin_stats.py            # pure query functions: user_counts, revenue_stats, plan_breakdown, credit_stats, funnel_stats, session_stats, stuck_at_checkout, get_user_funnel_stage
    announcements.py          # get_active_announcement(db, user) helper
  database/
    models.py                 # + UserSession, Announcement, User.is_admin
    bootstrap.py              # + announcements/user_sessions table + is_admin column + promote ADMIN_BOOTSTRAP_EMAIL

frontend/templates/
  admin/
    base.html                 # extends site base; admin sidebar nav
    dashboard.html            # main analytics page
    announcements.html        # list + create/edit form
    partials/
      kpi_cards.html
      activity_feed.html
      online_now.html
      funnel_widget.html
      stuck_at_checkout.html
      banner_form.html
  partials/
    announcement_banner.html  # rendered on /app (and optionally /) for all users
```

**Why a separate router and service module:** keeps authorization and query logic testable and contained. The router stays thin and delegates all SQL to `admin_stats`. If analytics grows, it has its own home.

## 4. Access Control

**Model change:**
```python
# models.py — User
is_admin = Column(Boolean, default=False, nullable=False)
```

**Config addition:**
```python
# core/config.py
ADMIN_BOOTSTRAP_EMAIL: str = "sjpenn@gmail.com"
```

**Bootstrap promotion (idempotent, runs every startup):**
In `bootstrap_database()`, after schema creation, find any `User` whose `email == settings.ADMIN_BOOTSTRAP_EMAIL` and set `is_admin = True` if not already. Safe if the admin user doesn't exist yet — the next startup after they register/sign in with Google will promote them.

**Dependency:**
```python
# core/security.py
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only.")
    return current_user
```

Every `/admin/*` endpoint depends on `require_admin`. Defense in depth: even if a template leaks the link, the server refuses non-admins.

## 5. Data Model Changes

### 5.1 User (existing table)
Add `is_admin` boolean column, default `False`, not null.

### 5.2 Announcement (new table)
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
    target_funnel_stage = Column(String, nullable=True)   # e.g. "plan_selected"
    target_plan_status = Column(String, nullable=True)    # e.g. "free", "trial"

    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

**Active resolver:** `get_active_announcement(db, user)` returns the newest announcement where `is_published` is true and the current time falls within `[starts_at, ends_at]` (nulls = open-ended). In Phase 1 it ignores `target_*` columns; Phase 2 adds filtering.

### 5.3 UserSession (new table)
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
    ip_hash = Column(String, nullable=True)  # sha256 of ip + settings.JWT_SECRET, never raw
```

### 5.4 Migration strategy
`bootstrap_database()` already runs on startup. Extend it with:
- `CREATE TABLE IF NOT EXISTS announcements ...`
- `CREATE TABLE IF NOT EXISTS user_sessions ...`
- `ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE NOT NULL` — guarded for both Postgres (`IF NOT EXISTS`) and SQLite (pragma check then conditional alter, since SQLite pre-3.35 lacks `IF NOT EXISTS` on `ADD COLUMN`).

The Dockerized Postgres and the local `pxnn_it.db` SQLite must both boot cleanly.

## 6. Session Tracking & Heartbeat

### 6.1 Endpoint
`POST /api/session/heartbeat` — requires auth, returns `204 No Content`.

### 6.2 Client
A ~15-line inline `<script>` block in `app.html`:
- On page load, immediately POST once.
- `setInterval(fetch, 60_000)` afterwards.
- `visibilitychange` listener: pause while hidden (no phantom sessions from open-but-unfocused tabs).
- `beforeunload` best-effort fire-and-forget.

### 6.3 Server logic
Given the current user, find the session where `user_id = ? AND ended_at IS NULL AND last_seen_at >= now() - 15 minutes`:
- **Found:** update `last_seen_at = now()`.
- **Not found:** close any stale open session for this user (set `ended_at = last_seen_at`, compute `duration_seconds`) then insert a new session with `user_agent` (from header) and `ip_hash` (from `request.client.host` sha256'd with `JWT_SECRET` as salt).

### 6.4 Opportunistic cleanup
`admin_stats.session_stats()` sweeps any session with `last_seen_at < now - 15 min AND ended_at IS NULL`, closes them in-line. No cron, no background worker. Worst case: a stale open session lingers until an admin next loads the dashboard. Acceptable.

## 7. Purchase Funnel

### 7.1 Stages (6)

| # | Stage | Event source | Instrumentation change |
|---|---|---|---|
| 1 | `registered` | derived from `User.created_at` | none |
| 2 | `pricing_viewed` | new `ActivityLog` event | **new**: log on `GET /` and `GET /app` when pricing panel renders, deduped per `UserSession.id` |
| 3 | `plan_selected` | new `ActivityLog` event | **new**: `POST /api/funnel/plan-selected` called before the checkout create call |
| 4 | `checkout_started` | existing `payment_started` | none |
| 5 | `checkout_abandoned` | new `ActivityLog` event | **new**: log when `/?billing=cancelled` is hit |
| 6 | `payment_completed` | existing `payment_completed` | none |

### 7.2 Per-session dedup
To avoid spamming `pricing_viewed` and `plan_selected`, both events embed the current `UserSession.id` in `details_json` and the logger skips inserts if the stage already exists for that session.

### 7.3 Query — `admin_stats.funnel_stats(db, window='7d')`
Returns an ordered list of stage dicts:
```python
[
  {"stage": "registered",       "users": N, "pct_of_prev": 100.0, "dropoff_pct": 0.0},
  {"stage": "pricing_viewed",   "users": N, "pct_of_prev": x,     "dropoff_pct": y},
  {"stage": "plan_selected",    "users": N, "pct_of_prev": x,     "dropoff_pct": y},
  {"stage": "checkout_started", "users": N, "pct_of_prev": x,     "dropoff_pct": y},
  {"stage": "payment_completed","users": N, "pct_of_prev": x,     "dropoff_pct": y},
]
```
Window options: `24h`, `7d`, `30d`, `all`. Dashboard defaults to `7d`.

### 7.4 Stuck-at-checkout query
`admin_stats.stuck_at_checkout(db, limit=20)` returns users whose furthest funnel stage is `plan_selected` or `checkout_started` with no `payment_completed`, ordered by most recent attempt. Each row: `{user_id, username, email, last_stage, last_stage_at, last_plan_key}`. Drives the "Stuck at Checkout" widget that gives the admin a manual outreach list.

### 7.5 Nudge-ready helper
`admin_stats.get_user_funnel_stage(db, user_id) -> str` returns the furthest stage any single user has reached. Not consumed by Phase 1 UI, but used by Phase 2 to filter announcements by `target_funnel_stage`.

## 8. Admin Endpoints

All routes live in `backend/app/routes/admin.py` and depend on `require_admin`.

### 8.1 Page routes (full HTML)
| Route | Template | Purpose |
|---|---|---|
| `GET /admin` | `admin/dashboard.html` | Main analytics page |
| `GET /admin/announcements` | `admin/announcements.html` | List + composer for banners |

### 8.2 HTMX partials (HTML fragments)
| Route | Poll cadence | Renders |
|---|---|---|
| `GET /admin/partials/kpis` | 30s | 4 KPI cards (users / revenue / plans / credits) |
| `GET /admin/partials/activity` | 15s | Last 50 `ActivityLog` rows |
| `GET /admin/partials/online` | 15s | "Active now" count + short user list |
| `GET /admin/partials/funnel?window=7d` | 60s | Funnel widget for the selected window |
| `GET /admin/partials/stuck` | 60s | Stuck-at-checkout list |

### 8.3 Actions
| Route | Purpose |
|---|---|
| `POST /admin/announcements` | Create announcement from form |
| `POST /admin/announcements/{id}/publish` | Toggle `is_published` |
| `POST /admin/announcements/{id}/delete` | Hard delete |

### 8.4 Non-admin endpoints added
| Route | Purpose |
|---|---|
| `POST /api/session/heartbeat` | Extend/open `UserSession` |
| `POST /api/funnel/plan-selected` | Log `plan_selected` event (called by client before checkout) |

Existing `/?billing=cancelled` handler gets extended to log `checkout_abandoned` if the user is authenticated.

## 9. Query Layer — `admin_stats.py`

All functions take a `Session` and return plain dataclasses or dicts. No query code in the router.

```python
user_counts(db)         -> UserCounts
revenue_stats(db)       -> RevenueStats
plan_breakdown(db)      -> list[PlanBucket]
credit_stats(db)        -> CreditStats
session_stats(db)       -> SessionStats  # also opportunistically closes stale sessions
funnel_stats(db, window) -> list[FunnelStage]
stuck_at_checkout(db, limit=20) -> list[StuckRow]
recent_activity(db, limit=50)   -> list[ActivityRow]
get_user_funnel_stage(db, user_id) -> str
```

### 9.1 KPI definitions

**Users** — total, new (24h / 7d / 30d), active now (open `UserSession` with fresh heartbeat, unioned with users having any `ActivityLog` in last 5 min), active today, active week.

**Revenue** — `PaymentRecord` where `status='paid'`: total, today, week, month, breakdown by `plan_key`.

**Plans** — count of users grouped by `(active_plan, plan_status)`. Free / trial / paid are derived: `plan_status='inactive'` → free; trial detection uses `subscription_status='trialing'` if present; everything else with `plan_status='active'` is paid.

**Credits** — outstanding = `SUM(User.credit_balance)`. Consumed today/week/month = sum of negative `credit_balance` deltas derivable from `ActivityLog` events of type `credit_spent` (or equivalent — final event name confirmed during implementation by grep'ing the existing codebase for credit-mutation points).

**Sessions** — active now, sessions today/week/month, avg session duration (today/week/month) from `duration_seconds` on closed sessions.

### 9.2 Performance
All queries hit indexed columns (`user_id`, `created_at`, `last_seen_at`, `is_published`) and are aggregate-only (`COUNT`/`SUM`/`GROUP BY`). Acceptable for current scale. If `ActivityLog` grows past ~1M rows, a materialized summary table can be added behind the same function signatures without touching the router.

## 10. UI / Templates

**Visual direction:** Dark neon aesthetic from `feat/studio-dark-neon-reskin`. Reuse Tailwind classes already in the workspace templates. No new CSS files, no chart library in Phase 1.

**Dashboard layout (single scrolling page):**

```
┌──────────────────────────────────────────────────────┐
│  Admin · PxNN                         sjpenn@… ▾    │
├──────────────────────────────────────────────────────┤
│  [Users]  [Revenue]  [Plans]  [Credits]   (30s poll) │
│                                                      │
│  ┌────── Purchase Funnel (7d ▾) ─────────────────┐  │
│  │  Registered        ████████████████████ 120   │  │
│  │  Pricing viewed    ██████████████      84 70% │  │
│  │  Plan selected     ███████             41 49% │  │
│  │  Checkout started  █████               33 80% │  │
│  │  Payment completed ███                 18 55% │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ Active Now ─┐  ┌────── Activity Feed ────────┐  │
│  │  12 online   │  │  14:22 user_b  upload       │  │
│  │  • user_a    │  │  14:21 user_a  rename       │  │
│  │  • user_b    │  │  ...                        │  │
│  └──────────────┘  └──────────────────────────────┘  │
│                                                      │
│  ┌── Stuck at Checkout (manual nudge list) ──────┐  │
│  │  user_c  plan_selected  2h ago  [copy email]  │  │
│  │  user_d  checkout_started 5h    [copy email]  │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────── Publish Announcement ───────────────────┐  │
│  │ Title [____] Body [____] Severity [info ▾]    │  │
│  │ Start [__]   End [__]    [ Publish ]          │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

**KPI cards** — each shows one headline number big plus 2–3 sub-stats (e.g. Users: big `total`, below `new today / week / month`).

**Funnel widget** — horizontal bar per stage with count, percent-of-previous, and drop-off percentage. Window selector (24h / 7d / 30d / all) swaps the partial via HTMX.

**Polling** — each partial block uses `hx-get="..." hx-trigger="every Ns" hx-swap="innerHTML"`. No WebSockets.

**Announcement banner on user side** — new partial `frontend/templates/partials/announcement_banner.html` included at the top of `app.html`. Classes keyed off `severity` (info/success/warn/danger). Dismissible per-browser via `localStorage["dismissed_announcement_id"]`; resets when a new announcement id publishes.

**Admin link in user menu** — conditional `{% if current_user.is_admin %}<a href="/admin">Admin</a>{% endif %}` in the `/app` nav. Non-admins never see it.

## 11. Privacy & Security Notes

- `UserSession.ip_hash` stores `sha256(ip + JWT_SECRET)`, never the raw IP. Enough for rough de-duping, safe for logs.
- Heartbeat endpoint is auth-gated; unauthenticated pings return `401` and don't create rows.
- `require_admin` is applied as a dependency, not a template conditional. Even a hand-crafted `curl` request to `/admin/partials/kpis` is refused.
- Announcement `body` is rendered with Jinja autoescape on (default). Admin is trusted but we still don't `| safe` user-supplied text.

## 12. Out of Scope (Phase 2 backlog)

- Email blasts (SMTP/SES/Mailgun)
- UTM parameter capture and campaign attribution
- Automated nudge engine that consumes `target_funnel_stage` / `target_plan_status`
- Chart.js visualizations on the dashboard
- Role hierarchy beyond `is_admin`
- Session replay / per-user drill-down page
- CSV/Excel export of activity log

## 13. Success Criteria

Phase 1 is done when:
1. `sjpenn@gmail.com` can visit `/admin`, see live KPI cards, funnel widget, activity feed, stuck-at-checkout list, and a banner composer.
2. A non-admin hitting `/admin` gets a 403.
3. Publishing an announcement causes the banner to appear on `/app` for all logged-in users until un-published, end-date-expired, or dismissed client-side.
4. The funnel widget reflects real `pricing_viewed` / `plan_selected` / `checkout_started` / `payment_completed` / `checkout_abandoned` events generated by actual usage.
5. Avg session duration updates as users heartbeat through the app.
6. Docker Postgres boot and local SQLite boot both succeed with the new schema (idempotent migrations).
