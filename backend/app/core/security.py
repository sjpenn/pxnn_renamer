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
