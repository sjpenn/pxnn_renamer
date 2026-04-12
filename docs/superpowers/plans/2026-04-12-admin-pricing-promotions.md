# Admin-Managed Pricing, Promotions & Credit Clarity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins edit pricing display, create promotional bonus credit offers, and make credit costs clear throughout the UI.

**Architecture:** Two new DB models (`PricingOverride`, `Promotion`) with admin CRUD routes. `get_payment_options()` gains a `db` parameter to merge overrides. The payment webhook grants promo bonus credits automatically. Frontend templates updated with promo banners and credit cost callouts.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2, HTMX, Tailwind CSS (existing stack)

---

### Task 1: Add PricingOverride and Promotion database models

**Files:**
- Modify: `backend/app/database/models.py` (add 2 new classes at end)
- Modify: `backend/app/database/bootstrap.py` (comment noting create_all handles new tables)

- [ ] **Step 1: Add PricingOverride model to models.py**

Add after the `CampaignImage` class at the end of the file:

```python
class PricingOverride(Base):
    __tablename__ = "pricing_overrides"

    id = Column(Integer, primary_key=True, index=True)
    plan_key = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    amount_cents = Column(Integer, nullable=True)
    credits = Column(Integer, nullable=True)
    accent = Column(String, nullable=True)
    is_visible = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True, index=True)
    plan_key = Column(String, nullable=False, index=True)
    bonus_credits = Column(Integer, nullable=False)
    headline = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

- [ ] **Step 2: Add bootstrap comment for new tables**

In `backend/app/database/bootstrap.py`, add this comment at the end of the `bootstrap_database()` function (after line 156):

```python
    # PricingOverride, Promotion — brand-new tables, handled by create_all above — no _ensure_column needed.
```

- [ ] **Step 3: Verify the app starts without errors**

Run: `cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && docker-compose up --build -d && sleep 5 && docker-compose logs --tail=30 backend`

Expected: No errors, tables created successfully.

- [ ] **Step 4: Commit**

```bash
git add backend/app/database/models.py backend/app/database/bootstrap.py
git commit -m "feat(db): add PricingOverride and Promotion models"
```

---

### Task 2: Update get_payment_options() to merge pricing overrides from DB

**Files:**
- Modify: `backend/app/core/pricing.py` (update `get_payment_options` and `get_payment_plan`)
- Modify: `backend/app/main.py` (pass `db` to `get_payment_options`)
- Modify: `backend/app/routes/dashboard.py` (pass `db` to `get_payment_options`)
- Modify: `backend/app/routes/payments.py` (pass `db` to `get_payment_options`)

- [ ] **Step 1: Update pricing.py — add db-aware get_payment_options**

Replace the entire `get_payment_options` function and add a helper:

```python
from typing import Optional
from sqlalchemy.orm import Session


def _format_amount(amount_cents: int) -> str:
    dollars = amount_cents / 100
    if dollars.is_integer():
        return f"${int(dollars)}"
    return f"${dollars:.2f}"


def get_payment_options(db: Optional[Session] = None) -> list[dict]:
    overrides_by_key = {}
    if db is not None:
        from ..database.models import PricingOverride
        for row in db.query(PricingOverride).all():
            overrides_by_key[row.plan_key] = row

    options = []
    for key, plan in PAYMENT_PLANS.items():
        override = overrides_by_key.get(key)
        label = (override.label if override and override.label else plan["label"])
        description = (override.description if override and override.description else plan["description"])
        amount_cents = (override.amount_cents if override and override.amount_cents is not None else plan["amount_cents"])
        credits = (override.credits if override and override.credits is not None else plan["credits"])
        accent = (override.accent if override and override.accent else plan["accent"])
        is_visible = override.is_visible if override else True
        sort_order = override.sort_order if override else 0

        if not is_visible:
            continue

        price_id = getattr(settings, plan["price_id_setting"])
        options.append(
            {
                "key": key,
                "label": label,
                "description": description,
                "amount_cents": amount_cents,
                "amount_label": _format_amount(amount_cents),
                "credits": credits,
                "accent": accent,
                "stripe_price_id": price_id,
                "plan_type": plan["plan_type"],
                "sort_order": sort_order,
            }
        )
    options.sort(key=lambda o: o["sort_order"])
    return options
