# Design Spec: Marketing Homepage, Global Nav, Auth Pages, Profile
**Date:** 2026-04-10
**Project:** PxNN it (music_renamer)
**Status:** Approved

---

## 1. Overview

Transform PxNN it from a single-page workspace into a proper SaaS surface:

1. **Marketing homepage at `/`** — Flashy landing page with hero animation, problem/solution for producers and labels, features, pricing, social proof
2. **Workspace moved to `/app`** — Current `index.html` functionality, accessed only after login
3. **Dedicated auth routes** — `/login` and `/register` replace the inline forms on the workspace
4. **Profile page at `/profile`** — Identity, Google link, password change, delete account
5. **Global nav component** — Top-right nav on every page with login/logout/profile dropdown
6. **Template refactor** — Extract shared `base.html`, `partials/nav.html`, `partials/footer.html`

Settings page is deferred to a future iteration.

---

## 2. Routes & Access Control

### 2.1 Route Table

| Route | Template | Auth | Behavior |
|---|---|---|---|
| `GET /` | `home.html` | Public | Marketing homepage. If authenticated, 303 redirect to `/app` |
| `GET /app` | `app.html` | Required | Workspace wizard. If not authenticated, 303 redirect to `/login?next=/app` |
| `GET /login` | `auth/login.html` | Public | Login form. If authenticated, 303 redirect to `/app` |
| `GET /register` | `auth/register.html` | Public | Register form. If authenticated, 303 redirect to `/app`. Accepts `?plan=<plan_key>` query param |
| `GET /profile` | `profile.html` | Required | User identity page. If not authenticated, 303 redirect to `/login` |
| `POST /auth/login` | — | — | Unchanged endpoint. On success, 303 redirect to `/app` |
| `POST /auth/register` | — | — | Unchanged endpoint. On success, check pending plan, redirect to `/app` or to checkout |
| `GET /auth/google/callback` | — | — | Unchanged logic. Update redirect target from `/` to `/app` |
| `POST /api/profile/password` | — | Required | Change password. See Section 6 |
| `POST /api/profile/delete` | — | Required | Delete account. See Section 6 |

### 2.2 Access Control Helper

Protected page routes (`GET /app`, `GET /profile`) take `current_user: Optional[User] = Depends(get_current_user_optional)` and explicitly check `if current_user is None: return RedirectResponse(url="/login", status_code=303)` at the top of the handler. `get_current_user_optional` is a thin wrapper around the existing `get_current_user` that returns `None` instead of raising on missing credentials.

Add `get_current_user_optional` to `backend/app/core/security.py` if not already present.

---

## 3. Template Architecture

### 3.1 File Structure

```
frontend/templates/
├── base.html                    NEW — HTML skeleton, head, Tailwind config, shared CSS/fonts
├── partials/
│   ├── nav.html                 NEW — Top-right nav component
│   └── footer.html              NEW — Marketing footer
├── home.html                    NEW — Marketing homepage
├── app.html                     RENAMED from index.html — Workspace wizard
├── profile.html                 NEW — User profile page
└── auth/
    ├── login.html               NEW — Login form page
    └── register.html            NEW — Register form page
```

### 3.2 `base.html` Responsibilities

- `<!doctype html>`, `<html>`, `<head>` with meta tags
- Font imports: Inter, Manrope, Geist Mono, Material Symbols Outlined
- Tailwind CDN + inline `tailwind.config` with existing color tokens and font families
- `<link rel="stylesheet" href="/static/css/style.css">`
- `<body class="{% block body_class %}{% endblock %}">` with:
  - `{% block body %}{% endblock %}` — full body control (used by `app.html`)

### 3.3 Blocks Exposed

| Block | Purpose |
|---|---|
| `title` | Page `<title>` content |
| `extra_head` | Page-specific styles, meta tags, or scripts |
| `body_class` | Additional CSS classes on `<body>` |
| `body` | Full body content |

