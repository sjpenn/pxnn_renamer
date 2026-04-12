# AI Promo Headlines & Trial Credits

**Date**: 2026-04-12
**Status**: Approved

## Overview

Two enhancements:
1. **AI promo headline generator** — "Generate with AI" link on the promotions admin page that auto-populates headline, description, and time period.
2. **Free trial credits** — New users get configurable free credits on registration, adjustable from admin pricing page.

---

## 1. AI Promo Headline Generator

### Service: `backend/app/services/promo_generator.py`

Uses same Anthropic -> OpenRouter -> fallback pattern as `campaign_generator.py`.

**Input**: plan label, plan credits, bonus credits amount.

**Output**: `{ headline, description, duration_days }`

**Prompt**: Generate a catchy promotional headline (under 60 chars), compelling description (1 sentence), and recommended duration in days for a music production SaaS bonus credit offer.

**Fallback**: Template-based — "Buy {credits} credits, get {bonus} FREE!" / "Limited time offer — upgrade your workflow today." / 14 days.

### Admin Route: `POST /admin/promotions/generate`

Accepts `plan_key` and `bonus_credits` as form data. Returns JSON with generated headline, description, and suggested start/end dates.

### Template: `frontend/templates/admin/promotions.html`

Add a "Generate with AI" link next to the Headline input. On click, JS reads the plan_key and bonus_credits values, POSTs to the generate endpoint, and auto-fills headline, description, starts_at, and ends_at fields.

---

## 2. SiteSettings + Trial Credits

### Model: `SiteSettings`

| Column | Type | Notes |
|--------|------|-------|
| `key` | String, PK, unique | e.g., `trial_credits` |
| `value` | String, not null | Stored as string, parsed by consumers |
| `updated_at` | DateTime | |
| `updated_by_id` | Integer FK -> users.id | |

### Service: `backend/app/services/site_settings.py`

- `get_setting(db, key, default)` — returns string value or default
- `set_setting(db, key, value, admin_id)` — upserts the setting

### Registration Changes

- `backend/app/routes/auth.py`: After user creation, read `trial_credits` setting (default "5"), set `user.credit_balance = int(value)`, log `trial_credits_granted` activity.
- `backend/app/routes/oauth.py`: Same logic for Google OAuth new user creation.

### Admin UI

Top of `/admin/pricing` page: a "Site Settings" card with "Free Trial Credits" input and Save button. Posts to `POST /admin/settings/trial_credits`.

---

## Out of Scope

- Per-user trial tracking (separate field)
- Trial expiration dates
- Promo code system