```

Remove the old `_format_amount` and `get_payment_options` functions (they're replaced above). Keep `get_payment_plan` and `PAYMENT_PLANS` as-is since `get_payment_plan` is used for Stripe checkout and should use hardcoded values.

- [ ] **Step 2: Update main.py callers**

In `backend/app/main.py`, change both `get_payment_options()` calls (lines ~109 and ~132) to pass `db`:

```python
"payment_options": get_payment_options(db),
```

The home route (line ~109) doesn't currently have a `db` dependency. Add it to the function signature. Find the home route function and add `db: Session = Depends(get_db)` parameter. Also add the import for `get_db` and `Session` if not already present at the top.

Looking at the home route around line 103, the function that renders `home.html` needs db access. Check the function signature and add the dependency.

- [ ] **Step 3: Update dashboard.py caller**

In `backend/app/routes/dashboard.py`, change line 100:

```python
"payment_options": get_payment_options(db),
```

The `db` session is already available as a parameter in that function.

- [ ] **Step 4: Update payments.py caller**

In `backend/app/routes/payments.py`, change the `payment_options` endpoint (line 245-246):

```python
@router.get("/api/payments/options")
async def payment_options(db: Session = Depends(get_db)):
    return {"payment_options": get_payment_options(db)}
```

The `get_db` import is already present.

- [ ] **Step 5: Verify the app starts and pricing page loads**

Run: `docker-compose up --build -d && sleep 5 && docker-compose logs --tail=30 backend`

Expected: No errors. Home page still shows all 6 plans with their default values (no overrides exist yet).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/pricing.py backend/app/main.py backend/app/routes/dashboard.py backend/app/routes/payments.py
git commit -m "feat(pricing): merge PricingOverride from DB into get_payment_options"
```

---

### Task 3: Add promotions service for active promo queries

**Files:**
- Create: `backend/app/services/promotions.py`

- [ ] **Step 1: Create the promotions service**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/promotions.py
git commit -m "feat(services): add promotions service for active promo queries"
```

---

### Task 4: Add admin pricing management routes and template

**Files:**
- Modify: `backend/app/routes/admin.py` (add pricing routes)
- Modify: `backend/app/database/models.py` (import in admin.py)
- Create: `frontend/templates/admin/pricing.html`
- Modify: `frontend/templates/admin/base.html` (add nav link)

- [ ] **Step 1: Add pricing routes to admin.py**

Add these imports at the top of `backend/app/routes/admin.py`:

```python
from ..database.models import ActivityLog, Announcement, Campaign, CampaignImage, CampaignVariant, CommentCluster, PricingOverride, Promotion, UIComment, User
from ..core.pricing import PAYMENT_PLANS
```

(Replace the existing `..database.models` import line to include `PricingOverride` and `Promotion`.)

Add these routes before the campaigns section (before the `# Campaigns` comment block):