### 3.4 `app.html` Migration Steps

1. Copy current `index.html` to `app.html` verbatim
2. Replace `<!doctype html>` through `</head>` with `{% extends "base.html" %}{% block title %}PxNN it — Workspace{% endblock %}{% block body %}`
3. Wrap the body content, close with `{% endblock %}`
4. Remove the inline login/register forms inside `signed-out-shell`
5. Remove the `wizard-lockout` overlay (logged-out users cannot reach `/app`)
6. Remove signed-out code branches from the existing JavaScript (`state.user` will always be truthy on this page)
7. Include `{% include "partials/nav.html" %}` at the top of the main content area, above the current "Active Session" header
8. Delete the old `index.html` file

The workspace continues to have its own "Active Session" sticky header below the global nav.

---

## 4. Nav Component

**File:** `frontend/templates/partials/nav.html`

### 4.1 Layout

Horizontal bar, sticky top, full width, 64px tall (`h-16`), visible on every page.

```
┌──────────────────────────────────────────────────────────────────┐
│  [PxNN it]   Features  Pricing                     [nav right]  │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Logged-Out State

Nav right: `[Sign in]` (ghost button → `/login`) + `[Get Started]` (solid primary button → `/register`)

### 4.3 Logged-In State

Nav right: `[Dashboard]` (text link → `/app`) + `[Billing]` (text link → `/app?billing=options`) + `[👤 username ▼]` avatar dropdown

**Dropdown contents:**
- Username header (not clickable, shows `current_user.username`)
- `Profile` → `/profile`
- Divider
- `Logout` → POST to `/auth/logout` (form submit), redirects to `/`

### 4.4 Left-Side Links (always visible)

- `PxNN it` logo (text + icon) → links to `/` when logged out, `/app` when logged in
- `Features` → `/#features` (hash anchor)
- `Pricing` → `/#pricing` (hash anchor)

The `Features` and `Pricing` links are hidden when `page` is `"app"` or `"profile"` since hash anchors on those pages don't go anywhere useful.

### 4.5 Active Link Styling

The nav partial receives a `page` variable from the route context:
- `"home"` — highlight logo
- `"app"` — highlight "Dashboard"
- `"login"` — highlight "Sign in"
- `"register"` — highlight "Get Started"
- `"profile"` — no highlight on main nav links

Active state: `text-primary-container` with `border-b-2 border-primary-container`.

### 4.6 Dropdown Implementation

Pure vanilla JavaScript toggle (~20 lines):

```javascript
const dropdownBtn = document.getElementById('nav-user-dropdown-btn');
const dropdownMenu = document.getElementById('nav-user-dropdown-menu');
if (dropdownBtn && dropdownMenu) {
    dropdownBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownMenu.classList.toggle('hidden');
    });
    document.addEventListener('click', () => {
        dropdownMenu.classList.add('hidden');
    });
}
```

No framework dependencies.

### 4.7 Mobile Responsive

- Below 768px (`md:` breakpoint):
  - Left links (`Features`, `Pricing`) collapse into a hamburger menu
  - Logged-out nav right: shows only `[Sign in]` (full width)
  - Logged-in nav right: shows only avatar dropdown
- Hamburger uses a CSS `:checked` hidden-checkbox trick to toggle a slide-down panel. No JS.

### 4.8 Styling

- Background: `bg-white/90 backdrop-blur-md` on marketing/auth/profile; `bg-surface-bright border-b border-outline/10` on `/app`
- Z-index: `z-50`
- Border bottom: `border-b border-outline/10`

---

## 5. Marketing Homepage Content

**File:** `frontend/templates/home.html`

One long scrollable page with 8 sections. Narrative: **"Your file names are chaos → We fix them in seconds → Here's proof → Start free."**

### 5.1 Hero Section

**Layout:** Centered full-width section, min-height 80vh, gradient background.

