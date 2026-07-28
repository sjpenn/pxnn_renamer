import json
import re

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.requests import Request

from ..core.config import settings
from ..core.security import create_access_token, set_auth_cookie
from ..database.models import ActivityLog, User
from ..database.session import get_db
from ..services.email_service import notify_new_signup
from ..services.site_settings import get_setting

router = APIRouter(tags=["oauth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def _resolve_or_create_google_user(
    db: Session, google_sub: str, email: str, email_verified: bool = False
) -> tuple[User, bool]:
    """Find existing user by google_sub, link by email (only if Google reports the
    email as verified — prevents account takeover via unverified addresses), or
    create a new user. Returns (user, is_new) tuple."""
    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user:
        return user, False

    if email and email_verified:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_sub = google_sub
            db.commit()
            return user, False

    # Derive a unique username from email
    name_hint = email.split("@")[0][:20] if email else "user"
    base_username = re.sub(r"[^a-z0-9]", "_", name_hint.lower()).strip("_")[:20] or "user"
    username = base_username
    suffix = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}_{suffix}"
        suffix += 1

    user = User(
        username=username,
        email=email,
        google_sub=google_sub,
        password_hash=None,
    )
    db.add(user)
    db.flush()
    db.add(
        ActivityLog(
            user_id=user.id,
            event_type="account_created",
            summary="Account created via Google",
            details_json=json.dumps({"method": "google", "email": email}),
        )
    )

    # Grant trial credits
    trial_credits = int(get_setting(db, "trial_credits", "5"))
    if trial_credits > 0:
        user.credit_balance = trial_credits
        db.add(
            ActivityLog(
                user_id=user.id,
                event_type="trial_credits_granted",
                summary=f"{trial_credits} trial credits granted",
                details_json=json.dumps({"trial_credits": trial_credits}),
            )
        )

    db.commit()
    return user, True


@router.get("/auth/google/login")
async def google_login(request: Request):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    redirect_uri = settings.GOOGLE_REDIRECT_URI.strip()
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Google OAuth failed. Please try again.") from exc

    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(status_code=400, detail="No user info returned from Google.")

    google_sub = userinfo["sub"]
    email = userinfo.get("email", "")
    email_verified = bool(userinfo.get("email_verified", False))

    user, is_new = _resolve_or_create_google_user(
        db, google_sub=google_sub, email=email, email_verified=email_verified
    )

    if is_new:
        notify_new_signup(db, user, method="google")

    jwt_token = create_access_token(str(user.id))
    response = RedirectResponse(url="/app", status_code=303)
    set_auth_cookie(response, jwt_token)
    return response