```python
# --------------------------------------------------------------------------- #
# Pricing — admin overrides for plan display
# --------------------------------------------------------------------------- #


@router.get("/pricing", response_class=HTMLResponse)
async def admin_pricing_page(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    overrides = {row.plan_key: row for row in db.query(PricingOverride).all()}
    plans = []
    for key, plan in PAYMENT_PLANS.items():
        override = overrides.get(key)
        plans.append({
            "key": key,
            "default_label": plan["label"],
            "default_description": plan["description"],
            "default_amount_cents": plan["amount_cents"],
            "default_credits": plan["credits"],
            "default_accent": plan["accent"],
            "plan_type": plan["plan_type"],
            "label": override.label if override and override.label else "",
            "description": override.description if override and override.description else "",
            "amount_cents": override.amount_cents if override and override.amount_cents is not None else "",
            "credits": override.credits if override and override.credits is not None else "",
            "accent": override.accent if override and override.accent else "",
            "is_visible": override.is_visible if override else True,
            "sort_order": override.sort_order if override else 0,
        })
    return templates.TemplateResponse(
        request,
        "admin/pricing.html",
        {
            "current_user": admin,
            "plans": plans,
            "title": "Pricing · PxNN Admin",
        },
    )


@router.post("/pricing/{plan_key}")
async def admin_pricing_update(
    plan_key: str,
    label: str = Form(""),
    description: str = Form(""),
    amount_cents: str = Form(""),
    credits: str = Form(""),
    accent: str = Form(""),
    is_visible: str = Form("on"),
    sort_order: int = Form(0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if plan_key not in PAYMENT_PLANS:
        raise HTTPException(status_code=404, detail="Unknown plan key.")

    override = db.query(PricingOverride).filter(PricingOverride.plan_key == plan_key).first()
    if not override:
        override = PricingOverride(plan_key=plan_key)
        db.add(override)

    override.label = label.strip() or None
    override.description = description.strip() or None
    override.amount_cents = int(amount_cents) if amount_cents.strip() else None
    override.credits = int(credits) if credits.strip() else None
    override.accent = accent.strip() or None
    override.is_visible = is_visible == "on"
    override.sort_order = sort_order
    override.updated_by_id = admin.id
    db.commit()
    return RedirectResponse(url="/admin/pricing", status_code=303)


@router.post("/pricing/{plan_key}/reset")
async def admin_pricing_reset(
    plan_key: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    override = db.query(PricingOverride).filter(PricingOverride.plan_key == plan_key).first()
    if override:
        db.delete(override)
        db.commit()
    return RedirectResponse(url="/admin/pricing", status_code=303)
```

- [ ] **Step 2: Create the pricing admin template**

Create `frontend/templates/admin/pricing.html`:

```html
{% extends "admin/base.html" %}

{% block admin_content %}
<div class="space-y-6">
  <div>
    <h1 class="text-2xl font-display font-bold text-ink">Pricing Management</h1>
    <p class="mt-1 text-sm text-ink-dim">Override plan display values. Empty fields use defaults. Stripe prices remain unchanged.</p>
  </div>

  <div class="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
    {% for plan in plans %}
    <form action="/admin/pricing/{{ plan.key }}" method="POST"
          class="rounded-xl border border-hairline bg-stage-raised p-5 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-[10px] font-bold uppercase tracking-widest text-cyan">{{ plan.plan_type }}</p>
          <h3 class="text-lg font-display font-bold text-ink">{{ plan.default_label }}</h3>
          <p class="text-xs text-ink-mute">Key: {{ plan.key }}</p>
        </div>
        <label class="flex items-center gap-2 text-xs text-ink-dim">
          <input type="checkbox" name="is_visible" value="on" {% if plan.is_visible %}checked{% endif %}
                 class="accent-cyan">
          Visible
        </label>
      </div>

      <div class="space-y-3">
        <div>
          <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">
            Label <span class="font-normal opacity-60">(default: {{ plan.default_label }})</span>
          </label>
          <input type="text" name="label" value="{{ plan.label }}" placeholder="{{ plan.default_label }}"
                 class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">
        </div>

        <div>
          <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">
            Description <span class="font-normal opacity-60">(default: {{ plan.default_description[:40] }}...)</span>
          </label>
          <textarea name="description" placeholder="{{ plan.default_description }}" rows="2"
                    class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">{{ plan.description }}</textarea>
        </div>

        <div class="grid grid-cols-3 gap-3">
          <div>
            <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">
              Price (cents)
            </label>
            <input type="number" name="amount_cents" value="{{ plan.amount_cents }}" placeholder="{{ plan.default_amount_cents }}"
                   class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">
          </div>
          <div>
            <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">
              Credits
            </label>
            <input type="number" name="credits" value="{{ plan.credits }}" placeholder="{{ plan.default_credits }}"
                   class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">
          </div>
          <div>
            <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">
              Sort
            </label>
            <input type="number" name="sort_order" value="{{ plan.sort_order }}"
                   class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">
          </div>
        </div>

        <div>
          <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">
            Accent Tag <span class="font-normal opacity-60">(default: {{ plan.default_accent }})</span>
          </label>
          <input type="text" name="accent" value="{{ plan.accent }}" placeholder="{{ plan.default_accent }}"
                 class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">
        </div>
      </div>

      <div class="flex items-center gap-3 pt-2 border-t border-hairline">
        <button type="submit" class="px-4 py-2 rounded-lg bg-cyan text-stage text-xs font-bold uppercase tracking-widest hover:bg-cyan/80 transition">
          Save
        </button>
        <button type="button" class="px-4 py-2 rounded-lg border border-hairline text-xs font-bold uppercase tracking-widest text-ink-dim hover:text-ink transition"
                onclick="fetch('/admin/pricing/{{ plan.key }}/reset', {method:'POST'}).then(()=>location.reload())">
          Reset to Defaults
        </button>
      </div>
    </form>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Add nav links to admin base template**

In `frontend/templates/admin/base.html`, add two new links in the `<nav>` element after the "Campaigns" link (line 23):

```html
        <a href="/admin/pricing" class="hover:text-ink transition">Pricing</a>
        <a href="/admin/promotions" class="hover:text-ink transition">Promotions</a>
