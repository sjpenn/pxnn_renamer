import json

from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..core.security import (
    authenticate_user,
    clear_auth_cookie,
    create_access_token,
    hash_password,
    serialize_user,
    set_auth_cookie,
)
from ..database.models import ActivityLog, User
from ..database.session import get_db

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
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_username = username.strip().lower()
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
    )
    db.add(user)
    db.flush()
    _log_auth_activity(db, user, "account_created", "Account created")
    db.commit()

    token = create_access_token(str(user.id))
    set_auth_cookie(response, token)
    return {"user": serialize_user(user)}


@router.post("/login")
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username.strip().lower(), password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    _log_auth_activity(db, user, "login", "Signed in")
    db.commit()

    token = create_access_token(str(user.id))
    set_auth_cookie(response, token)
    return {"user": serialize_user(user)}


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}