**Copy:**
- Eyebrow: `BULK AUDIO FILE RENAMER`
- Headline (H1, Manrope 800, 56px/clamped): `Stop drowning in "track_final_v2.wav"`
- Subhead (Inter 400, 20px): `PxNN it renames hundreds of audio files at once with clean, consistent, metadata-rich filenames`
- Primary CTA: `Get Started Free` → `/register`
- Secondary CTA: `See how it works` → smooth scroll to `#how-it-works`

**Hero animation:** A card below the CTAs shows filename transformation on a loop.

**Animation implementation:** Three stacked filename pairs use CSS `@keyframes` with `steps()` timing to simulate typing of the "after" filename, with `animation-delay` cycling between the three stacks on a 10-second loop. Pure CSS, zero JavaScript.

**Three filename pairs:**
1. `track_final_v2_FIX (1).wav` → `JuneLake_Nightfall_Cmin_128BPM_2026.wav`
2. `beat ideas 03 FULL.wav` → `JuneLake_Sunset_Amin_90BPM_2026.wav`
3. `Untitled Project 14.aif` → `JuneLake_HorizonLine_Gmaj_120BPM_2026.aif`

### 5.2 Problem Section (Dual Audience)

Side-by-side two-column grid, id `#problem`.

**Left column — For Producers:**
- Material icon: `music_note`
- Headline: `Beat makers: every session is a mess`
- Three bullets:
  - `Downloads folder full of "beat1.wav", "beat1_FINAL.wav", "beat1_FINAL_REAL.wav"`
  - `Clients demand specific naming formats for every delivery`
  - `Can't find last month's session when you need it`

**Right column — For Labels & A&R:**
- Material icon: `album`
- Headline: `Labels: 500 demos a week, zero consistency`
- Three bullets:
  - `Artists submit with inconsistent or missing metadata`
  - `Manual rename takes 2 hours per batch, every batch`
  - `Lost track of which version of which song from which artist`

Each column is a rounded card with a subtle border and hover lift.

### 5.3 How It Works Section

Id `#how-it-works`. Three horizontal step cards with animated connector arrows.

| Step | Icon | Title | Description |
|---|---|---|---|
| 01 | `upload_file` | Upload | Drag & drop your audio files |
| 02 | `tune` | Define | Set your format template |
| 03 | `download` | Export | Download your renamed archive |

On scroll into view, the connector arrows fade in via IntersectionObserver.

### 5.4 Live Example Section

Two-column table showing five filename transformations. Styled as two stacked cards on mobile.

| Before | After |
|---|---|
| `track_final_v2 (1).wav` | `JuneLake_Nightfall_Cmin_128BPM.wav` |
| `beat ideas 03 FULL.wav` | `JuneLake_Sunset_Amin_90BPM.wav` |
| `Untitled Project 14.aif` | `JuneLake_HorizonLine_Gmaj_120BPM.aif` |
| `mix_master_real_final.mp3` | `JuneLake_MidnightDrive_Dmin_140BPM.mp3` |
| `nev song.wav` | `JuneLake_FirstLight_Emaj_110BPM.wav` |

On scroll, each row fades in with a 100ms stagger (via IntersectionObserver with CSS classes).

### 5.5 Features Grid

Six feature cards in a 3×2 grid (1×6 on mobile), id `#features`.

| Icon | Title | Description |
|---|---|---|
| `bolt` | Lightning fast | Rename hundreds of files in seconds, not hours |
| `tune` | Flexible templates | `{ARTIST}_{TITLE}_{KEY}_{BPM}` — build any format |
| `auto_fix_high` | Precision cleanup | Strip version tags, fix casing, normalize spaces automatically |
| `music_note` | All major formats | WAV, MP3, AIFF, FLAC — every format you actually use |
| `history` | Batch history | Every rename is logged. Revisit, re-export, never lose work |
| `lock` | Private by default | Your files are processed and deleted. Nothing is stored |

### 5.6 Pricing Section