```

- [ ] **Step 4: Verify the pricing admin page loads**

Run: `docker-compose up --build -d && sleep 5 && docker-compose logs --tail=30 backend`

Navigate to `/admin/pricing` — should show all 6 plans with editable fields.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/admin.py frontend/templates/admin/pricing.html frontend/templates/admin/base.html
git commit -m "feat(admin): add pricing management page with plan overrides"
```

---

### Task 5: Add admin promotions management routes and template

**Files:**
- Modify: `backend/app/routes/admin.py` (add promotion routes)
- Create: `frontend/templates/admin/promotions.html`

- [ ] **Step 1: Add promotions routes to admin.py**

Add these routes after the pricing routes section:

```python
# --------------------------------------------------------------------------- #
# Promotions — bonus credit offers tied to plans
# --------------------------------------------------------------------------- #


@router.get("/promotions", response_class=HTMLResponse)
async def admin_promotions_page(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(Promotion).order_by(Promotion.created_at.desc()).all()
    now = datetime.utcnow()
    promos = []
    for row in rows:
        if not row.is_active:
            status = "draft"
        elif row.starts_at and row.starts_at > now:
            status = "scheduled"
        elif row.ends_at and row.ends_at < now:
            status = "expired"
        else:
            status = "active"
        promos.append({"row": row, "status": status})

    plan_choices = [{"key": k, "label": v["label"]} for k, v in PAYMENT_PLANS.items()]
    return templates.TemplateResponse(
        request,
        "admin/promotions.html",
        {
            "current_user": admin,
            "promos": promos,
            "plan_choices": plan_choices,
            "title": "Promotions · PxNN Admin",
        },
    )


@router.post("/promotions")
async def admin_promotions_create(
    plan_key: str = Form(...),
    bonus_credits: int = Form(...),
    headline: str = Form(...),
    description: str = Form(""),
    starts_at: str = Form(""),
    ends_at: str = Form(""),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if plan_key not in PAYMENT_PLANS:
        raise HTTPException(status_code=400, detail="Unknown plan key.")
    if bonus_credits <= 0:
        raise HTTPException(status_code=400, detail="Bonus credits must be positive.")

    promo = Promotion(
        plan_key=plan_key,
        bonus_credits=bonus_credits,
        headline=headline.strip(),
        description=description.strip() or None,
        is_active=False,
        starts_at=datetime.fromisoformat(starts_at) if starts_at.strip() else None,
        ends_at=datetime.fromisoformat(ends_at) if ends_at.strip() else None,
        created_by_id=admin.id,
    )
    db.add(promo)
    db.commit()
    return RedirectResponse(url="/admin/promotions", status_code=303)


@router.post("/promotions/{promo_id}/toggle")
async def admin_promotions_toggle(
    promo_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found.")

    if not promo.is_active:
        # Deactivate any other active promo for the same plan_key
        db.query(Promotion).filter(
            Promotion.plan_key == promo.plan_key,
            Promotion.is_active.is_(True),
            Promotion.id != promo.id,
        ).update({"is_active": False})
        promo.is_active = True
    else:
        promo.is_active = False
    db.commit()
    return RedirectResponse(url="/admin/promotions", status_code=303)


@router.post("/promotions/{promo_id}/delete")
async def admin_promotions_delete(
    promo_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if promo:
        db.delete(promo)
        db.commit()
    return RedirectResponse(url="/admin/promotions", status_code=303)
```

