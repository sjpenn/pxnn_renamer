from typing import Optional
import json
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..services.promotions import get_active_promotion
from ..core.pricing import get_payment_options, get_payment_plan, PAYMENT_PLANS
from ..core.security import get_current_user
from ..database.models import ActivityLog, PaymentRecord, User
from ..database.session import get_db

router = APIRouter(tags=["payments"])

STRIPE_API_VERSION = "2026-02-25.clover"


def _configure_stripe() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Payments are not configured yet. Add your Stripe keys to enable checkout.",
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = STRIPE_API_VERSION


def _get_or_create_customer(db: Session, user: User):
    _configure_stripe()

    if user.stripe_customer_id:
        return stripe.Customer.retrieve(user.stripe_customer_id)

    customer = stripe.Customer.create(
        name=user.username,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer


def _line_item_for_plan(plan: dict) -> dict:
    if plan.get("stripe_price_id"):
        return {"price": plan["stripe_price_id"], "quantity": 1}

    price_data = {
        "currency": "usd",
        "unit_amount": plan["amount_cents"],
        "product_data": {
            "name": plan["label"],
            "description": plan["description"],
        },
    }

    if plan.get("plan_type") == "subscription":
        price_data["recurring"] = {"interval": "month"}

    return {"price_data": price_data, "quantity": 1}


def _activity(db: Session, user_id: int, event_type: str, summary: str, details: Optional[dict] = None) -> None:
    db.add(
        ActivityLog(
            user_id=user_id,
            event_type=event_type,
            summary=summary,
            details_json=json.dumps(details or {}),
        )
    )


def _mark_checkout_session_paid(
    db: Session,
    checkout_session_id: str,
    expected_user_id: Optional[int] = None,
) -> PaymentRecord:
    _configure_stripe()
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)

    if checkout_session.get("payment_status") not in ("paid", "no_payment_required"):
        raise HTTPException(status_code=400, detail="This checkout session is not paid yet.")

    payment_record = (
        db.query(PaymentRecord)
        .filter(PaymentRecord.stripe_checkout_session_id == checkout_session_id)
        .first()
    )
    if not payment_record:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    if expected_user_id and payment_record.user_id != expected_user_id:
        raise HTTPException(status_code=403, detail="That payment does not belong to you.")

    if payment_record.status == "paid":
        return payment_record

    user = db.query(User).filter(User.id == payment_record.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found for payment.")

    payment_record.status = "paid"
    payment_record.completed_at = datetime.utcnow()
    payment_record.amount_cents = checkout_session.get("amount_total") or payment_record.amount_cents
    payment_record.currency = checkout_session.get("currency") or payment_record.currency

    is_subscription = payment_record.plan_type == "subscription"

    if is_subscription:
        sub_id = checkout_session.get("subscription")
        user.subscription_id = sub_id
        user.subscription_status = "active"
        user.subscription_plan = payment_record.plan_key
        user.active_plan = payment_record.plan_key
        user.plan_status = "active"
        _activity(
            db,
            user.id,
            "subscription_started",
            f"Subscription started: {payment_record.plan_key}",
            {
                "plan_key": payment_record.plan_key,
                "subscription_id": sub_id,
            },
        )
    else:
        user.credit_balance += payment_record.credits
        user.active_plan = payment_record.plan_key
        user.plan_status = "active"
        _activity(
            db,
            user.id,
            "payment_completed",
            f"{payment_record.credits} credits added",
            {
                "plan_key": payment_record.plan_key,
                "checkout_session_id": checkout_session_id,
                "credit_balance": user.credit_balance,
            },
        )

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

    db.commit()
    return payment_record


def _handle_invoice_paid(db: Session, invoice: dict) -> None:
    customer_id = invoice.get("customer")
    invoice_id = invoice.get("id")
    subscription_id = invoice.get("subscription")

    if not customer_id or not subscription_id or not invoice_id:
        return

    # Idempotency: skip if this invoice was already processed
    existing = db.query(PaymentRecord).filter(PaymentRecord.stripe_invoice_id == invoice_id).first()
    if existing:
        return

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    # Get plan_key from subscription metadata
    try:
        _configure_stripe()
        sub = stripe.Subscription.retrieve(subscription_id)
        plan_key = (sub.get("metadata") or {}).get("plan_key") or user.subscription_plan
    except Exception:
        plan_key = user.subscription_plan

    if not plan_key or plan_key not in PAYMENT_PLANS:
        return

    plan = PAYMENT_PLANS[plan_key]
    credits_to_add = plan["credits"]
    user.credit_balance += credits_to_add

    # Note: promo bonuses are NOT granted on recurring invoices — only on initial checkout
    # via _mark_checkout_session_paid. This prevents unlimited bonus credits each month.

    db.add(
        PaymentRecord(
            user_id=user.id,
            stripe_invoice_id=invoice_id,
            stripe_customer_id=customer_id,
            plan_key=plan_key,
            plan_type="subscription",
            amount_cents=invoice.get("amount_paid", 0),
            currency=invoice.get("currency", "usd"),
            credits=credits_to_add,
            status="paid",
            completed_at=datetime.utcnow(),
        )
    )
    _activity(
        db,
        user.id,
        "subscription_credits_granted",
        f"{credits_to_add} credits granted for {plan_key}",
        {
            "plan_key": plan_key,
            "invoice_id": invoice_id,
            "credit_balance": user.credit_balance,
        },
    )
    db.commit()


def _handle_subscription_deleted(db: Session, subscription: dict) -> None:
    sub_id = subscription.get("id")
    customer_id = subscription.get("customer")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    # Only clear if this deletion event is for the user's current subscription
    if user.subscription_id and user.subscription_id != sub_id:
        return

    user.subscription_status = "canceled"
    user.subscription_id = None
    user.subscription_plan = None
    user.active_plan = "free"
    user.plan_status = "inactive"

    _activity(db, user.id, "subscription_cancelled", "Subscription cancelled", {"subscription_id": sub_id})
    db.commit()


def _handle_subscription_updated(db: Session, subscription: dict) -> None:
    customer_id = subscription.get("customer")
    new_status = subscription.get("status")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    user.subscription_status = new_status
    db.commit()


@router.get("/api/payments/options")
async def payment_options(db: Session = Depends(get_db)):
    return {"payment_options": get_payment_options(db)}


@router.post("/api/payments/checkout")
async def create_checkout_session(
    request: Request,
    plan_key: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _configure_stripe()

    try:
        plan = get_payment_plan(plan_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown payment option.") from exc

    customer = _get_or_create_customer(db, current_user)
    app_url = settings.APP_URL.rstrip("/")
    is_subscription = plan.get("plan_type") == "subscription"
    mode = "subscription" if is_subscription else "payment"

    checkout_kwargs = {
        "mode": mode,
        "customer": customer.id,
        "line_items": [_line_item_for_plan(plan)],
        "success_url": f"{app_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{app_url}/?billing=cancelled",
        "allow_promotion_codes": True,
        "metadata": {
            "user_id": str(current_user.id),
            "plan_key": plan["key"],
            "credits": str(plan["credits"]),
        },
    }

    if is_subscription:
        checkout_kwargs["subscription_data"] = {
            "metadata": {
                "plan_key": plan["key"],
                "user_id": str(current_user.id),
            }
        }

    checkout_session = stripe.checkout.Session.create(**checkout_kwargs)

    db.add(
        PaymentRecord(
            user_id=current_user.id,
            stripe_checkout_session_id=checkout_session.id,
            stripe_customer_id=customer.id,
            stripe_price_id=plan.get("stripe_price_id") or plan["key"],
            plan_key=plan["key"],
            plan_type=plan.get("plan_type", "one_time"),
            amount_cents=plan["amount_cents"],
            currency="usd",
            credits=plan["credits"],
            status="pending",
        )
    )
    _activity(
        db,
        current_user.id,
        "payment_started",
        f"Checkout started for {plan['label']}",
        {"plan_key": plan["key"], "credits": plan["credits"], "mode": mode},
    )
    db.commit()

    return {"checkout_url": checkout_session.url}


@router.get("/billing/success")
async def billing_success(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _mark_checkout_session_paid(db, session_id, expected_user_id=current_user.id)
    return RedirectResponse(url="/?billing=success", status_code=303)


@router.post("/api/payments/subscription/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _configure_stripe()

    if not current_user.subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription found.")

    if current_user.subscription_status != "active":
        raise HTTPException(status_code=400, detail="Subscription is not active.")

    stripe.Subscription.delete(current_user.subscription_id)
    # Status will be updated by webhook; set optimistically
    current_user.subscription_status = "canceled"
    current_user.active_plan = "free"
    current_user.plan_status = "inactive"
    _activity(db, current_user.id, "subscription_cancelled", "Subscription cancelled by user")
    db.commit()

    return {"ok": True}


@router.post("/api/payments/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    stripe.api_key = settings.STRIPE_SECRET_KEY or "sk_test_placeholder"
    stripe.api_version = STRIPE_API_VERSION

    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if settings.STRIPE_WEBHOOK_SECRET:
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature.")
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Stripe payload.") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.") from exc
    else:
        # No webhook secret configured — only safe in test/dev environments
        try:
            event = json.loads(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid payload.") from exc

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        _mark_checkout_session_paid(db, event["data"]["object"]["id"])

    elif event_type == "invoice.paid":
        _handle_invoice_paid(db, event["data"]["object"])

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db, event["data"]["object"])

    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(db, event["data"]["object"])

    return {"received": True}
