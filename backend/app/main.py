from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Request
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .core.config import settings
from .core.pricing import get_payment_options
from .core.security import (
    get_current_user_optional,
    serialize_user,
    set_pending_plan,
)
from sqlalchemy import func, text
from fastapi.responses import JSONResponse
from .database.bootstrap import bootstrap_database
from .database.models import UIComment, User
from .database.session import get_db
import logging

from .routes.auth import router as auth_router
from .routes.coupons import router as coupons_router
from .routes.funnel import router as funnel_router
from .routes.dashboard import router as dashboard_router
from .routes.oauth import router as oauth_router
from .routes.payments import router as payments_router
from .routes.profile import router as profile_router
from .routes.session_heartbeat import router as session_heartbeat_router
from .routes.wizard import router as wizard_router
from .routes.admin import router as admin_router
from .routes.ui_comments import router as ui_comments_router
from .routes import suggestions as suggestions_routes
from .services.announcements import get_active_announcement
from .services.funnel import log_funnel_event
from .services.promotions import get_active_promotion

app = FastAPI(title="PxNN it")


class NoCacheHTMLMiddleware(BaseHTTPMiddleware):
    """Prevent browsers from caching HTML pages so template/style changes deploy instantly.

    Static assets under /static (with query-string versioning) can still be cached
    because we pass them through untouched.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if request.url.path.startswith("/static"):
            # Templates use query-string versioning (?v=...), so long-lived
            # immutable caching is safe and removes per-asset conditional requests.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif content_type.startswith("text/html"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheHTMLMiddleware)

# SessionMiddleware required by authlib for OAuth state/nonce and pending plan storage
app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET)

# Setup Templates and Static Files
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")

app.include_router(auth_router)
app.include_router(coupons_router)
app.include_router(dashboard_router)
app.include_router(oauth_router)
app.include_router(payments_router)
app.include_router(profile_router)
app.include_router(funnel_router)
app.include_router(session_heartbeat_router)
app.include_router(wizard_router)
app.include_router(admin_router)
app.include_router(ui_comments_router)
app.include_router(suggestions_routes.router)


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if current_user:
        billing = request.query_params.get("billing")
        if billing == "cancelled":
            log_funnel_event(
                db,
                current_user,
                event_type="checkout_abandoned",
                summary="Checkout cancelled",
            )
            return RedirectResponse(url="/app?billing=cancelled", status_code=303)

        log_funnel_event(
            db,
            current_user,
            event_type="pricing_viewed",
            summary="Viewed pricing",
        )
        return RedirectResponse(url="/app", status_code=303)

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "current_user": None,
            "page": "home",
            "payment_options": get_payment_options(db),
            "stripe_enabled": bool(settings.STRIPE_SECRET_KEY),
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
            "active_promo": get_active_promotion(db),
        },
    )


@app.get("/app", response_class=HTMLResponse)
async def workspace(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "app.html",
        {
            "title": "PxNN it - Workspace",
            "current_user": current_user,
            "page": "app",
            "initial_user": serialize_user(current_user),
            "payment_options": get_payment_options(db),
            "stripe_enabled": bool(settings.STRIPE_SECRET_KEY),
            "billing_notice": request.query_params.get("billing", ""),
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
            "announcement": get_active_announcement(db, current_user),
            "active_promo": get_active_promotion(db),
            "ui_comment_counts": dict(
                db.query(UIComment.block_key, func.count(UIComment.id))
                .filter(
                    UIComment.page_path == "/app",
                    UIComment.status == "open",
                )
                .group_by(UIComment.block_key)
                .all()
            ),
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/app", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "current_user": None,
            "page": "login",
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/app", status_code=303)

    plan_key = request.query_params.get("plan")
    if plan_key:
        set_pending_plan(request, plan_key)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        {
            "current_user": None,
            "page": "register",
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.get("/forgot", response_class=HTMLResponse)
async def forgot_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/app", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/forgot.html",
        {"current_user": None, "page": "forgot"},
    )


@app.get("/reset", response_class=HTMLResponse)
async def reset_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/app", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/reset.html",
        {
            "current_user": None,
            "page": "reset",
            "token": request.query_params.get("token", ""),
        },
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "title": "Profile — PxNN it",
            "current_user": current_user,
            "page": "profile",
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.get("/health")
async def health(db: Session = Depends(get_db)):
    """Liveness/readiness probe for Coolify and load balancers."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})


@app.on_event("startup")
def startup_event():
    logger = logging.getLogger("pxnn.startup")
    if settings.JWT_SECRET == "change-me-in-production":
        if settings.APP_URL.startswith("https://"):
            raise RuntimeError(
                "Refusing to start: JWT_SECRET is still the default value on a "
                "production (https) deployment. Set JWT_SECRET in the environment."
            )
        logger.warning(
            "JWT_SECRET is the default value — fine for local dev, "
            "but set a real secret before deploying."
        )
    bootstrap_database()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