- [ ] **Step 2: Create the promotions admin template**

Create `frontend/templates/admin/promotions.html`:

```html
{% extends "admin/base.html" %}

{% block admin_content %}
<div class="space-y-6">
  <div>
    <h1 class="text-2xl font-display font-bold text-ink">Promotions</h1>
    <p class="mt-1 text-sm text-ink-dim">Create bonus credit offers tied to specific plans. Only one active promotion per plan.</p>
  </div>

  <!-- Create Form -->
  <form action="/admin/promotions" method="POST"
        class="rounded-xl border border-hairline bg-stage-raised p-5 space-y-4">
    <p class="text-[10px] font-bold uppercase tracking-widest text-cyan">New Promotion</p>
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div>
        <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">Plan</label>
        <select name="plan_key" required
                class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink focus:border-cyan focus:outline-none">
          {% for plan in plan_choices %}
          <option value="{{ plan.key }}">{{ plan.label }} ({{ plan.key }})</option>
          {% endfor %}
        </select>
      </div>
      <div>
        <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">Bonus Credits</label>
        <input type="number" name="bonus_credits" required min="1" placeholder="20"
               class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">
      </div>
      <div>
        <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">Headline</label>
        <input type="text" name="headline" required placeholder="Buy 50 credits, get 20 FREE!"
               class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">
      </div>
      <div class="sm:col-span-2 lg:col-span-1">
        <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">Description (optional)</label>
        <input type="text" name="description" placeholder="Limited time offer"
               class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink placeholder-ink-mute focus:border-cyan focus:outline-none">
      </div>
      <div>
        <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">Starts At (optional)</label>
        <input type="datetime-local" name="starts_at"
               class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink focus:border-cyan focus:outline-none">
      </div>
      <div>
        <label class="block text-[10px] font-bold uppercase tracking-widest text-ink-mute mb-1">Ends At (optional)</label>
        <input type="datetime-local" name="ends_at"
               class="w-full rounded-lg border border-hairline bg-stage px-3 py-2 text-sm text-ink focus:border-cyan focus:outline-none">
      </div>
    </div>
    <button type="submit" class="px-4 py-2 rounded-lg bg-cyan text-stage text-xs font-bold uppercase tracking-widest hover:bg-cyan/80 transition">
      Create Promotion
    </button>
  </form>

  <!-- Promotions List -->
  {% if promos %}
  <div class="space-y-3">
    {% for item in promos %}
    <div class="rounded-xl border border-hairline bg-stage-raised p-5 flex items-start justify-between gap-4">
      <div class="space-y-1 flex-1">
        <div class="flex items-center gap-2">
          <h3 class="text-base font-bold text-ink">{{ item.row.headline }}</h3>
          {% if item.status == 'active' %}
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest bg-success/15 text-success">Active</span>
          {% elif item.status == 'scheduled' %}
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest bg-cyan/15 text-cyan">Scheduled</span>
          {% elif item.status == 'expired' %}
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest bg-ink-mute/15 text-ink-mute">Expired</span>
          {% else %}
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest bg-amber/15 text-amber">Draft</span>
          {% endif %}
        </div>
        <p class="text-sm text-ink-dim">
          <span class="font-bold text-cyan">{{ item.row.plan_key }}</span> &mdash;
          +{{ item.row.bonus_credits }} bonus credits
        </p>
        {% if item.row.description %}
        <p class="text-xs text-ink-mute">{{ item.row.description }}</p>
        {% endif %}
        <p class="text-xs text-ink-mute">
          {% if item.row.starts_at %}From {{ item.row.starts_at.strftime('%Y-%m-%d %H:%M') }}{% endif %}
          {% if item.row.ends_at %}Until {{ item.row.ends_at.strftime('%Y-%m-%d %H:%M') }}{% endif %}
          {% if not item.row.starts_at and not item.row.ends_at %}No date limits{% endif %}
        </p>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <form action="/admin/promotions/{{ item.row.id }}/toggle" method="POST">
          <button type="submit"
                  class="px-3 py-1.5 rounded-lg border border-hairline text-xs font-bold uppercase tracking-widest
                         {% if item.row.is_active %}text-amber hover:text-amber{% else %}text-success hover:text-success{% endif %} transition">
            {% if item.row.is_active %}Deactivate{% else %}Activate{% endif %}
          </button>
        </form>
        <form action="/admin/promotions/{{ item.row.id }}/delete" method="POST"
              onsubmit="return confirm('Delete this promotion?')">
          <button type="submit" class="px-3 py-1.5 rounded-lg border border-hairline text-xs font-bold uppercase tracking-widest text-danger hover:text-danger transition">
            Delete
          </button>
        </form>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="rounded-xl border border-dashed border-hairline p-8 text-center text-sm text-ink-mute">
    No promotions yet. Create one above.
  </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Verify the promotions admin page loads**

Run: `docker-compose up --build -d && sleep 5`

Navigate to `/admin/promotions` — should show empty state with the create form.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/admin.py frontend/templates/admin/promotions.html
git commit -m "feat(admin): add promotions management page with CRUD"
```

