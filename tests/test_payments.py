import json
from unittest.mock import MagicMock, patch

import pytest

from backend.app.database.models import PaymentRecord, User
from backend.app.core.security import hash_password


def _create_user(db, username="testuser", credits=0, stripe_customer_id="cus_test"):
    user = User(
        username=username,
        password_hash=hash_password("password123"),
        credit_balance=credits,
        stripe_customer_id=stripe_customer_id,
    )
    db.add(user)
    db.commit()
    return user


def test_invoice_paid_webhook_grants_subscription_credits(client, db):
    user = _create_user(db, credits=0, stripe_customer_id="cus_inv")
    user.subscription_plan = "pro_monthly"
    user.subscription_id = "sub_test"
    db.commit()

    mock_sub = MagicMock()
    mock_sub.get.return_value = {"plan_key": "pro_monthly", "user_id": str(user.id)}

    event_payload = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "inv_001",
                "customer": "cus_inv",
                "subscription": "sub_test",
                "amount_paid": 2900,
                "currency": "usd",
            }
        },
    }

    with patch("backend.app.routes.payments.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.return_value = event_payload
        mock_stripe.Subscription.retrieve.return_value = mock_sub

        response = client.post(
            "/api/payments/webhook",
            content=json.dumps(event_payload),
            headers={"stripe-signature": "test_sig", "content-type": "application/json"},
        )

    assert response.status_code == 200
    db.refresh(user)
    assert user.credit_balance == 15  # pro_monthly grants 15 credits


def test_invoice_paid_webhook_idempotent(client, db):
    """Second call with same invoice_id must not double-grant credits."""
    user = _create_user(db, credits=15, stripe_customer_id="cus_idem")
    user.subscription_plan = "pro_monthly"
    user.subscription_id = "sub_idem"
    db.commit()

    # Pre-create the payment record as if already processed
    db.add(PaymentRecord(
        user_id=user.id,
        stripe_invoice_id="inv_idem",
        plan_key="pro_monthly",
        plan_type="subscription",
        amount_cents=2900,
        currency="usd",
        credits=15,
        status="paid",
    ))
    db.commit()

    mock_sub = MagicMock()
    mock_sub.get.return_value = {"plan_key": "pro_monthly"}

    event_payload = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "inv_idem",
                "customer": "cus_idem",
                "subscription": "sub_idem",
                "amount_paid": 2900,
                "currency": "usd",
            }
        },
    }

    with patch("backend.app.routes.payments.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.return_value = event_payload
        mock_stripe.Subscription.retrieve.return_value = mock_sub

        response = client.post(
            "/api/payments/webhook",
            content=json.dumps(event_payload),
            headers={"stripe-signature": "test_sig", "content-type": "application/json"},
        )

    assert response.status_code == 200
    db.refresh(user)
    assert user.credit_balance == 15  # unchanged


def test_subscription_cancelled_webhook_clears_plan(client, db):
    user = _create_user(db, stripe_customer_id="cus_cancel")
    user.subscription_id = "sub_cancel"
    user.subscription_status = "active"
    user.subscription_plan = "starter_monthly"
    user.active_plan = "starter_monthly"
    db.commit()

    event_payload = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_cancel",
                "customer": "cus_cancel",
                "status": "canceled",
            }
        },
    }

    with patch("backend.app.routes.payments.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.return_value = event_payload

        response = client.post(
            "/api/payments/webhook",
            content=json.dumps(event_payload),
            headers={"stripe-signature": "test_sig", "content-type": "application/json"},
        )

    assert response.status_code == 200
    db.refresh(user)
    assert user.subscription_status == "canceled"
    assert user.active_plan == "free"
