import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.security import require_admin
from ..database.models import ActivityLog, Announcement, User
from ..database.session import get_db
from ..services import admin_stats

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "current_user": admin,
            "page": "admin",
            "title": "Admin · PxNN",
        },
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    q: str = "",
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User).order_by(User.created_at.desc())
    search = (q or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(User.username.ilike(like), User.email.ilike(like))
        )
    users = query.limit(200).all()
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            "current_user": admin,
            "users": users,
            "q": search,
            "title": "Users · PxNN Admin",
        },
    )


@router.post("/users/{user_id}/credits")
async def admin_grant_credits(
    user_id: int,
    amount: int = Form(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    previous = target.credit_balance
    target.credit_balance = previous + amount
    db.add(
        ActivityLog(
            user_id=target.id,
            event_type="admin_credit_grant",
            summary=f"Admin granted {amount} credits",
            details_json=json.dumps(
                {
                    "granted_by_admin_id": admin.id,
                    "granted_by_email": admin.email,
                    "amount": amount,
                    "previous_balance": previous,
                    "new_balance": target.credit_balance,
                }
            ),
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/testing")
async def admin_toggle_testing(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    target.is_testing = not bool(target.is_testing)
    db.add(
        ActivityLog(
            user_id=target.id,
            event_type="admin_testing_toggled",
            summary=f"Testing mode {'enabled' if target.is_testing else 'disabled'}",
            details_json=json.dumps(
                {
                    "toggled_by_admin_id": admin.id,
                    "toggled_by_email": admin.email,
                    "new_value": bool(target.is_testing),
                }
            ),
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/partials/kpis", response_class=HTMLResponse)
async def partial_kpis(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/partials/kpi_cards.html",
        {
            "users": admin_stats.user_counts(db),
            "revenue": admin_stats.revenue_stats(db),
            "plans": admin_stats.plan_breakdown(db),
            "credits": admin_stats.credit_stats(db),
            "sessions": admin_stats.session_stats(db),
        },
    )


@router.get("/partials/activity", response_class=HTMLResponse)
async def partial_activity(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/partials/activity_feed.html",
        {"rows": admin_stats.recent_activity(db, limit=50)},
    )


@router.get("/partials/online", response_class=HTMLResponse)
async def partial_online(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/partials/online_now.html",
        {"sessions": admin_stats.session_stats(db)},
    )


@router.get("/partials/funnel", response_class=HTMLResponse)
async def partial_funnel(
    request: Request,
    window: int = 7,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    window_days = max(1, min(window, 365))
    return templates.TemplateResponse(
        request,
        "admin/partials/funnel_widget.html",
        {
            "window_days": window_days,
            "stages": admin_stats.funnel_stats(db, window_days=window_days),
        },
    )


@router.get("/partials/stuck", response_class=HTMLResponse)
async def partial_stuck(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "admin/partials/stuck_at_checkout.html",
        {"rows": admin_stats.stuck_at_checkout(db, limit=20)},
    )


@router.get("/announcements", response_class=HTMLResponse)
async def admin_announcements_page(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Announcement)
        .order_by(Announcement.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/announcements.html",
        {
            "current_user": admin,
            "announcements": rows,
            "title": "Announcements · PxNN Admin",
        },
    )


@router.post("/announcements")
async def admin_announcements_create(
    title: str = Form(...),
    body: str = Form(...),
    severity: str = Form("info"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.add(
        Announcement(
            title=title,
            body=body,
            severity=severity,
            is_published=False,
            created_by_id=admin.id,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/announcements", status_code=303)


@router.post("/announcements/{announcement_id}/publish")
async def admin_announcements_publish(
    announcement_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if row:
        row.is_published = not row.is_published
        db.commit()
    return RedirectResponse(url="/admin/announcements", status_code=303)


@router.post("/announcements/{announcement_id}/delete")
async def admin_announcements_delete(
    announcement_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if row:
        db.delete(row)
        db.commit()
    return RedirectResponse(url="/admin/announcements", status_code=303)