---

### Task 6: Add promo bonus credits to payment webhook

**Files:**
- Modify: `backend/app/routes/payments.py` (update `_mark_checkout_session_paid` and `_handle_invoice_paid`)

- [ ] **Step 1: Add promo import and bonus logic to _mark_checkout_session_paid**

At the top of `payments.py`, add:

```python
from ..services.promotions import get_active_promotion
```

In the `_mark_checkout_session_paid` function, add promo bonus logic right before the `db.commit()` call (line 146). Insert after the `if is_subscription:` / `else:` block but before `db.commit()`:

```python
    # Check for active promotion and grant bonus credits
    active_promo = get_active_promotion(db, plan_key=payment_record.plan_key)
    if active_promo:
        user.credit_balance += active_promo.bonus_credits
        _activity(
            db,
            user.id,
            "promo_credits_granted",
            f"{active_promo.bonus_credits} bonus credits from promotion",
            {
                "promotion_id": active_promo.id,
                "promotion_headline": active_promo.headline,
                "plan_key": payment_record.plan_key,
                "bonus_credits": active_promo.bonus_credits,
                "credit_balance": user.credit_balance,
            },
        )
```

- [ ] **Step 2: Add promo bonus logic to _handle_invoice_paid**

In the `_handle_invoice_paid` function, add promo bonus logic after `user.credit_balance += credits_to_add` (line 180) and before the `db.add(PaymentRecord(...))` call:

```python
    # Check for active promotion and grant bonus credits
    active_promo = get_active_promotion(db, plan_key=plan_key)
    if active_promo:
        user.credit_balance += active_promo.bonus_credits
        _activity(
            db,
            user.id,
            "promo_credits_granted",
            f"{active_promo.bonus_credits} bonus credits from promotion",
            {
                "promotion_id": active_promo.id,
                "promotion_headline": active_promo.headline,
                "plan_key": plan_key,
                "bonus_credits": active_promo.bonus_credits,
                "credit_balance": user.credit_balance,
            },
        )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/payments.py
git commit -m "feat(payments): auto-grant promo bonus credits on purchase"
```

---

### Task 7: Add promo banner partial and display on home page

**Files:**
- Create: `frontend/templates/partials/promo_banner.html`
- Modify: `frontend/templates/home.html` (include promo banner + credit explainer)
- Modify: `backend/app/main.py` (pass active promo to home template)

- [ ] **Step 1: Create the promo banner partial**

Create `frontend/templates/partials/promo_banner.html`:

```html
{% if active_promo %}
<div id="promo-banner-{{ active_promo.id }}"
     data-promo-id="{{ active_promo.id }}"
     class="promo-banner relative overflow-hidden rounded-2xl border border-cyan/30 bg-gradient-to-r from-cyan/15 via-purple-500/10 to-cyan/15 px-6 py-5 mb-8">
  <div class="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
    <div>
      <p class="text-[10px] font-bold uppercase tracking-widest text-cyan mb-1">Limited Offer</p>
      <h3 class="text-lg sm:text-xl font-display font-extrabold text-ink">{{ active_promo.headline }}</h3>
      {% if active_promo.description %}
      <p class="mt-1 text-sm text-ink-dim">{{ active_promo.description }}</p>
      {% endif %}
    </div>
    <div class="flex items-center gap-3 shrink-0">
      <a href="#pricing" class="px-5 py-2.5 rounded-xl bg-cyan text-stage text-xs font-bold uppercase tracking-widest hover:bg-cyan/80 transition">
        Claim Offer
      </a>
      <button type="button"
              onclick="localStorage.setItem('dismissed_promo_id','{{ active_promo.id }}'); this.closest('.promo-banner').remove();"
              class="text-xs text-ink-mute opacity-60 hover:opacity-100 transition">dismiss</button>
    </div>
  </div>
</div>
<script>
(function() {
  var id = '{{ active_promo.id }}';
  if (localStorage.getItem('dismissed_promo_id') === id) {
    var el = document.getElementById('promo-banner-' + id);
    if (el) el.remove();
  }
})();
</script>
{% endif %}
```

