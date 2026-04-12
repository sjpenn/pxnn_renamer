# Admin-Managed Pricing, Promotions & Credit Clarity

**Date**: 2026-04-12
**Status**: Approved

## Overview

Three enhancements to the PxNN music renamer app:

1. **Admin-editable pricing** — Admin panel controls what users see for plan labels, descriptions, prices, credits, and visibility. Stripe Price IDs remain env-configured (Phase B later).
2. **Automatic promotional bonuses** — Admin creates promotions that grant bonus credits on purchase. Banners auto-display where buying decisions happen.
3. **Credit cost clarity** — Make it obvious that 1 credit = 1 batch export, previewing is free, and re-downloads are free.

---

## 1. Database Models

### `PricingOverride` table

Stores admin overrides for plan display properties. Each row maps to one `plan_key` from the hardcoded `PAYMENT_PLANS` dict.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `plan_key` | String, unique, not null | e.g., `creator_pack` |
| `label` | String, nullable | Overrides default label |
| `description` | Text, nullable | Overrides default description |
| `amount_cents` | Integer, nullable | Overrides display price |
| `credits` | Integer, nullable | Overrides credit count shown |
| `accent` | String, nullable | Overrides accent tag |
| `is_visible` | Boolean, default True | Hide plan from UI |
| `sort_order` | Integer, default 0 | Display ordering |
| `updated_at` | DateTime | Auto-updated |
| `updated_by_id` | Integer FK -> users.id | Admin who last edited |

**Merge logic**: `get_payment_options()` loads all `PricingOverride` rows, merges non-null fields on top of `PAYMENT_PLANS` defaults, filters out `is_visible=False`, and sorts by `sort_order` then original dict order.

### `Promotion` table

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `plan_key` | String, not null | Which plan triggers the bonus |
| `bonus_credits` | Integer, not null | Extra credits granted |
| `headline` | String, not null | Banner text, e.g., "Buy 50 credits, get 20 FREE!" |
| `description` | Text, nullable | Optional subtext |
| `is_active` | Boolean, default False | Toggle on/off |
| `starts_at` | DateTime, nullable | Optional start date |
| `ends_at` | DateTime, nullable | Optional end date |
| `created_by_id` | Integer FK -> users.id | |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

**Constraint**: Only one active promotion per `plan_key` at a time. Enforced in the admin route — when activating a promo, deactivate any other active promo for the same `plan_key`.

**Active promo query**: `is_active=True AND (starts_at IS NULL OR starts_at <= now) AND (ends_at IS NULL OR ends_at > now)`.

---

## 2. Admin Panel: Pricing Management

**Route**: `GET /admin/pricing` — renders `admin/pricing.html`

Displays all 6 plans in a card grid. Each card shows:
- Current effective values (override or default) for: label, description, amount, credits, accent
- Inline form fields to edit each value
- "Visible" toggle
- Sort order number input
- "Reset to default" link per field (deletes the override for that field)

**Route**: `POST /admin/pricing/{plan_key}` — saves overrides

Accepts form data for all editable fields. Creates or updates the `PricingOverride` row for that `plan_key`. Null/empty values clear the override (revert to default).

**Route**: `POST /admin/pricing/{plan_key}/reset` — deletes the override row entirely

---

## 3. Admin Panel: Promotions Management

**Route**: `GET /admin/promotions` — renders `admin/promotions.html`

Shows:
- Create form: plan dropdown, bonus credits, headline, description, start/end dates
- List of all promotions with status badge: Active, Scheduled, Expired, Draft
- Toggle active/inactive button
- Delete button

**Status logic** (display only, not a DB column):
- **Draft**: `is_active=False`
- **Scheduled**: `is_active=True` and `starts_at` is in the future
- **Active**: `is_active=True` and within date range (or no dates set)
- **Expired**: `is_active=True` but `ends_at` is in the past

**Route**: `POST /admin/promotions` — create new promotion
**Route**: `POST /admin/promotions/{id}/toggle` — toggle `is_active` (deactivates other promos for same `plan_key` if activating)
**Route**: `POST /admin/promotions/{id}/delete` — delete promotion