Id `#pricing`. Two-column split: subscriptions on the left, one-time packs on the right.

- Pulls `payment_options` from the `/` route context (same data structure the workspace uses)
- Subscription cards use `{amount}<small>/mo</small>` and `{credits} credits/month` labels
- One-time cards use `{amount}` and `{credits} credits` labels
- Each card CTA button links to `/register?plan=<plan_key>`
- Plan key is stored in the Starlette session by `/register` route; after signup, the user is redirected to Stripe checkout for that plan (or to `/app` if no plan)

### 5.7 Stats / Social Proof Counter

A single horizontal strip with three counters. Numbers count up from 0 when scrolled into view using a small IntersectionObserver (~20 lines JS).

- `50,000+` Files renamed
- `2.3s` Average per file
- `99.7%` Customer satisfaction

**These are hardcoded marketing placeholder numbers**, not pulled from real data. The template contains a comment documenting this.

### 5.8 Final CTA + Footer

Full-width dark gradient band:
- Headline: `Ready to stop fighting your filenames?`
- Primary CTA: `Get Started Free — No card required` → `/register`

Footer (`partials/footer.html`):
- Left: `PxNN it` logo + tagline `Bulk audio file renamer for producers and labels`
- Center: links `Features` · `Pricing` · `Login` · `Register`
- Right: `© 2026 PxNN it` + GitHub icon link to `https://github.com/sjpenn/pxnn_renamer`

### 5.9 Page-Wide Micro-Animations

- Sections fade-in on scroll using a single `IntersectionObserver` that adds `.in-view` CSS class to any element with `.reveal-on-scroll`. ~30 lines total JS.
- CSS: `.reveal-on-scroll { opacity: 0; transform: translateY(20px); transition: all 0.6s ease-out; } .reveal-on-scroll.in-view { opacity: 1; transform: translateY(0); }`
- Feature card hover: subtle lift and shadow via Tailwind `hover:-translate-y-1 hover:shadow-lg`
- Smooth scroll behavior: `html { scroll-behavior: smooth; }`
- CTAs: no pulse animation (keep it calm)

---

## 6. Auth Pages & Profile

### 6.1 `/login` — `auth/login.html`

Centered card (`max-w-md`) on a full-height gradient background.

- Page title: `Sign in to PxNN it`
- Username field
- Password field
- Primary button: `Sign in` → POST to `/auth/login`
- Divider: `or`
- Google button: `Continue with Google` → `/auth/google/login` (hidden when `google_oauth_enabled` is false)
- Footer link: `Don't have an account? Sign up` → `/register`
- Error banner: displayed when `?error=invalid_credentials` is present

**Behavior:** Route handler redirects authenticated users to `/app` before rendering.

### 6.2 `/register` — `auth/register.html`

Same centered card layout.

- Page title: `Create your PxNN it account`
- Username field
- Email field (optional)
- Password field
- Primary button: `Create account` → POST to `/auth/register`
- Divider: `or`
- Google button: `Continue with Google` → `/auth/google/login`
- Footer link: `Already have an account? Sign in` → `/login`

**Plan key handling:**
- `GET /register?plan=<plan_key>` stores `plan_key` in `request.session["pending_plan"]` before rendering the template
- After successful registration via `POST /auth/register`, check `request.session.pop("pending_plan", None)`:
  - If set and valid, redirect to `/api/payments/checkout?plan_key=<plan_key>` flow
  - If not set, redirect to `/app`
- Implementation: `set_pending_plan(request, plan_key)` and `pop_pending_plan(request)` helpers in `backend/app/core/security.py`

### 6.3 `/profile` — `profile.html`

Full nav + centered content (`max-w-2xl`). Five cards stacked vertically.

**Card 1 — Account identity (read-only)**
- Username
- Email (or `Not set` if null)
- Account created date (formatted from `user.created_at`)
- Subscription status badge: reads `current_user.subscription_status` (`active`, `canceled`, `none`)

