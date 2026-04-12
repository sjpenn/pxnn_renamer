from typing import Optional

from sqlalchemy.orm import Session

from .config import settings

PAYMENT_PLANS = {
    "single_export": {
        "label": "Single Export",
        "description": "1 download credit for a finished rename batch.",
        "amount_cents": 700,
        "credits": 1,
        "price_id_setting": "STRIPE_SINGLE_EXPORT_PRICE_ID",
        "accent": "Starter",
        "plan_type": "one_time",
    },
    "creator_pack": {
        "label": "Creator Pack",
        "description": "10 download credits for repeat uploads and revisions.",
        "amount_cents": 3900,
        "credits": 10,
        "price_id_setting": "STRIPE_CREATOR_PACK_PRICE_ID",
        "accent": "Best value",
        "plan_type": "one_time",
    },
    "label_pack": {
        "label": "Label Pack",
        "description": "50 download credits for teams and heavier release schedules.",
        "amount_cents": 14900,
        "credits": 50,
        "price_id_setting": "STRIPE_LABEL_PACK_PRICE_ID",
        "accent": "Team",
        "plan_type": "one_time",
    },
    "starter_monthly": {
        "label": "Starter",
        "description": "3 credits/month for independent producers.",
        "amount_cents": 900,
        "credits": 3,
        "price_id_setting": "STRIPE_STARTER_MONTHLY_PRICE_ID",
        "accent": "Monthly",
        "plan_type": "subscription",
    },
    "pro_monthly": {
        "label": "Pro",
        "description": "15 credits/month for regular uploaders.",
        "amount_cents": 2900,
        "credits": 15,
        "price_id_setting": "STRIPE_PRO_MONTHLY_PRICE_ID",
        "accent": "Popular",
        "plan_type": "subscription",
    },
    "label_monthly": {
        "label": "Label",
        "description": "60 credits/month for teams and heavy release schedules.",
        "amount_cents": 7900,
        "credits": 60,
        "price_id_setting": "STRIPE_LABEL_MONTHLY_PRICE_ID",
        "accent": "Team",
        "plan_type": "subscription",
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
