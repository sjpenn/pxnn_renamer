import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.security import require_admin
from ..database.models import ActivityLog, Announcement, Campaign, CampaignImage, CampaignVariant, CommentCluster, UIComment, User
from ..database.session import get_db
from ..services import admin_stats, ai_clusterer

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


# --------------------------------------------------------------------------- #
# UI Comments — admin notes about individual UI blocks
# --------------------------------------------------------------------------- #


@router.get("/ui-comments")
async def admin_ui_comments_legacy_redirect(
    admin: User = Depends(require_admin),
):
    return RedirectResponse(url="/admin/todos", status_code=303)


@router.post("/ui-comments/{comment_id}/resolve")
async def admin_ui_comments_resolve(
    comment_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(UIComment).filter(UIComment.id == comment_id).first()
    if row:
        if row.status == "resolved":
            row.status = "open"
            row.resolved_at = None
        else:
            row.status = "resolved"
            row.resolved_at = datetime.utcnow()
        db.commit()
    return RedirectResponse(url="/admin/ui-comments", status_code=303)


@router.post("/ui-comments/{comment_id}/delete")
async def admin_ui_comments_delete(
    comment_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(UIComment).filter(UIComment.id == comment_id).first()
    if row:
        db.delete(row)
        db.commit()
    return RedirectResponse(url="/admin/ui-comments", status_code=303)


# --------------------------------------------------------------------------- #
# Todos — the richer replacement for the raw UI-comment list
# --------------------------------------------------------------------------- #
VALID_TODO_STATUSES = {"open", "in_progress", "done", "wont_do"}


@router.get("/todos", response_class=HTMLResponse)
async def admin_todos_page(
    request: Request,
    status: str = "all",
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Fetch all comments (with author metadata), most recent first
    query = (
        db.query(UIComment, User.username, User.email)
        .join(User, UIComment.author_id == User.id)
        .order_by(UIComment.created_at.desc())
    )
    if status in VALID_TODO_STATUSES:
        query = query.filter(UIComment.status == status)

    comment_rows = [
        {
            "comment": c,
            "author_username": username,
            "author_email": email,
        }
        for c, username, email in query.all()
    ]

    # Fetch clusters; attach the relevant comments to each
    clusters = db.query(CommentCluster).order_by(CommentCluster.created_at.desc()).all()
    clustered_ids = set()
    grouped = []
    for cluster in clusters:
        rows_in_cluster = [
            r for r in comment_rows if r["comment"].cluster_id == cluster.id
        ]
        if rows_in_cluster:
            grouped.append({"cluster": cluster, "rows": rows_in_cluster})
            for r in rows_in_cluster:
                clustered_ids.add(r["comment"].id)

    unclustered = [r for r in comment_rows if r["comment"].id not in clustered_ids]

    return templates.TemplateResponse(
        request,
        "admin/todos.html",
        {
            "current_user": admin,
            "grouped": grouped,
            "unclustered": unclustered,
            "status_filter": status,
            "total_open": sum(
                1 for r in comment_rows if r["comment"].status == "open"
            ),
            "open_unclustered_count": sum(
                1 for r in comment_rows
                if r["comment"].status == "open" and r["comment"].cluster_id is None
            ),
            "title": "Todos · PxNN Admin",
        },
    )


@router.post("/todos/{comment_id}/status")
async def admin_todos_set_status(
    comment_id: int,
    status: str = Form(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if status not in VALID_TODO_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status.")

    row = db.query(UIComment).filter(UIComment.id == comment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Todo not found.")

    row.status = status
    if status in ("done", "wont_do"):
        row.resolved_at = datetime.utcnow()
    else:
        row.resolved_at = None
    db.commit()
    return RedirectResponse(url="/admin/todos", status_code=303)


@router.post("/todos/analyze")
async def admin_todos_analyze(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    open_unclustered = (
        db.query(UIComment)
        .filter(
            UIComment.status == "open",
            UIComment.cluster_id.is_(None),
        )
        .all()
    )
    if not open_unclustered:
        return RedirectResponse(url="/admin/todos", status_code=303)

    clusters = ai_clusterer.cluster_notes(open_unclustered)
    for cluster_data in clusters:
        if not cluster_data.note_ids:
            continue
        cluster_row = CommentCluster(
            title=cluster_data.title[:500],
            summary=cluster_data.summary,
        )
        db.add(cluster_row)
        db.flush()  # assign id
        for note_id in cluster_data.note_ids:
            note = db.query(UIComment).filter(UIComment.id == note_id).first()
            if note and note.cluster_id is None and note.status == "open":
                note.cluster_id = cluster_row.id
    db.commit()
    return RedirectResponse(url="/admin/todos", status_code=303)


# --------------------------------------------------------------------------- #
# Campaigns — AI-generated ad creative for Meta
# --------------------------------------------------------------------------- #


@router.get("/campaigns", response_class=HTMLResponse)
async def admin_campaigns_list(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    campaigns = (
        db.query(Campaign)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/campaigns.html",
        {
            "current_user": admin,
            "campaigns": campaigns,
            "title": "Campaigns · PxNN Admin",
        },
    )


@router.get("/campaigns/new", response_class=HTMLResponse)
async def admin_campaigns_new(
    request: Request,
    admin: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "admin/campaign_new.html",
        {
            "current_user": admin,
            "title": "New Campaign · PxNN Admin",
        },
    )


@router.post("/campaigns")
async def admin_campaigns_create(
    name: str = Form(...),
    product_description: str = Form(...),
    target_audience: str = Form(...),
    offer: str = Form(""),
    tone: str = Form("authentic"),
    placements: str = Form("feed,story"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    campaign = Campaign(
        admin_id=admin.id,
        name=name,
        product_description=product_description,
        target_audience=target_audience,
        offer=offer or None,
        tone=tone,
        placements=placements,
        status="draft",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return RedirectResponse(url=f"/admin/campaigns/{campaign.id}", status_code=303)


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def admin_campaigns_detail(
    campaign_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return templates.TemplateResponse(
        request,
        "admin/campaign_detail.html",
        {
            "current_user": admin,
            "campaign": campaign,
            "title": f"{campaign.name} · PxNN Admin",
        },
    )


@router.post("/campaigns/{campaign_id}/delete")
async def admin_campaigns_delete(
    campaign_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign:
        db.delete(campaign)
        db.commit()
    return RedirectResponse(url="/admin/campaigns", status_code=303)