**Card 2 — Connected accounts**
- Google: if `current_user.google_sub` is set, show `Connected` badge with email; otherwise show `Not connected` with `Connect Google` button → `/auth/google/login`

**Card 3 — Change password**
- Current password field
- New password field
- Confirm new password field
- Button: `Update password` → POST to `/api/profile/password`
- **If `current_user.password_hash is None`** (Google-only account), replace the entire card body with: `This is a Google-only account. Sign in with Google to authenticate.`

**Card 4 — Credit balance & subscription**
- Display: `{current_user.credit_balance}` credits
- Display: Active subscription plan name (formatted from `subscription_plan`) or `No active subscription`
- Link: `Manage billing` → `/app?billing=options`

**Card 5 — Danger zone**
- Red-outlined `Delete account` button
- Clicking opens an inline `<dialog>` modal (no framework)
- Modal content: `Type your username to confirm` input + `Permanently delete account` button
- Confirm submits a form to `POST /api/profile/delete` with `username_confirmation` field

### 6.4 New Backend Endpoints

File: `backend/app/routes/profile.py` (new)

| Endpoint | Method | Body | Behavior |
|---|---|---|---|
| `/api/profile/password` | POST | `current_password`, `new_password`, `confirm_password` | Verify `current_password` matches current `password_hash`; verify `new_password == confirm_password` and length ≥ 8; hash `new_password` and update `User.password_hash`; log `ActivityLog` event_type=`password_changed`; return `{"ok": true}`. If `user.password_hash is None`, return 400 `This account has no password`. |
| `/api/profile/delete` | POST | `username_confirmation` | Verify `username_confirmation == current_user.username`; delete the `User` row (SQLAlchemy cascades to `ActivityLog` and `PaymentRecord`); clear `pxnn_session` cookie; return 303 redirect to `/` |

**Error codes:**
- Password endpoint: 401 for wrong current password, 400 for mismatched confirmation, 400 for password shorter than 8 characters, 400 for Google-only account
- Delete endpoint: 400 for wrong username confirmation

Both routes require authentication via existing `get_current_user` dependency.

**Register in `main.py`:** `app.include_router(profile_router)`

---

## 7. Error Handling

### 7.1 Route-Level Redirects

| Condition | Response |
|---|---|
| `GET /` when authenticated | 303 redirect to `/app` |
| `GET /app` when not authenticated | 303 redirect to `/login?next=/app` |
| `GET /login` when authenticated | 303 redirect to `/app` |
| `GET /register` when authenticated | 303 redirect to `/app` |
| `GET /profile` when not authenticated | 303 redirect to `/login` |

### 7.2 Auth Page Error Banners

- Login failure: backend redirects to `/login?error=invalid_credentials`; template renders error banner when `request.query_params.get("error")` is `"invalid_credentials"`
- Register validation errors: `/register?error=duplicate_username`, `/register?error=weak_password`, etc.

### 7.3 Profile Endpoint Errors

Password endpoint:
- 401 for wrong current password → `{"detail": "Current password is incorrect"}`
- 400 for mismatched confirmation → `{"detail": "Password confirmation does not match"}`
- 400 for weak password → `{"detail": "Password must be at least 8 characters"}`
- 400 for Google-only account → `{"detail": "This account has no password"}`

Delete endpoint:
- 400 for wrong username → `{"detail": "Username confirmation does not match"}`

Existing JSON APIs remain unchanged — new page routes return HTML; new `/api/profile/*` endpoints return JSON.

---

## 8. Testing

All tests live in the existing `tests/` directory and use the existing `client` and `db` pytest fixtures.

### 8.1 Test Files

**`tests/test_routes_home.py`**
- `test_home_renders_for_anonymous` — `GET /` returns 200 with marketing content
- `test_home_redirects_authenticated_to_app` — `GET /` with logged-in user returns 303 to `/app`
- `test_app_requires_auth` — `GET /app` without login returns 303 to `/login`