---

## 4. Promo Banner Display

### Home page (pricing section)

Query for any currently active promotion. If found, render a promotional banner **above** the pricing grid:

- Visually distinct from the announcement banner: gradient background (cyan-to-purple or similar), bold headline, optional description
- Links/scrolls to the relevant plan card
- Dismissible via localStorage (same pattern as announcements)

The active promo data is passed to the home page template via the existing route context.

### App billing area

When a logged-in user views their credit balance / billing options in the workspace, show a smaller contextual promo callout card if an active promotion exists:

- Compact card near the credit balance display
- Shows headline and a "Get it now" CTA linking to checkout for that plan
- Same active promo query

---

## 5. Credit Cost Clarity

### Home page pricing section

Add a subtitle below the pricing heading:

> "Preview unlimited batches for free. 1 credit to export your renamed ZIP. Re-downloads are always free."

Styled as `text-ink-dim` helper text, consistent with existing copy.

### Sidebar credit display (`app.html`)

Below the "Credits: N" line, add:

> "1 credit = 1 export"

Styled as `text-[10px] text-ink-mute`.

### Download step in wizard

Before the download button, add a credit cost indicator:

- **First download**: "This will use 1 credit" with a credit icon — amber/warning styled
- **Re-download**: "Free re-download" with a checkmark — green/success styled
- **No credits**: "You need 1 credit to export" with a link to billing — red/danger styled

This info is derived from `collection.download_count` and `user.credit_balance`, both already available in the download flow.

---

## 6. Webhook Enhancement

In `backend/app/routes/payments.py`, inside `_mark_checkout_session_paid()`:

After the normal credit grant, query for an active `Promotion` where `plan_key` matches the purchased plan and the current time is within the date range.

If found:
1. Add `promotion.bonus_credits` to `user.credit_balance`
2. Create an `ActivityLog` with `event_type="promo_credits_granted"` including: promo ID, bonus amount, plan key, new balance
3. The PaymentRecord already tracks the base credits — the bonus is a separate log entry

---

## 7. Modified Existing Code

### `backend/app/core/pricing.py`

- `get_payment_options()` updated to merge `PricingOverride` rows from DB
- Requires a `db` session parameter (breaking change to function signature)
- All callers updated: `dashboard.py`, `payments.py`, home page route

### `backend/app/routes/payments.py`

- `_mark_checkout_session_paid()` extended with promotion bonus logic
- `get_payment_options` API endpoint updated for new signature

### Home page route

- Passes active promotion to template context
- Passes credit cost messaging

### `frontend/templates/app.html`

- Sidebar: credit helper text added
- Billing area: promo callout card added

### Admin nav

- Add "Pricing" and "Promotions" links to admin sidebar/nav

---

## 8. Files to Create

| File | Purpose |
|------|---------|
| `backend/app/database/models.py` | Add `PricingOverride` and `Promotion` models |
| `backend/app/routes/admin.py` | Add pricing and promotions admin routes |
| `frontend/templates/admin/pricing.html` | Pricing management page |
| `frontend/templates/admin/promotions.html` | Promotions management page |
| `frontend/templates/partials/promo_banner.html` | Reusable promo banner partial |

## 9. Files to Modify

| File | Change |
|------|--------|
| `backend/app/core/pricing.py` | Merge override logic in `get_payment_options()` |
| `backend/app/routes/payments.py` | Promo bonus in webhook handler |
| `backend/app/routes/dashboard.py` | Pass `db` to `get_payment_options()` |
| `frontend/templates/home.html` | Promo banner, credit explainer text |
| `frontend/templates/app.html` | Sidebar helper text, promo callout, download credit indicator |
| Admin nav template | Add Pricing + Promotions links |

---

## Out of Scope

- Stripe Price object creation/sync (Phase B — after Stripe setup)
- Promo codes / coupon entry at checkout
- Email notifications for promotions
- Per-user targeted promotions (announcement targeting Phase 2)
