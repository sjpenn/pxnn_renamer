from typing import Optional
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from ..core.pricing import get_payment_options
from ..core.security import get_current_user, serialize_user
from ..database.models import ActivityLog, FileCollection, PaymentRecord, User
from ..database.session import get_db

router = APIRouter(tags=["dashboard"])


def _loads_json(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


@router.get("/api/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collections = (
        db.query(FileCollection)
        .options(joinedload(FileCollection.files))
        .filter(FileCollection.user_id == current_user.id)
        .order_by(FileCollection.created_at.desc())
        .all()
    )
    activities = (
        db.query(ActivityLog)
        .filter(ActivityLog.user_id == current_user.id)
        .order_by(ActivityLog.created_at.desc())
        .all()
    )
    payments = (
        db.query(PaymentRecord)
        .filter(PaymentRecord.user_id == current_user.id)
        .order_by(PaymentRecord.created_at.desc())
        .all()
    )

    return {
        "user": serialize_user(current_user),
        "summary": {
            "credit_balance": current_user.credit_balance,
            "total_batches": len(collections),
            "total_files": sum(len(collection.files) for collection in collections),
            "downloads_completed": sum(collection.download_count for collection in collections),
        },
        "collections": [
            {
                "id": collection.id,
                "session_id": collection.session_id,
                "name": collection.name,
                "status": collection.status,
                "file_count": len(collection.files),
                "total_size_bytes": collection.total_size_bytes,
                "download_count": collection.download_count,
                "created_at": collection.created_at.isoformat() if collection.created_at else None,
                "preview_generated_at": (
                    collection.preview_generated_at.isoformat()
                    if collection.preview_generated_at
                    else None
                ),
                "downloaded_at": collection.downloaded_at.isoformat() if collection.downloaded_at else None,
            }
            for collection in collections
        ],
        "activity": [
            {
                "id": activity.id,
                "event_type": activity.event_type,
                "summary": activity.summary,
                "collection_id": activity.collection_id,
                "details": _loads_json(activity.details_json),
                "created_at": activity.created_at.isoformat() if activity.created_at else None,
            }
            for activity in activities
        ],
        "payments": [
            {
                "id": payment.id,
                "plan_key": payment.plan_key,
                "credits": payment.credits,
                "amount_cents": payment.amount_cents,
                "currency": payment.currency,
                "status": payment.status,
                "created_at": payment.created_at.isoformat() if payment.created_at else None,
                "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
            }
            for payment in payments
        ],
        "payment_options": get_payment_options(),
    }
