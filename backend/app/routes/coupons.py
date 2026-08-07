from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.rate_limit import check_rate_limit
from ..core.security import get_current_user
from ..database.models import User
from ..database.session import get_db
from ..services.coupons import CouponError, redeem_coupon

router = APIRouter(prefix="/api/credits", tags=["credits"])


@router.post("/redeem")
async def redeem_code(
    request: Request,
    code: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_rate_limit(request, "coupon_redeem", settings.RATE_LIMIT_FORGOT_PER_WINDOW)
    try:
        coupon = redeem_coupon(db, current_user, code)
    except CouponError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "code": coupon.code,
        "credits_granted": coupon.credits,
        "credit_balance": current_user.credit_balance,
    }