**`tests/test_routes_auth_pages.py`**
- `test_login_page_renders_for_anonymous`
- `test_login_page_redirects_authenticated_to_app`
- `test_register_page_renders_for_anonymous`
- `test_register_page_redirects_authenticated_to_app`
- `test_register_stores_pending_plan_in_session` — `GET /register?plan=pro_monthly` stores `"pro_monthly"` in session

**`tests/test_profile.py`**
- `test_profile_page_renders_for_authenticated`
- `test_profile_page_redirects_anonymous`
- `test_password_update_success`
- `test_password_update_wrong_current` — returns 401
- `test_password_update_mismatched_confirmation` — returns 400
- `test_password_update_weak_password` — returns 400
- `test_password_update_google_only_user` — returns 400
- `test_delete_account_success` — user row deleted, cookie cleared
- `test_delete_account_wrong_username` — returns 400

### 8.2 Frontend Testing

No automated frontend tests. Visual verification via `docker-compose up` → browser inspection.

---

## 9. Integration Notes

### 9.1 Google OAuth Callback Target Change

In `backend/app/routes/oauth.py`, the `google_callback` route currently redirects to `/`. Change the redirect target to `/app` so users land in the workspace after OAuth login.

### 9.2 Session Helpers

Add to `backend/app/core/security.py`:

```python
def set_pending_plan(request: Request, plan_key: str) -> None:
    request.session["pending_plan"] = plan_key

def pop_pending_plan(request: Request) -> Optional[str]:
    return request.session.pop("pending_plan", None)
```

### 9.3 Template Context Conventions

Every page route must pass:
- `current_user` — the `User` object or `None`
- `page` — a string identifier: `"home"`, `"app"`, `"login"`, `"register"`, `"profile"`

The nav partial reads both to render the appropriate state.

### 9.4 Dependencies

Zero new Python or frontend dependencies. Everything uses existing Tailwind + vanilla JS + Jinja2 + authlib session middleware.

### 9.5 Migration Safety

- `index.html` is renamed to `app.html` in the same commit as the new routes to avoid a broken intermediate state
- The old `GET /` route handler logic is moved verbatim to `GET /app`, then the new marketing handler replaces `GET /`
- All existing API endpoints (`/api/*`) are unchanged
- All existing tests continue to pass

### 9.6 Logout Flow

The current logout (if any) needs to be updated to redirect to `/` (marketing page) instead of rendering the now-removed inline login form. Verify `POST /auth/logout` or equivalent clears the cookie and returns a 303 to `/`.

---

## 10. File Changes Summary

| File | Action |
|---|---|
| `frontend/templates/base.html` | Create |
| `frontend/templates/partials/nav.html` | Create |
| `frontend/templates/partials/footer.html` | Create |
| `frontend/templates/home.html` | Create |
| `frontend/templates/app.html` | Create from old `index.html` |
| `frontend/templates/index.html` | Delete |
| `frontend/templates/auth/login.html` | Create |
| `frontend/templates/auth/register.html` | Create |
| `frontend/templates/profile.html` | Create |
| `frontend/static/css/style.css` | Modify — add marketing page animation keyframes and utility classes |
| `backend/app/main.py` | Modify — split old `/` handler into `/` (marketing) + `/app` (workspace); add `/login`, `/register`, `/profile` route handlers; include `profile_router` |
| `backend/app/routes/oauth.py` | Modify — change OAuth callback redirect from `/` to `/app` |
| `backend/app/routes/auth.py` | Modify — post-login and post-register redirects check pending plan, go to `/app` or checkout |
| `backend/app/routes/profile.py` | Create — password update and delete account endpoints |
| `backend/app/core/security.py` | Modify — add `require_auth_redirect`, `set_pending_plan`, `pop_pending_plan` helpers |
| `tests/test_routes_home.py` | Create |
| `tests/test_routes_auth_pages.py` | Create |
| `tests/test_profile.py` | Create |