- [ ] **Step 2: Update home page route to pass active promo**

In `backend/app/main.py`, add the import at the top:

```python
from .services.promotions import get_active_promotion
```

In the home route's template context (the block that renders `home.html` around line 103-113), add:

```python
"active_promo": get_active_promotion(db),
```

Note: The home route needs a `db` session — this was already added in Task 2, Step 2.

- [ ] **Step 3: Include promo banner and credit explainer on home page**

In `frontend/templates/home.html`, in the pricing section (after line 242, right after the closing `</div>` of the text-center heading block), add:

```html
        {% include "partials/promo_banner.html" %}

        <p class="text-center text-sm text-ink-dim mt-2 mb-6">
            Preview unlimited batches for free. 1 credit to export your renamed ZIP. Re-downloads are always free.
        </p>
```

- [ ] **Step 4: Verify the home page renders with credit explainer**

Run: `docker-compose up --build -d && sleep 5`

Navigate to `/` — should show the credit explainer text below the pricing heading. No promo banner yet (none created).

- [ ] **Step 5: Commit**

```bash
git add frontend/templates/partials/promo_banner.html frontend/templates/home.html backend/app/main.py
git commit -m "feat(ui): add promo banner partial and credit explainer to home page"
```

---

### Task 8: Add promo callout and credit clarity to app workspace

**Files:**
- Modify: `frontend/templates/app.html` (sidebar credit helper, promo callout, download credit indicator)
- Modify: `backend/app/main.py` (pass active promo to app template)

- [ ] **Step 1: Pass active promo to app template**

In `backend/app/main.py`, in the workspace route's template context (around line 124-147), add after the `"announcement"` line:

```python
"active_promo": get_active_promotion(db),
```

The `get_active_promotion` import was already added in Task 7.

- [ ] **Step 2: Add credit helper text to sidebar**

In `frontend/templates/app.html`, find the sidebar credit display (around line 76):

```html
<span class="text-xs font-bold text-cyan">Credits: <span id="account-sidebar-credits">0</span></span>
```

Add immediately after this line:

```html
                            <span class="text-[10px] text-ink-mute block mt-0.5">1 credit = 1 export</span>
```

- [ ] **Step 3: Add promo callout in the workspace billing area**

In `frontend/templates/app.html`, find the subscription status section (around line 358, after the `</div>` closing `subscription-status-section`). Add after it:

```html
                                    {% if active_promo %}
                                    <div id="app-promo-callout" class="rounded-xl border border-cyan/30 bg-gradient-to-r from-cyan/10 to-purple-500/5 p-4">
                                        <p class="text-[10px] font-bold uppercase tracking-widest text-cyan mb-1">Promotion</p>
                                        <p class="text-sm font-bold text-ink">{{ active_promo.headline }}</p>
                                        {% if active_promo.description %}
                                        <p class="mt-1 text-xs text-ink-dim">{{ active_promo.description }}</p>
                                        {% endif %}
                                        <button onclick="openBilling()" class="mt-3 px-4 py-2 rounded-lg bg-cyan text-stage text-[10px] font-bold uppercase tracking-widest hover:bg-cyan/80 transition">
                                            Get It Now
                                        </button>
                                    </div>
                                    {% endif %}
```

- [ ] **Step 4: Add credit cost indicator to download step**

In `frontend/templates/app.html`, find the download link (around line 291):

