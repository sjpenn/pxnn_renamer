from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from .core.config import settings
from .core.pricing import get_payment_options
from .core.security import get_current_user_optional, serialize_user
from .database.bootstrap import bootstrap_database
from .database.models import User
from .routes.auth import router as auth_router
from .routes.dashboard import router as dashboard_router
from .routes.oauth import router as oauth_router
from .routes.payments import router as payments_router
from .routes.wizard import router as wizard_router

app = FastAPI(title="PxNN it")

# SessionMiddleware required by authlib for OAuth state/nonce
app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET)

# Setup Templates and Static Files
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(oauth_router)
app.include_router(payments_router)
app.include_router(wizard_router)


@app.get("/", response_class=HTMLResponse)
async def root(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "PxNN it - Home",
            "initial_user": serialize_user(current_user),
            "payment_options": get_payment_options(),
            "stripe_enabled": bool(settings.STRIPE_SECRET_KEY),
            "billing_notice": request.query_params.get("billing", ""),
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.on_event("startup")
def startup_event():
    bootstrap_database()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
