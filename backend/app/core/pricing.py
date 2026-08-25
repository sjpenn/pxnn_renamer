from typing import Optional

from sqlalchemy.orm import Session

from .config import settings

# Two-option pricing: pay-per-single ($1 per export) vs. unlimited monthly ($7.99/mo).
# The monthly plan carries `unlimited: True`; active subscribers bypass the credit
# paywall via core.security.has_unlimited_access rather than accumulating credits.
PAYMENT_PLANS = {
    "single_export": {
        "label": "Pay Per Single",
        "description": "One export credit \u2014 $1 per turn. Perfect for a single finished batch.",
        "amount_cents": 100,
        "credits": 1,
        "price_id_setting": "STRIPE_SINGLE_EXPORT_PRICE_ID",
        "accent": "Pay as you go",
        "plan_type": "one_time",
        "unlimited": False,
    },
    "monthly_unlimited": {
        "label": "Monthly Unlimited",
        "description": "Unlimited exports every month for one flat price. Cancel anytime.",
        "amount_cents": 799,
        "credits": 0,
        "price_id_setting": "STRIPE_MONTHLY_UNLIMITED_PRICE_ID",
        "accent": "Best value",
        "plan_type": "subscription",
        "unlimited": True,
    },
}


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
                "unlimited": plan.get("unlimited", False),
                "sort_order": sort_order,
            }
        )
    options.sort(key=lambda o: o["sort_order"])
    return options


def get_payment_plan(plan_key: str) -> dict:
    if plan_key not in PAYMENT_PLANS:
        raise KeyError(plan_key)

    plan = PAYMENT_PLANS[plan_key]
    return {
        **plan,
        "key": plan_key,
        "amount_label": _format_amount(plan["amount_cents"]),
        "stripe_price_id": getattr(settings, plan["price_id_setting"]),
    }