```html
<a id="download-link" href="#" class="mt-8 flex w-full items-center justify-center gap-2 rounded-xl bg-stage-raised py-4 text-sm font-bold text-cyan transition hover:bg-stage-raised-dim">
    <span class="material-symbols-outlined text-sm">download</span>
    DOWNLOAD ARCHIVE
</a>
```

Add immediately after this `</a>` tag:

```html
                                    <div id="credit-cost-indicator" class="mt-3 text-center text-xs font-medium">
                                        <span id="credit-cost-first" class="hidden text-amber">
                                            <span class="material-symbols-outlined text-xs align-middle">toll</span>
                                            This will use 1 credit
                                        </span>
                                        <span id="credit-cost-free" class="hidden text-success">
                                            <span class="material-symbols-outlined text-xs align-middle">check_circle</span>
                                            Free re-download
                                        </span>
                                        <span id="credit-cost-none" class="hidden text-danger">
                                            <span class="material-symbols-outlined text-xs align-middle">error</span>
                                            You need 1 credit to export &mdash;
                                            <button onclick="openBilling()" class="underline text-cyan">Buy credits</button>
                                        </span>
                                    </div>
```

- [ ] **Step 5: Add JavaScript logic to show/hide credit cost indicator**

In the JavaScript section of `app.html`, find the `updateUI` function or the section that handles step 3 visibility. Look for where `downloadLink.href` is set (around line 1317). Add this function and call it when step 3 becomes visible:

Find the section where the download URL is set (around line 1313-1317) and add after it:

```javascript
            updateCreditIndicator();
```

Then add this function in the script section (after the `downloadArchive` function around line 1363):

```javascript
        function updateCreditIndicator() {
            const first = document.getElementById("credit-cost-first");
            const free = document.getElementById("credit-cost-free");
            const none = document.getElementById("credit-cost-none");
            if (!first || !free || !none) return;

            first.classList.add("hidden");
            free.classList.add("hidden");
            none.classList.add("hidden");

            // Check if this is a re-download (collection already downloaded)
            if (state.downloadCount && state.downloadCount > 0) {
                free.classList.remove("hidden");
            } else if (state.user && state.user.credit_balance > 0) {
                first.classList.remove("hidden");
            } else if (state.user && state.user.is_testing) {
                free.classList.remove("hidden");
            } else {
                none.classList.remove("hidden");
            }
        }
```

Also, ensure `state.downloadCount` is tracked. In the state initialization section (around line 486), find or add:

```javascript
downloadCount: 0,
```

And in the preview response handler (around line 1313 where `state.downloadUrl` is set), also capture the download count from the collection data if available. Since the preview endpoint doesn't return download count, default to 0 for new previews:

```javascript
state.downloadCount = 0;
```

After a successful download (in the `downloadArchive` function, after the "Archive downloaded" status), add:

```javascript
            state.downloadCount = (state.downloadCount || 0) + 1;
            updateCreditIndicator();
```

- [ ] **Step 6: Verify the app workspace shows credit helper and indicator**

Run: `docker-compose up --build -d && sleep 5`

Navigate to `/app` — sidebar should show "1 credit = 1 export" under the credit balance. Step 3 should show the credit cost indicator.

- [ ] **Step 7: Commit**

```bash
git add frontend/templates/app.html backend/app/main.py
git commit -m "feat(ui): add promo callout, credit helper text, and download cost indicator to app"
```

---

### Task 9: Final integration verification

**Files:** None (verification only)

- [ ] **Step 1: Verify admin pricing page**

Navigate to `/admin/pricing`. Edit one plan's label and save. Verify the home page reflects the change.

- [ ] **Step 2: Verify admin promotions page**

Navigate to `/admin/promotions`. Create a promotion for `label_pack` with 20 bonus credits and headline "Buy 50 credits, get 20 FREE!". Activate it. Verify the promo banner appears on the home page and in the app workspace.

- [ ] **Step 3: Verify credit clarity**

Check that:
- Home page shows "Preview unlimited batches for free. 1 credit to export your renamed ZIP. Re-downloads are always free."
- App sidebar shows "1 credit = 1 export" under the credit balance
- Step 3 export area shows the credit cost indicator

- [ ] **Step 4: Commit any final fixes**

If any issues found, fix and commit with descriptive message.
