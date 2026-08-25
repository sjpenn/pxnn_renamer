"""Append-only audit trail helper.

Every meaningful state change in the system should call ``record_audit`` so we
have a durable, queryable record of *who did what to whom*, including
before/after values and request context (IP + user agent).

The caller is responsible for committing the surrounding transaction; this
helper only stages the ``AuditLog`` row via ``db.add`` so it commits atomically
with the change it describes.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from ..database.models import AuditLog, User


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    # Honor the reverse proxy (Coolify) forwarded header when present.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _label(user: Optional[User]) -> Optional[str]:
    if user is None:
        return None
    return user.email or user.username


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value))


def record_audit(
    db: Session,
    *,
    action: str,
    summary: str,
    actor: Optional[User] = None,
    actor_id: Optional[int] = None,
    actor_label: Optional[str] = None,
    category: str = "general",
    target: Optional[User] = None,
    target_id: Optional[int] = None,
    target_label: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    before: Any = None,
    after: Any = None,
    meta: Optional[dict] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """Stage an audit-log entry. Returns the (uncommitted) row."""
    if actor is not None:
        actor_id = actor.id
        actor_label = actor_label or _label(actor)
    if target is not None:
        target_id = target.id
        target_label = target_label or _label(target)

    entry = AuditLog(
        action=action,
        category=category,
        summary=summary,
        actor_id=actor_id,
        actor_label=actor_label,
        target_id=target_id,
        target_label=target_label,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before_json=_json(before),
        after_json=_json(after),
        meta_json=_json(meta),
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("user-agent") if request is not None else None),
    )
    db.add(entry)
    return entry


def rename_changes(preview_items: list[dict]) -> list[dict]:
    """Build a compact before->after list from wizard preview items."""
    changes = []
    for item in preview_items or []:
        before = item.get("original_name")
        after = item.get("preview_name")
        if before is None and after is None:
            continue
        changes.append({"from": before, "to": after})
    return changes
