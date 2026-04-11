from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session

from ..core.security import get_current_user
from ..database.models import User
from ..database.session import get_db
from ..services.funnel import log_funnel_event

router = APIRouter(tags=["funnel"])


@router.post("/api/funnel/plan-selected", status_code=204)
async def plan_selected(
    plan_key: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    log_funnel_event(
        db,
        current_user,
        event_type="plan_selected",
        summary=f"Plan selected: {plan_key}",
        extra={"plan_key": plan_key},
    )
    return Response(status_code=204)
