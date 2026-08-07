"""Coupon code creation and redemption logic."""

import json
import secrets
import string
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..database.models import ActivityLog, CouponCode, CouponRedemption, User

CODE_ALPHABET = string.ascii_uppercase + string.digits


class CouponError(Exception):
    """Raised when a coupon cannot be redeemed. Message is user-safe."""


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.strip().upper() if ch.isalnum() or ch == "-")


def generate_code(prefix: str = "PXNN") -> str:
    suffix = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    return f"{prefix}-{suffix}"


def create_coupon(
    db: Session,
    *,
    credits: int,
    code: Optional[str] = None,
    max_redemptions: Optional[int] = None,
    expires_at: Optional[datetime] = None,
    note: Optional[str] = None,
    created_by_id: Optional[int] = None,
) -> CouponCode:
    if credits <= 0:
        raise CouponError("Credits must be positive.")

    normalized = normalize_code(code) if code else generate_code()
    if len(normalized) < 4:
        raise CouponError("Code must be at least 4 characters.")

    existing = db.query(CouponCode).filter(CouponCode.code == normalized).first()
    if existing:
        raise CouponError("That code already exists.")

    coupon = CouponCode(
        code=normalized,
        credits=credits,
        max_redemptions=max_redemptions if max_redemptions and max_redemptions > 0 else None,
        expires_at=expires_at,
        note=(note or "").strip() or None,
        created_by_id=created_by_id,
    )
    db.add(coupon)
    db.flush()
    return coupon


def redeem_coupon(db: Session, user: User, raw_code: str) -> CouponCode:
    """Validate and redeem a coupon for a user. Grants credits and logs activity."""
    normalized = normalize_code(raw_code)
    if not normalized:
        raise CouponError("Enter a coupon code.")

    coupon = db.query(CouponCode).filter(CouponCode.code == normalized).first()
    if not coupon or not coupon.is_active:
        raise CouponError("That code is not valid.")
    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        raise CouponError("That code has expired.")
    if coupon.max_redemptions is not None and coupon.redeemed_count >= coupon.max_redemptions:
        raise CouponError("That code has reached its redemption limit.")

    already = (
        db.query(CouponRedemption)
        .filter(
            CouponRedemption.coupon_id == coupon.id,
            CouponRedemption.user_id == user.id,
        )
        .first()
    )
    if already:
        raise CouponError("You've already redeemed this code.")

    db.add(
        CouponRedemption(
            coupon_id=coupon.id,
            user_id=user.id,
            credits_granted=coupon.credits,
        )
    )
    coupon.redeemed_count += 1
    user.credit_balance += coupon.credits
    db.add(
        ActivityLog(
            user_id=user.id,
            event_type="coupon_redeemed",
            summary=f"Redeemed code {coupon.code} for {coupon.credits} credits",
            details_json=json.dumps(
                {
                    "code": coupon.code,
                    "credits": coupon.credits,
                    "new_balance": user.credit_balance,
                }
            ),
        )
    )
    db.commit()
    return coupon
