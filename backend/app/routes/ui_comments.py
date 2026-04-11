from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session

from ..core.security import require_admin
from ..database.models import UIComment, User
from ..database.session import get_db

router = APIRouter(tags=["ui-comments"])


@router.post("/api/admin/ui-comments", status_code=204)
async def create_ui_comment(
    block_key: str = Form(...),
    page_path: str = Form(...),
    body: str = Form(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    db.add(
        UIComment(
            author_id=admin.id,
            block_key=block_key,
            page_path=page_path,
            body=body,
            status="open",
        )
    )
    db.commit()
    return Response(status_code=204)
