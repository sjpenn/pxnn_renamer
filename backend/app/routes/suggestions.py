from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.security import get_current_user
from ..database.models import File as StoredFile, FileCollection, User
from ..database.session import get_db

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])


def _collect_field(db: Session, user_id: int, field: str, multivalued: bool) -> list[str]:
    rows = (
        db.query(StoredFile.resolved_json, StoredFile.created_at)
        .join(FileCollection, StoredFile.collection_id == FileCollection.id)
        .filter(FileCollection.user_id == user_id)
        .filter(StoredFile.resolved_json.isnot(None))
        .order_by(StoredFile.created_at.desc())
        .all()
    )

    ranking: dict[str, tuple[int, int]] = {}
    for index, (resolved_json, _created_at) in enumerate(rows):
        try:
            resolved = json.loads(resolved_json) or {}
        except (TypeError, ValueError):
            continue
        raw = resolved.get(field) or ""
        candidates = (
            [part.strip() for part in raw.split(";") if part.strip()]
            if multivalued
            else ([raw.strip()] if raw.strip() else [])
        )
        for name in candidates:
            if name not in ranking:
                ranking[name] = (index, 1)
            else:
                first_seen, count = ranking[name]
                ranking[name] = (first_seen, count + 1)

    # Sort by most-recent-first (ascending index), then frequency descending.
    return sorted(ranking.keys(), key=lambda name: (ranking[name][0], -ranking[name][1]))


@router.get("/producers")
def list_producers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"values": _collect_field(db, current_user.id, "producers", multivalued=True)}


@router.get("/artists")
def list_artists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"values": _collect_field(db, current_user.id, "artist", multivalued=False)}
