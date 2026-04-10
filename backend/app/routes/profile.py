from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import (
    clear_auth_cookie,
    get_current_user,
    hash_password,
    verify_password,
)
from ..database.models import ActivityLog, PaymentRecord, User
from ..database.session import get_db

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.post("/password")
async def update_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.password_hash:
        raise HTTPException(status_code=400, detail="This account has no password. Sign in with Google instead.")

    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Password confirmation does not match.")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    current_user.password_hash = hash_password(new_password)
    db.commit()

    return {"ok": True}


@router.post("/delete")
async def delete_account(
    response: Response,
    username_confirmation: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if username_confirmation != current_user.username:
        raise HTTPException(status_code=400, detail="Username confirmation does not match.")

    # Manually delete related rows first — no ORM cascade configured on these relationships.
    db.query(ActivityLog).filter(ActivityLog.user_id == current_user.id).delete(synchronize_session=False)
    db.query(PaymentRecord).filter(PaymentRecord.user_id == current_user.id).delete(synchronize_session=False)
    db.delete(current_user)
    db.commit()

    clear_auth_cookie(response)

    return {"ok": True}
