from typing import Optional
import json
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.pricing import get_payment_options, get_payment_plan
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

    return {
        "price_data": {
            "currency": "usd",
            "unit_amount": plan["amount_cents"],
            "product_data": {
                "name": plan["label"],
                "description": plan["description"],
            },
        },
        "quantity": 1,
    }


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

    if checkout_session.get("payment_status") != "paid":
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
    db.commit()
    return payment_record


@router.get("/api/payments/options")
async def payment_options():
    return {"payment_options": get_payment_options()}


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
    checkout_session = stripe.checkout.Session.create(
        mode="payment",
        customer=customer.id,
        line_items=[_line_item_for_plan(plan)],
        success_url=f"{app_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{app_url}/?billing=cancelled",
        allow_promotion_codes=True,
        metadata={
            "user_id": str(current_user.id),
            "plan_key": plan["key"],
            "credits": str(plan["credits"]),
        },
    )

    db.add(
        PaymentRecord(
            user_id=current_user.id,
            stripe_checkout_session_id=checkout_session.id,
            stripe_customer_id=customer.id,
            stripe_price_id=plan.get("stripe_price_id") or plan["key"],
            plan_key=plan["key"],
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
        {"plan_key": plan["key"], "credits": plan["credits"]},
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


@router.post("/api/payments/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    _configure_stripe()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured.")

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
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

    if event["type"] == "checkout.session.completed":
        _mark_checkout_session_paid(db, event["data"]["object"]["id"])

    return {"received": True}
