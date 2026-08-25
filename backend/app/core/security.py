from typing import Optional, Union
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..database.models import User
from ..database.session import get_db
from .config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def create_password_reset_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES)
    payload = {
        "sub": str(user_id),
        "purpose": "password_reset",
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def verify_password_reset_token(token: str) -> Optional[int]:
    """Return the user id for a valid password-reset token, else None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != "password_reset":
        return None
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError):
        return None


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.APP_URL.startswith("https://"),
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(settings.COOKIE_NAME)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not user.password_hash:
        # Google-only account — cannot sign in with password
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def has_unlimited_access(user) -> bool:
    """Return True if the user should bypass all paywalls / credit gates.

    Triggered by either:
      * the per-user is_testing flag (admin-assigned testers), or
      * an active subscription on a plan marked ``unlimited`` (the
        $7.99/mo Monthly Unlimited plan).

    Any future feature gate should call this helper rather than re-checking
    flags directly.
    """
    if user is None:
        return False

    if bool(getattr(user, "is_testing", False)):
        return True

    # Active subscribers on an unlimited monthly plan bypass the credit paywall.
    if getattr(user, "subscription_status", None) == "active":
        plan_key = getattr(user, "subscription_plan", None)
        if plan_key:
            from .pricing import PAYMENT_PLANS

            plan = PAYMENT_PLANS.get(plan_key)
            if plan and plan.get("unlimited"):
                return True

    return False


def serialize_user(user: Optional[User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "credit_balance": user.credit_balance,
        "active_plan": user.active_plan,
        "plan_status": user.plan_status,
        "subscription_status": user.subscription_status,
        "subscription_plan": user.subscription_plan,
        "is_testing": bool(getattr(user, "is_testing", False)),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        resolved_user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    return db.query(User).filter(User.id == resolved_user_id).first()


def get_current_user(
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    if current_user:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in to continue.",
    )


def set_pending_plan(request: Request, plan_key: str) -> None:
    """Store a plan key in the session for post-registration checkout redirect."""
    request.session["pending_plan"] = plan_key


def pop_pending_plan(request: Request) -> Optional[str]:
    """Retrieve and clear the pending plan from the session."""
    return request.session.pop("pending_plan", None)


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the authenticated user to have is_admin=True."""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user
