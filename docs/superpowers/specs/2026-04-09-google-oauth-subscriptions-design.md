# Design Spec: Google OAuth + Subscription Payments + Full App Flow
**Date:** 2026-04-09
**Project:** PxNN it (music_renamer)
**Status:** Approved

---

## 1. Overview

Enhance PxNN it with:
1. Google OAuth authentication (alongside existing username/password)
2. Monthly subscription tiers that auto-grant credits (alongside existing one-time credit packs)
3. Fully wired application flow with access control
4. Push to existing GitHub remote and redeploy to existing Railway project

---

## 2. Google OAuth + Account Linking

### Library
`authlib` — OAuth2/OIDC library with native FastAPI/Starlette integration.

### New User Model Fields
| Field | Type | Notes |
|-------|------|-------|
| `google_sub` | String, unique, nullable | Google's stable user ID |
| `email` | String, nullable, indexed | From Google profile; also captured on registration |
| `password_hash` | String, **nullable** | Google-only users have no password |

### New Routes (`backend/app/routes/auth.py`)
- `GET /auth/google/login` — generate state token, store in signed cookie, redirect to Google
- `GET /auth/google/callback` — exchange code, verify ID token, resolve/create user, set JWT cookie, redirect to dashboard

### Account Resolution Logic (callback)
1. Look up by `google_sub` → sign in (returning Google user)
2. Else look up by `email` → link Google to existing account, sign in
3. Else → create new user (`google_sub` + `email`, `password_hash=None`)

### Session State for OAuth
Use `itsdangerous` signed cookies to store the OAuth `state` parameter across the redirect. Railway is single-instance so no shared store needed.

### New Config Vars
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI` (e.g. `https://<app>.railway.app/auth/google/callback`)

### Frontend Changes
- "Sign in with Google" button on login/register UI (index.html)
- Route users to `/auth/google/login` on click

---

## 3. Subscription Payments

### Subscription Tiers (added to `pricing.py`)
| Key | Label | Price | Monthly Credits |
|-----|-------|-------|----------------|
| `starter_monthly` | Starter | $9/mo | 3 credits |
| `pro_monthly` | Pro | $29/mo | 15 credits |
| `label_monthly` | Label | $79/mo | 60 credits |

Existing one-time packs remain unchanged:
- `single_export`: $7 / 1 credit
- `creator_pack`: $39 / 10 credits
- `label_pack`: $149 / 50 credits

### New User Model Fields
| Field | Type | Notes |
|-------|------|-------|
| `subscription_id` | String, nullable | Stripe Subscription ID |
| `subscription_status` | String, nullable | `active`, `past_due`, `canceled`, etc. |
| `subscription_plan` | String, nullable | Plan key (e.g. `pro_monthly`) |

### Checkout Flow
- One-time packs: `mode="payment"` (unchanged)
- Subscription plans: `mode="subscription"` in Stripe Checkout Session
- Both flows create a `PaymentRecord`; subscriptions add a `plan_type="subscription"` field

### PaymentRecord Changes
- Add `plan_type` field (String: `"one_time"` or `"subscription"`) to distinguish records
- Add `stripe_invoice_id` (String, unique, nullable) for subscription renewal records — used as idempotency key to prevent double credit grants on webhook retries

### New Webhook Handlers (`/api/payments/webhook`)
| Stripe Event | Action |
|---|---|
| `checkout.session.completed` | Existing handler extended: detect subscription vs payment mode; for subscriptions, set `subscription_id`, `subscription_status="active"`, `subscription_plan`, `active_plan` |
| `invoice.paid` | Look up user by `stripe_customer_id`, grant monthly credits per plan, log to `ActivityLog` |
| `customer.subscription.deleted` | Set `subscription_status="canceled"`, clear `subscription_plan` and `active_plan` |
| `customer.subscription.updated` | Sync `subscription_status` from Stripe event data |

### New Route
- `POST /api/payments/subscription/cancel` — calls `stripe.Subscription.delete(user.subscription_id)`, logs activity

### New Config Vars
- `STRIPE_STARTER_MONTHLY_PRICE_ID`
- `STRIPE_PRO_MONTHLY_PRICE_ID`
- `STRIPE_LABEL_MONTHLY_PRICE_ID`

### Frontend Changes
- Subscription plan cards on billing/landing page (alongside one-time packs)
- Dashboard: subscription status section (plan name, next renewal date, Cancel button)
- Header/nav: credit balance + subscription badge

---

## 4. Full Application Flow

### User Journey
```
Landing (/) → Sign In / Register (username+password or Google OAuth)
    ↓
Dashboard (/dashboard) — batches, credit balance, subscription status
    ↓
Wizard Step 1 (/wizard/step-1) — drag & drop file upload [login required]
    ↓
Wizard Step 2 (/wizard/step-2) — metadata definition [login required]
    ↓
Wizard Step 3 (/wizard/step-3) — review & download [1 credit deducted on download]
    ↓
Billing (shown inline or redirect if no credits)
```

### Access Control Rules
- Wizard steps 1–2: require login, no credit check
- Wizard step 3 download action: deduct 1 credit; if `credit_balance == 0` redirect to `/?billing=no_credits`
- Billing page: all authenticated users
- Subscription management (cancel): only users with `subscription_status == "active"`

---

## 5. GitHub + Railway Deploy

### GitHub
- Verify `origin` remote is configured
- Push `main` branch to existing remote

### Railway
- Existing Railway project and config remain in place
- Add new environment variables in Railway dashboard before deploy:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
  - `STRIPE_STARTER_MONTHLY_PRICE_ID`
  - `STRIPE_PRO_MONTHLY_PRICE_ID`
  - `STRIPE_LABEL_MONTHLY_PRICE_ID`
- Push to GitHub triggers auto-deploy

---

## 6. Dependencies to Add (`requirements.txt`)
- `authlib` — Google OAuth
- `httpx` — required by authlib for async HTTP
- `itsdangerous` — signed state cookie for OAuth flow

---

## 7. Files to Create or Modify
| File | Change |
|------|--------|
| `backend/app/database/models.py` | Add `google_sub`, `email`, `subscription_id`, `subscription_status`, `subscription_plan`; make `password_hash` nullable |
| `backend/app/database/bootstrap.py` | Ensure new columns are handled in bootstrap |
| `backend/app/core/config.py` | Add Google OAuth and new Stripe price ID vars |
| `backend/app/core/pricing.py` | Add subscription plan definitions |
| `backend/app/core/security.py` | Handle nullable `password_hash` in auth |
| `backend/app/routes/auth.py` | Add Google OAuth routes |
| `backend/app/routes/payments.py` | Add subscription checkout, new webhook handlers, cancel route |
| `frontend/templates/index.html` | Google sign-in button, subscription plan cards |
| `frontend/templates/dashboard.html` | Subscription status section |
| `requirements.txt` | Add authlib, httpx, itsdangerous |
| `docker-compose.yml` | Add new env var pass-throughs |
| `.env.example` | Document all new vars |
