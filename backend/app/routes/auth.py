import json
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.rate_limit import check_rate_limit
from ..core.security import (
    authenticate_user,
    clear_auth_cookie,
    create_access_token,
    create_password_reset_token,
    get_current_user_optional,
    hash_password,
    serialize_user,
    set_auth_cookie,
    verify_password_reset_token,
)
from ..database.models import ActivityLog, User
from ..database.session import get_db
from ..services.audit import record_audit
from ..services.email_service import notify_new_signup, send_password_reset
from ..services.site_settings import get_setting

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _log_auth_activity(db: Session, user: User, event_type: str, summary: str) -> None:
    db.add(
        ActivityLog(
            user_id=user.id,
            event_type=event_type,
            summary=summary,
            details_json=json.dumps({"username": user.username}),
        )
    )


@router.post("/register")
async def register(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(""),
    db: Session = Depends(get_db),
):
    check_rate_limit(request, "register", settings.RATE_LIMIT_REGISTER_PER_WINDOW)
    normalized_username = username.strip().lower()
    normalized_email = email.strip().lower()
    if normalized_email and not EMAIL_RE.match(normalized_email):
        raise HTTPException(status_code=400, detail="That email address doesn't look valid.")
    if len(normalized_username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    existing_user = db.query(User).filter(User.username == normalized_username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="That username is already taken.")

    user = User(
        username=normalized_username,
        password_hash=hash_password(password),
        email=normalized_email or None,
    )
    db.add(user)
    db.flush()
    _log_auth_activity(db, user, "account_created", "Account created")

    # Grant trial credits
    trial_credits = int(get_setting(db, "trial_credits", "5"))
    if trial_credits > 0:
        user.credit_balance = trial_credits
        _log_auth_activity(db, user, "trial_credits_granted", f"{trial_credits} trial credits granted")

    record_audit(
        db,
        action="auth.register",
        category="auth",
        summary=f"Account created: {user.username}",
        actor=user,
        target=user,
        entity_type="user",
        entity_id=user.id,
        meta={"email": user.email, "trial_credits": trial_credits, "method": "form"},
        request=request,
    )
    db.commit()

    notify_new_signup(db, user, method="form")

    token = create_access_token(str(user.id))
    set_auth_cookie(response, token)
    return {"user": serialize_user(user)}


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    check_rate_limit(request, "login", settings.RATE_LIMIT_LOGIN_PER_WINDOW)
    user = authenticate_user(db, username.strip().lower(), password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    _log_auth_activity(db, user, "login", "Signed in")
    record_audit(
        db,
        action="auth.login",
        category="auth",
        summary=f"Signed in: {user.username}",
        actor=user,
        entity_type="user",
        entity_id=user.id,
        request=request,
    )
    db.commit()

    token = create_access_token(str(user.id))
    set_auth_cookie(response, token)
    return {"user": serialize_user(user)}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if current_user is not None:
        record_audit(
            db,
            action="auth.logout",
            category="auth",
            summary=f"Signed out: {current_user.username}",
            actor=current_user,
            entity_type="user",
            entity_id=current_user.id,
            request=request,
        )
        db.commit()
    clear_auth_cookie(response)
    return {"ok": True}


@router.post("/forgot")
async def forgot_password(
    request: Request,
    identifier: str = Form(...),
    db: Session = Depends(get_db),
):
    """Start a password reset. Always returns ok to avoid account enumeration."""
    check_rate_limit(request, "forgot", settings.RATE_LIMIT_FORGOT_PER_WINDOW)
    lookup = identifier.strip().lower()
    if not lookup:
        raise HTTPException(status_code=400, detail="Enter your username or email.")

    user = (
        db.query(User)
        .filter((User.username == lookup) | (User.email == lookup))
        .first()
    )
    if user and user.email and user.password_hash:
        token = create_password_reset_token(user.id)
        reset_url = f"{settings.APP_URL.rstrip('/')}/reset?token={token}"
        sent = send_password_reset(user, reset_url)
        if sent:
            _log_auth_activity(db, user, "password_reset_requested", "Password reset email sent")
            record_audit(
                db,
                action="auth.password_reset_requested",
                category="security",
                summary=f"Password reset requested: {user.username}",
                actor=user,
                target=user,
                entity_type="user",
                entity_id=user.id,
                request=request,
            )
            db.commit()

    return {"ok": True, "detail": "If that account has an email on file, a reset link is on its way."}


@router.post("/reset")
async def reset_password(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    check_rate_limit(request, "forgot", settings.RATE_LIMIT_FORGOT_PER_WINDOW)
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    user_id = verify_password_reset_token(token)
    if user_id is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user.password_hash = hash_password(new_password)
    _log_auth_activity(db, user, "password_reset_completed", "Password reset via email link")
    record_audit(
        db,
        action="auth.password_reset_completed",
        category="security",
        summary=f"Password reset completed: {user.username}",
        actor=user,
        target=user,
        entity_type="user",
        entity_id=user.id,
        request=request,
    )
    db.commit()
    return {"ok": True}
