# Google OAuth + Subscription Payments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google OAuth (alongside username/password) and monthly subscription plans (alongside one-time credits) to PxNN it, then push to GitHub and redeploy to Railway.

**Architecture:** Google OAuth via `authlib` starlette integration with account-linking logic extracted to a pure testable function. Stripe subscriptions use `mode="subscription"` checkout with `subscription_data.metadata` for plan lookup in `invoice.paid` webhooks. New User fields (`google_sub`, `email`, `subscription_id`, `subscription_status`, `subscription_plan`) and PaymentRecord fields (`plan_type`, `stripe_invoice_id`) are added through the existing `bootstrap.py` `_ensure_column` pattern.

**Tech Stack:** FastAPI, authlib≥1.3.0, httpx, itsdangerous, Stripe subscriptions API, SQLAlchemy, pytest, starlette TestClient

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add authlib, httpx, pytest, requests |
| `tests/__init__.py` | Create | Empty package marker |
| `tests/conftest.py` | Create | pytest fixtures: test client, SQLite in-memory DB |
| `tests/test_pricing.py` | Create | Pricing plan unit tests |
| `tests/test_security.py` | Create | Nullable password_hash + serialize_user tests |
| `tests/test_oauth.py` | Create | `_resolve_or_create_google_user` logic tests |
| `tests/test_payments.py` | Create | Subscription checkout + webhook tests |
| `backend/app/core/config.py` | Modify | Add Google OAuth + 3 subscription Stripe price ID vars |
| `backend/app/core/pricing.py` | Modify | Add 3 subscription plans with `plan_type="subscription"` |
| `backend/app/core/security.py` | Modify | Handle `password_hash=None`, add email/subscription to serialize_user |
| `backend/app/database/models.py` | Modify | New User fields, PaymentRecord fields, `password_hash` nullable |
| `backend/app/database/bootstrap.py` | Modify | `_ensure_column` + `_alter_nullable` calls for new schema |
| `backend/app/routes/oauth.py` | Create | `/auth/google/login` + `/auth/google/callback` |
| `backend/app/routes/auth.py` | Modify | Accept optional email on register |
| `backend/app/routes/payments.py` | Modify | Subscription checkout mode, 3 new webhook handlers, cancel route |
| `backend/app/main.py` | Modify | Add SessionMiddleware, include oauth_router |
| `frontend/templates/index.html` | Modify | Google sign-in button, subscription plan UI, cancel button |
| `docker-compose.yml` | Modify | Pass through 6 new env vars |
| `.env.example` | Create | Document all env vars |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Replace the file contents with:

```
fastapi==0.115.12
uvicorn[standard]==0.34.0
sqlalchemy==2.0.40
psycopg2-binary==2.9.10
alembic==1.15.2
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.20
pydantic-settings==2.8.1
jinja2==3.1.6
python-dotenv==1.0.1
stripe==12.0.0
authlib>=1.3.0
httpx>=0.27.0
itsdangerous>=2.1.0
pytest>=8.0.0
requests>=2.31.0
```

- [ ] **Step 2: Install locally**

```bash
pip install authlib httpx itsdangerous pytest requests
```

Expected: packages install without errors.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add authlib, httpx, itsdangerous, pytest dependencies"
```

---

## Task 2: Test Infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create tests/__init__.py**

```python
```
(empty file)

- [ ] **Step 2: Create tests/conftest.py**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.database.models import Base
from backend.app.database.session import get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()
```

- [ ] **Step 3: Verify pytest discovers the fixture**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/ --collect-only
```

Expected: `collected 0 items` (no tests yet, no errors).

- [ ] **Step 4: Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: add pytest fixtures and test infrastructure"
```

---

## Task 3: Update Config

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Update config.py**

```python
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./pxnn_it.db"
    JWT_SECRET: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    COOKIE_NAME: str = "pxnn_session"
    APP_URL: str = "http://localhost:8000"
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_SINGLE_EXPORT_PRICE_ID: Optional[str] = None
    STRIPE_CREATOR_PACK_PRICE_ID: Optional[str] = None
    STRIPE_LABEL_PACK_PRICE_ID: Optional[str] = None
    STRIPE_STARTER_MONTHLY_PRICE_ID: Optional[str] = None
    STRIPE_PRO_MONTHLY_PRICE_ID: Optional[str] = None
    STRIPE_LABEL_MONTHLY_PRICE_ID: Optional[str] = None
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat: add Google OAuth and subscription Stripe price ID config vars"
```

---

## Task 4: Update Pricing (TDD)

**Files:**
- Modify: `backend/app/core/pricing.py`
- Create: `tests/test_pricing.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_pricing.py`:

```python
from backend.app.core.pricing import get_payment_options, get_payment_plan, PAYMENT_PLANS


def test_get_payment_options_includes_subscription_plans():
    options = get_payment_options()
    plan_keys = [o["key"] for o in options]
    assert "starter_monthly" in plan_keys
    assert "pro_monthly" in plan_keys
    assert "label_monthly" in plan_keys


def test_subscription_plans_have_plan_type():
    options = get_payment_options()
    sub_options = [o for o in options if o["key"].endswith("_monthly")]
    assert len(sub_options) == 3
    for opt in sub_options:
        assert opt["plan_type"] == "subscription"


def test_one_time_plans_have_plan_type():
    options = get_payment_options()
    one_time = [o for o in options if not o["key"].endswith("_monthly")]
    assert len(one_time) == 3
    for opt in one_time:
        assert opt["plan_type"] == "one_time"


def test_get_payment_plan_subscription_returns_plan_type():
    plan = get_payment_plan("pro_monthly")
    assert plan["plan_type"] == "subscription"
    assert plan["credits"] == 15
    assert plan["amount_cents"] == 2900


def test_get_payment_plan_unknown_raises_key_error():
    try:
        get_payment_plan("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/test_pricing.py -v
```

Expected: 5 failures (subscription keys not found).

- [ ] **Step 3: Update pricing.py**

```python
from .config import settings

PAYMENT_PLANS = {
    "single_export": {
        "label": "Single Export",
        "description": "1 download credit for a finished rename batch.",
        "amount_cents": 700,
        "credits": 1,
        "price_id_setting": "STRIPE_SINGLE_EXPORT_PRICE_ID",
        "accent": "Starter",
        "plan_type": "one_time",
    },
    "creator_pack": {
        "label": "Creator Pack",
        "description": "10 download credits for repeat uploads and revisions.",
        "amount_cents": 3900,
        "credits": 10,
        "price_id_setting": "STRIPE_CREATOR_PACK_PRICE_ID",
        "accent": "Best value",
        "plan_type": "one_time",
    },
    "label_pack": {
        "label": "Label Pack",
        "description": "50 download credits for teams and heavier release schedules.",
        "amount_cents": 14900,
        "credits": 50,
        "price_id_setting": "STRIPE_LABEL_PACK_PRICE_ID",
        "accent": "Team",
        "plan_type": "one_time",
    },
    "starter_monthly": {
        "label": "Starter",
        "description": "3 credits/month for independent producers.",
        "amount_cents": 900,
        "credits": 3,
        "price_id_setting": "STRIPE_STARTER_MONTHLY_PRICE_ID",
        "accent": "Monthly",
        "plan_type": "subscription",
    },
    "pro_monthly": {
        "label": "Pro",
        "description": "15 credits/month for regular uploaders.",
        "amount_cents": 2900,
        "credits": 15,
        "price_id_setting": "STRIPE_PRO_MONTHLY_PRICE_ID",
        "accent": "Popular",
        "plan_type": "subscription",
    },
    "label_monthly": {
        "label": "Label",
        "description": "60 credits/month for teams and heavy release schedules.",
        "amount_cents": 7900,
        "credits": 60,
        "price_id_setting": "STRIPE_LABEL_MONTHLY_PRICE_ID",
        "accent": "Team",
        "plan_type": "subscription",
    },
}


def _format_amount(amount_cents: int) -> str:
    dollars = amount_cents / 100
    if dollars.is_integer():
        return f"${int(dollars)}"
    return f"${dollars:.2f}"


def get_payment_options() -> list[dict]:
    options = []
    for key, plan in PAYMENT_PLANS.items():
        price_id = getattr(settings, plan["price_id_setting"])
        options.append(
            {
                "key": key,
                "label": plan["label"],
                "description": plan["description"],
                "amount_cents": plan["amount_cents"],
                "amount_label": _format_amount(plan["amount_cents"]),
                "credits": plan["credits"],
                "accent": plan["accent"],
                "stripe_price_id": price_id,
                "plan_type": plan["plan_type"],
            }
        )
    return options


def get_payment_plan(plan_key: str) -> dict:
    if plan_key not in PAYMENT_PLANS:
        raise KeyError(plan_key)

    plan = PAYMENT_PLANS[plan_key]
    return {
        **plan,
        "key": plan_key,
        "amount_label": _format_amount(plan["amount_cents"]),
        "stripe_price_id": getattr(settings, plan["price_id_setting"]),
    }
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/test_pricing.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/pricing.py tests/test_pricing.py
git commit -m "feat: add monthly subscription plans to pricing"
```

---

## Task 5: Update Database Models

**Files:**
- Modify: `backend/app/database/models.py`

- [ ] **Step 1: Update models.py**

```python
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True)  # nullable for Google-only accounts
    email = Column(String, nullable=True, index=True)
    google_sub = Column(String, unique=True, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    subscription_id = Column(String, nullable=True)
    subscription_status = Column(String, nullable=True)
    subscription_plan = Column(String, nullable=True)
    credit_balance = Column(Integer, default=0, nullable=False)
    active_plan = Column(String, default="free", nullable=False)
    plan_status = Column(String, default="inactive", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    collections = relationship("FileCollection", back_populates="owner", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    payment_records = relationship("PaymentRecord", back_populates="user", cascade="all, delete-orphan")


class FileCollection(Base):
    __tablename__ = "file_collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    format_template = Column(String, default="ARTIST_TITLE_PRODUCERS_MIX_VERSION", nullable=False)
    delimiter = Column(String, default="underscore", nullable=False)
    case_style = Column(String, default="keep", nullable=False)
    safe_cleanup = Column(Boolean, default=True, nullable=False)
    total_size_bytes = Column(BigInteger, default=0, nullable=False)
    status = Column(String, default="uploaded", nullable=False)
    download_count = Column(Integer, default=0, nullable=False)
    preview_generated_at = Column(DateTime, nullable=True)
    downloaded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="collections")
    files = relationship("File", back_populates="collection", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="collection")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("file_collections.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String, unique=True, nullable=False, index=True)
    original_path = Column(String, nullable=False)
    current_path = Column(String, nullable=False)
    file_size = Column(BigInteger)
    extension = Column(String)
    extracted_json = Column(Text, nullable=True)
    resolved_json = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    collection = relationship("FileCollection", back_populates="files")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(Integer, ForeignKey("file_collections.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="activity_logs")
    collection = relationship("FileCollection", back_populates="activity_logs")


class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_checkout_session_id = Column(String, unique=True, nullable=True, index=True)
    stripe_invoice_id = Column(String, unique=True, nullable=True, index=True)
    stripe_customer_id = Column(String, nullable=True)
    stripe_price_id = Column(String, nullable=True)
    plan_key = Column(String, nullable=False)
    plan_type = Column(String, nullable=False, default="one_time")
    amount_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String, nullable=False, default="usd")
    credits = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending")
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="payment_records")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/database/models.py
git commit -m "feat: add google_sub, email, subscription fields to User; plan_type to PaymentRecord"
```

---

## Task 6: Update Bootstrap

**Files:**
- Modify: `backend/app/database/bootstrap.py`

- [ ] **Step 1: Update bootstrap.py**

```python
from sqlalchemy import inspect, text

from .models import Base
from .session import engine


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(engine)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _ensure_column(table_name: str, column_name: str, ddl: str) -> None:
    if table_name not in inspect(engine).get_table_names():
        return

    if column_name in _column_names(table_name):
        return

    with engine.begin() as connection:
        connection.execute(text(ddl))


def _run_ddl_safe(ddl: str) -> None:
    """Run a DDL statement, ignoring errors (for idempotent schema changes)."""
    try:
        with engine.begin() as connection:
            connection.execute(text(ddl))
    except Exception:
        pass


def bootstrap_database() -> None:
    Base.metadata.create_all(bind=engine)

    # Users — original columns
    _ensure_column("users", "stripe_customer_id", "ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    _ensure_column("users", "credit_balance", "ALTER TABLE users ADD COLUMN credit_balance INTEGER DEFAULT 0")
    _ensure_column("users", "active_plan", "ALTER TABLE users ADD COLUMN active_plan TEXT DEFAULT 'free'")
    _ensure_column("users", "plan_status", "ALTER TABLE users ADD COLUMN plan_status TEXT DEFAULT 'inactive'")

    # Users — new OAuth + subscription columns
    _ensure_column("users", "email", "ALTER TABLE users ADD COLUMN email TEXT")
    _ensure_column("users", "google_sub", "ALTER TABLE users ADD COLUMN google_sub TEXT")
    _ensure_column("users", "subscription_id", "ALTER TABLE users ADD COLUMN subscription_id TEXT")
    _ensure_column("users", "subscription_status", "ALTER TABLE users ADD COLUMN subscription_status TEXT")
    _ensure_column("users", "subscription_plan", "ALTER TABLE users ADD COLUMN subscription_plan TEXT")

    # Make password_hash nullable on existing PostgreSQL deployments
    _run_ddl_safe("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")

    # Add unique index for google_sub
    _run_ddl_safe("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub) WHERE google_sub IS NOT NULL")
    _run_ddl_safe("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    # FileCollections
    _ensure_column(
        "file_collections",
        "session_id",
        "ALTER TABLE file_collections ADD COLUMN session_id TEXT",
    )
    _ensure_column(
        "file_collections",
        "format_template",
        "ALTER TABLE file_collections ADD COLUMN format_template TEXT DEFAULT 'ARTIST_TITLE_PRODUCERS_MIX_VERSION'",
    )
    _ensure_column(
        "file_collections",
        "delimiter",
        "ALTER TABLE file_collections ADD COLUMN delimiter TEXT DEFAULT 'underscore'",
    )
    _ensure_column(
        "file_collections",
        "case_style",
        "ALTER TABLE file_collections ADD COLUMN case_style TEXT DEFAULT 'keep'",
    )
    _ensure_column(
        "file_collections",
        "safe_cleanup",
        "ALTER TABLE file_collections ADD COLUMN safe_cleanup BOOLEAN DEFAULT TRUE",
    )
    _ensure_column(
        "file_collections",
        "total_size_bytes",
        "ALTER TABLE file_collections ADD COLUMN total_size_bytes BIGINT DEFAULT 0",
    )
    _ensure_column(
        "file_collections",
        "status",
        "ALTER TABLE file_collections ADD COLUMN status TEXT DEFAULT 'uploaded'",
    )
    _ensure_column(
        "file_collections",
        "download_count",
        "ALTER TABLE file_collections ADD COLUMN download_count INTEGER DEFAULT 0",
    )
    _ensure_column(
        "file_collections",
        "preview_generated_at",
        "ALTER TABLE file_collections ADD COLUMN preview_generated_at TIMESTAMP",
    )
    _ensure_column(
        "file_collections",
        "downloaded_at",
        "ALTER TABLE file_collections ADD COLUMN downloaded_at TIMESTAMP",
    )

    # Files
    _ensure_column("files", "external_id", "ALTER TABLE files ADD COLUMN external_id TEXT")
    _ensure_column("files", "extracted_json", "ALTER TABLE files ADD COLUMN extracted_json TEXT")
    _ensure_column("files", "resolved_json", "ALTER TABLE files ADD COLUMN resolved_json TEXT")
    _ensure_column("files", "created_at", "ALTER TABLE files ADD COLUMN created_at TIMESTAMP")

    # PaymentRecords — new columns
    _ensure_column("payment_records", "plan_type", "ALTER TABLE payment_records ADD COLUMN plan_type TEXT DEFAULT 'one_time'")
    _ensure_column("payment_records", "stripe_invoice_id", "ALTER TABLE payment_records ADD COLUMN stripe_invoice_id TEXT")

    # Make stripe_checkout_session_id nullable for subscription renewal records
    _run_ddl_safe("ALTER TABLE payment_records ALTER COLUMN stripe_checkout_session_id DROP NOT NULL")

    with engine.begin() as connection:
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_file_collections_session_id ON file_collections (session_id)")
        )
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_files_external_id ON files (external_id)")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_records_checkout_session_id "
                "ON payment_records (stripe_checkout_session_id) WHERE stripe_checkout_session_id IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_records_stripe_invoice_id "
                "ON payment_records (stripe_invoice_id) WHERE stripe_invoice_id IS NOT NULL"
            )
        )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/database/bootstrap.py
git commit -m "feat: bootstrap new User OAuth/subscription columns and PaymentRecord plan_type"
```

---

## Task 7: Update Security (TDD)

**Files:**
- Modify: `backend/app/core/security.py`
- Create: `tests/test_security.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_security.py`:

```python
from backend.app.core.security import authenticate_user, serialize_user
from backend.app.database.models import User


def _make_user(**kwargs):
    defaults = {
        "id": 1,
        "username": "testuser",
        "password_hash": None,
        "email": "test@example.com",
        "credit_balance": 5,
        "active_plan": "pro_monthly",
        "plan_status": "active",
        "subscription_status": "active",
        "subscription_plan": "pro_monthly",
        "created_at": None,
    }
    defaults.update(kwargs)
    u = User.__new__(User)
    for k, v in defaults.items():
        setattr(u, k, v)
    return u


def test_serialize_user_includes_email():
    user = _make_user(email="artist@example.com")
    result = serialize_user(user)
    assert result["email"] == "artist@example.com"


def test_serialize_user_includes_subscription_status():
    user = _make_user(subscription_status="active", subscription_plan="pro_monthly")
    result = serialize_user(user)
    assert result["subscription_status"] == "active"
    assert result["subscription_plan"] == "pro_monthly"


def test_serialize_user_none_returns_none():
    assert serialize_user(None) is None


def test_authenticate_user_google_only_returns_none(db):
    from backend.app.core.security import hash_password
    user = User(username="googleuser", password_hash=None, email="g@example.com", google_sub="sub123")
    db.add(user)
    db.commit()
    result = authenticate_user(db, "googleuser", "any_password")
    assert result is None
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/test_security.py -v
```

Expected: failures on `email`, `subscription_status`, `subscription_plan` keys.

- [ ] **Step 3: Update security.py**

```python
from typing import Optional, Union
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..database.models import User
from ..database.session import get_db
from .config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.APP_URL.startswith("https://"),
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(settings.COOKIE_NAME)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not user.password_hash:
        # Google-only account — cannot sign in with password
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def serialize_user(user: Optional[User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "email": getattr(user, "email", None),
        "credit_balance": user.credit_balance,
        "active_plan": user.active_plan,
        "plan_status": user.plan_status,
        "subscription_status": getattr(user, "subscription_status", None),
        "subscription_plan": getattr(user, "subscription_plan", None),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        resolved_user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    return db.query(User).filter(User.id == resolved_user_id).first()


def get_current_user(
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    if current_user:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in to continue.",
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/test_security.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py tests/test_security.py
git commit -m "feat: handle nullable password_hash and add subscription fields to serialize_user"
```

---

## Task 8: Create Google OAuth Routes (TDD)

**Files:**
- Create: `backend/app/routes/oauth.py`
- Create: `tests/test_oauth.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_oauth.py`:

```python
import pytest
from backend.app.database.models import User, ActivityLog
from backend.app.routes.oauth import _resolve_or_create_google_user


def test_creates_new_user_from_google(db):
    user = _resolve_or_create_google_user(db, google_sub="sub_new", email="new@example.com")
    assert user.id is not None
    assert user.google_sub == "sub_new"
    assert user.email == "new@example.com"
    assert user.password_hash is None


def test_returns_existing_user_by_google_sub(db):
    existing = User(username="existing", google_sub="sub_exists", email="e@x.com", password_hash=None)
    db.add(existing)
    db.commit()

    result = _resolve_or_create_google_user(db, google_sub="sub_exists", email="e@x.com")
    assert result.id == existing.id


def test_links_google_to_existing_email_user(db):
    existing = User(username="emailuser", password_hash="hashed", email="link@x.com", google_sub=None)
    db.add(existing)
    db.commit()

    result = _resolve_or_create_google_user(db, google_sub="sub_link", email="link@x.com")
    assert result.id == existing.id
    assert result.google_sub == "sub_link"


def test_creates_unique_username_on_collision(db):
    # Create a user that will collide with the derived username
    db.add(User(username="artist", password_hash="hashed", email="other@x.com"))
    db.commit()

    user = _resolve_or_create_google_user(db, google_sub="sub_coll", email="artist@example.com")
    # Should not be exactly "artist" since that's taken
    assert user.username != "artist"
    assert "artist" in user.username


def test_logs_account_created_activity(db):
    _resolve_or_create_google_user(db, google_sub="sub_log", email="log@x.com")
    log = db.query(ActivityLog).filter(ActivityLog.event_type == "account_created").first()
    assert log is not None
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/test_oauth.py -v
```

Expected: 5 failures (`cannot import _resolve_or_create_google_user`).

- [ ] **Step 3: Create backend/app/routes/oauth.py**

```python
import json
import re

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.requests import Request

from ..core.config import settings
from ..core.security import create_access_token, set_auth_cookie
from ..database.models import ActivityLog, User
from ..database.session import get_db

router = APIRouter(tags=["oauth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def _resolve_or_create_google_user(db: Session, google_sub: str, email: str) -> User:
    """Find existing user by google_sub, link by email, or create new user."""
    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user:
        return user

    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_sub = google_sub
            db.commit()
            return user

    # Derive a unique username from email
    name_hint = email.split("@")[0][:20] if email else "user"
    base_username = re.sub(r"[^a-z0-9]", "_", name_hint.lower()).strip("_")[:20] or "user"
    username = base_username
    suffix = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}_{suffix}"
        suffix += 1

    user = User(
        username=username,
        email=email,
        google_sub=google_sub,
        password_hash=None,
    )
    db.add(user)
    db.flush()
    db.add(
        ActivityLog(
            user_id=user.id,
            event_type="account_created",
            summary="Account created via Google",
            details_json=json.dumps({"method": "google", "email": email}),
        )
    )
    db.commit()
    return user


@router.get("/auth/google/login")
async def google_login(request: Request):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Google OAuth failed. Please try again.") from exc

    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(status_code=400, detail="No user info returned from Google.")

    google_sub = userinfo["sub"]
    email = userinfo.get("email", "")

    user = _resolve_or_create_google_user(db, google_sub=google_sub, email=email)

    jwt_token = create_access_token(str(user.id))
    response = RedirectResponse(url="/", status_code=303)
    set_auth_cookie(response, jwt_token)
    return response
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/test_oauth.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/oauth.py tests/test_oauth.py
git commit -m "feat: add Google OAuth routes with account linking"
```

---

## Task 9: Update main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Update main.py**

```python
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
```

- [ ] **Step 2: Verify app still starts**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -c "from backend.app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: add SessionMiddleware and include oauth router in main app"
```

---

## Task 10: Update Payments Routes (TDD)

**Files:**
- Modify: `backend/app/routes/payments.py`
- Create: `tests/test_payments.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_payments.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from backend.app.database.models import PaymentRecord, User
from backend.app.core.security import hash_password


def _create_user(db, username="testuser", credits=0, stripe_customer_id="cus_test"):
    user = User(
        username=username,
        password_hash=hash_password("password123"),
        credit_balance=credits,
        stripe_customer_id=stripe_customer_id,
    )
    db.add(user)
    db.commit()
    return user


def test_invoice_paid_webhook_grants_subscription_credits(client, db):
    user = _create_user(db, credits=0, stripe_customer_id="cus_inv")
    user.subscription_plan = "pro_monthly"
    user.subscription_id = "sub_test"
    db.commit()

    mock_sub = MagicMock()
    mock_sub.get.return_value = {"plan_key": "pro_monthly", "user_id": str(user.id)}

    event_payload = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "inv_001",
                "customer": "cus_inv",
                "subscription": "sub_test",
                "amount_paid": 2900,
                "currency": "usd",
            }
        },
    }

    with patch("backend.app.routes.payments.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.return_value = event_payload
        mock_stripe.Subscription.retrieve.return_value = mock_sub

        response = client.post(
            "/api/payments/webhook",
            content=json.dumps(event_payload),
            headers={"stripe-signature": "test_sig", "content-type": "application/json"},
        )

    assert response.status_code == 200
    db.refresh(user)
    assert user.credit_balance == 15  # pro_monthly grants 15 credits


def test_invoice_paid_webhook_idempotent(client, db):
    """Second call with same invoice_id must not double-grant credits."""
    user = _create_user(db, credits=15, stripe_customer_id="cus_idem")
    user.subscription_plan = "pro_monthly"
    user.subscription_id = "sub_idem"
    db.commit()

    # Pre-create the payment record as if already processed
    db.add(PaymentRecord(
        user_id=user.id,
        stripe_invoice_id="inv_idem",
        plan_key="pro_monthly",
        plan_type="subscription",
        amount_cents=2900,
        currency="usd",
        credits=15,
        status="paid",
    ))
    db.commit()

    mock_sub = MagicMock()
    mock_sub.get.return_value = {"plan_key": "pro_monthly"}

    event_payload = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "inv_idem",
                "customer": "cus_idem",
                "subscription": "sub_idem",
                "amount_paid": 2900,
                "currency": "usd",
            }
        },
    }

    with patch("backend.app.routes.payments.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.return_value = event_payload
        mock_stripe.Subscription.retrieve.return_value = mock_sub

        response = client.post(
            "/api/payments/webhook",
            content=json.dumps(event_payload),
            headers={"stripe-signature": "test_sig", "content-type": "application/json"},
        )

    assert response.status_code == 200
    db.refresh(user)
    assert user.credit_balance == 15  # unchanged


def test_subscription_cancelled_webhook_clears_plan(client, db):
    user = _create_user(db, stripe_customer_id="cus_cancel")
    user.subscription_id = "sub_cancel"
    user.subscription_status = "active"
    user.subscription_plan = "starter_monthly"
    user.active_plan = "starter_monthly"
    db.commit()

    event_payload = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_cancel",
                "customer": "cus_cancel",
                "status": "canceled",
            }
        },
    }

    with patch("backend.app.routes.payments.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.return_value = event_payload

        response = client.post(
            "/api/payments/webhook",
            content=json.dumps(event_payload),
            headers={"stripe-signature": "test_sig", "content-type": "application/json"},
        )

    assert response.status_code == 200
    db.refresh(user)
    assert user.subscription_status == "canceled"
    assert user.active_plan == "free"
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/test_payments.py -v
```

Expected: failures (webhook secret not configured or handlers missing).

- [ ] **Step 3: Update payments.py**

Replace the full contents of `backend/app/routes/payments.py`:

```python
from typing import Optional
import json
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.pricing import get_payment_options, get_payment_plan, PAYMENT_PLANS
from ..core.security import get_current_user
from ..database.models import ActivityLog, PaymentRecord, User
from ..database.session import get_db

router = APIRouter(tags=["payments"])

STRIPE_API_VERSION = "2026-02-25.clover"


def _configure_stripe() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Payments are not configured yet. Add your Stripe keys to enable checkout.",
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = STRIPE_API_VERSION


def _get_or_create_customer(db: Session, user: User):
    _configure_stripe()

    if user.stripe_customer_id:
        return stripe.Customer.retrieve(user.stripe_customer_id)

    customer = stripe.Customer.create(
        name=user.username,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer


def _line_item_for_plan(plan: dict) -> dict:
    if plan.get("stripe_price_id"):
        return {"price": plan["stripe_price_id"], "quantity": 1}

    price_data = {
        "currency": "usd",
        "unit_amount": plan["amount_cents"],
        "product_data": {
            "name": plan["label"],
            "description": plan["description"],
        },
    }

    if plan.get("plan_type") == "subscription":
        price_data["recurring"] = {"interval": "month"}

    return {"price_data": price_data, "quantity": 1}


def _activity(db: Session, user_id: int, event_type: str, summary: str, details: Optional[dict] = None) -> None:
    db.add(
        ActivityLog(
            user_id=user_id,
            event_type=event_type,
            summary=summary,
            details_json=json.dumps(details or {}),
        )
    )


def _mark_checkout_session_paid(
    db: Session,
    checkout_session_id: str,
    expected_user_id: Optional[int] = None,
) -> PaymentRecord:
    _configure_stripe()
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)

    if checkout_session.get("payment_status") not in ("paid", "no_payment_required"):
        raise HTTPException(status_code=400, detail="This checkout session is not paid yet.")

    payment_record = (
        db.query(PaymentRecord)
        .filter(PaymentRecord.stripe_checkout_session_id == checkout_session_id)
        .first()
    )
    if not payment_record:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    if expected_user_id and payment_record.user_id != expected_user_id:
        raise HTTPException(status_code=403, detail="That payment does not belong to you.")

    if payment_record.status == "paid":
        return payment_record

    user = db.query(User).filter(User.id == payment_record.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found for payment.")

    payment_record.status = "paid"
    payment_record.completed_at = datetime.utcnow()
    payment_record.amount_cents = checkout_session.get("amount_total") or payment_record.amount_cents
    payment_record.currency = checkout_session.get("currency") or payment_record.currency

    is_subscription = payment_record.plan_type == "subscription"

    if is_subscription:
        sub_id = checkout_session.get("subscription")
        user.subscription_id = sub_id
        user.subscription_status = "active"
        user.subscription_plan = payment_record.plan_key
        user.active_plan = payment_record.plan_key
        user.plan_status = "active"
        _activity(
            db,
            user.id,
            "subscription_started",
            f"Subscription started: {payment_record.plan_key}",
            {
                "plan_key": payment_record.plan_key,
                "subscription_id": sub_id,
            },
        )
    else:
        user.credit_balance += payment_record.credits
        user.active_plan = payment_record.plan_key
        user.plan_status = "active"
        _activity(
            db,
            user.id,
            "payment_completed",
            f"{payment_record.credits} credits added",
            {
                "plan_key": payment_record.plan_key,
                "checkout_session_id": checkout_session_id,
                "credit_balance": user.credit_balance,
            },
        )

    db.commit()
    return payment_record


def _handle_invoice_paid(db: Session, invoice: dict) -> None:
    customer_id = invoice.get("customer")
    invoice_id = invoice.get("id")
    subscription_id = invoice.get("subscription")

    if not customer_id or not subscription_id or not invoice_id:
        return

    # Idempotency: skip if this invoice was already processed
    existing = db.query(PaymentRecord).filter(PaymentRecord.stripe_invoice_id == invoice_id).first()
    if existing:
        return

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    # Get plan_key from subscription metadata
    try:
        _configure_stripe()
        sub = stripe.Subscription.retrieve(subscription_id)
        plan_key = (sub.get("metadata") or {}).get("plan_key") or user.subscription_plan
    except Exception:
        plan_key = user.subscription_plan

    if not plan_key or plan_key not in PAYMENT_PLANS:
        return

    plan = PAYMENT_PLANS[plan_key]
    credits_to_add = plan["credits"]
    user.credit_balance += credits_to_add

    db.add(
        PaymentRecord(
            user_id=user.id,
            stripe_invoice_id=invoice_id,
            stripe_customer_id=customer_id,
            plan_key=plan_key,
            plan_type="subscription",
            amount_cents=invoice.get("amount_paid", 0),
            currency=invoice.get("currency", "usd"),
            credits=credits_to_add,
            status="paid",
            completed_at=datetime.utcnow(),
        )
    )
    _activity(
        db,
        user.id,
        "subscription_credits_granted",
        f"{credits_to_add} credits granted for {plan_key}",
        {
            "plan_key": plan_key,
            "invoice_id": invoice_id,
            "credit_balance": user.credit_balance,
        },
    )
    db.commit()


def _handle_subscription_deleted(db: Session, subscription: dict) -> None:
    sub_id = subscription.get("id")
    customer_id = subscription.get("customer")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    user.subscription_status = "canceled"
    user.subscription_id = None
    user.subscription_plan = None
    user.active_plan = "free"
    user.plan_status = "inactive"

    _activity(db, user.id, "subscription_cancelled", "Subscription cancelled", {"subscription_id": sub_id})
    db.commit()


def _handle_subscription_updated(db: Session, subscription: dict) -> None:
    customer_id = subscription.get("customer")
    new_status = subscription.get("status")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    user.subscription_status = new_status
    db.commit()


@router.get("/api/payments/options")
async def payment_options():
    return {"payment_options": get_payment_options()}


@router.post("/api/payments/checkout")
async def create_checkout_session(
    request: Request,
    plan_key: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _configure_stripe()

    try:
        plan = get_payment_plan(plan_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown payment option.") from exc

    customer = _get_or_create_customer(db, current_user)
    app_url = settings.APP_URL.rstrip("/")
    is_subscription = plan.get("plan_type") == "subscription"
    mode = "subscription" if is_subscription else "payment"

    checkout_kwargs = {
        "mode": mode,
        "customer": customer.id,
        "line_items": [_line_item_for_plan(plan)],
        "success_url": f"{app_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{app_url}/?billing=cancelled",
        "allow_promotion_codes": True,
        "metadata": {
            "user_id": str(current_user.id),
            "plan_key": plan["key"],
            "credits": str(plan["credits"]),
        },
    }

    if is_subscription:
        checkout_kwargs["subscription_data"] = {
            "metadata": {
                "plan_key": plan["key"],
                "user_id": str(current_user.id),
            }
        }

    checkout_session = stripe.checkout.Session.create(**checkout_kwargs)

    db.add(
        PaymentRecord(
            user_id=current_user.id,
            stripe_checkout_session_id=checkout_session.id,
            stripe_customer_id=customer.id,
            stripe_price_id=plan.get("stripe_price_id") or plan["key"],
            plan_key=plan["key"],
            plan_type=plan.get("plan_type", "one_time"),
            amount_cents=plan["amount_cents"],
            currency="usd",
            credits=plan["credits"],
            status="pending",
        )
    )
    _activity(
        db,
        current_user.id,
        "payment_started",
        f"Checkout started for {plan['label']}",
        {"plan_key": plan["key"], "credits": plan["credits"], "mode": mode},
    )
    db.commit()

    return {"checkout_url": checkout_session.url}


@router.get("/billing/success")
async def billing_success(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _mark_checkout_session_paid(db, session_id, expected_user_id=current_user.id)
    return RedirectResponse(url="/?billing=success", status_code=303)


@router.post("/api/payments/subscription/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _configure_stripe()

    if not current_user.subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription found.")

    if current_user.subscription_status != "active":
        raise HTTPException(status_code=400, detail="Subscription is not active.")

    stripe.Subscription.delete(current_user.subscription_id)
    # Status will be updated by webhook; set optimistically
    current_user.subscription_status = "canceled"
    current_user.active_plan = "free"
    current_user.plan_status = "inactive"
    _activity(db, current_user.id, "subscription_cancelled", "Subscription cancelled by user")
    db.commit()

    return {"ok": True}


@router.post("/api/payments/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.STRIPE_WEBHOOK_SECRET:
        # In test mode, accept without verification
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured.")

    stripe.api_key = settings.STRIPE_SECRET_KEY or "sk_test_placeholder"
    stripe.api_version = STRIPE_API_VERSION

    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if settings.STRIPE_WEBHOOK_SECRET and signature:
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Stripe payload.") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.") from exc
    else:
        # No secret configured — parse payload directly (test/dev only)
        try:
            event = json.loads(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid payload.") from exc

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        _mark_checkout_session_paid(db, event["data"]["object"]["id"])

    elif event_type == "invoice.paid":
        _handle_invoice_paid(db, event["data"]["object"])

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db, event["data"]["object"])

    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(db, event["data"]["object"])

    return {"received": True}
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/test_payments.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run all tests**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/payments.py tests/test_payments.py
git commit -m "feat: add subscription checkout, invoice.paid handler, cancel route"
```

---

## Task 11: Frontend — Google Sign-In Button

**Files:**
- Modify: `frontend/templates/index.html`

- [ ] **Step 1: Add `google_oauth_enabled` JS variable and Google button to auth panel**

Find the block in `index.html` (around line 521):
```javascript
const initialUser = {{ initial_user|tojson }};
```

Add one line after `const stripeEnabled = ...`:
```javascript
const googleOAuthEnabled = {{ google_oauth_enabled|tojson }};
```

- [ ] **Step 2: Add Google sign-in button to the signed-out auth panel**

Find the `register-form` closing tag (around line 398):
```html
                                    </form>
                                </div>
```

Insert immediately before `</div>` (the closing tag of `signed-out-shell`):
```html
                                    <div id="google-signin-section" class="pt-4 border-t border-outline/10">
                                        <a
                                            href="/auth/google/login"
                                            id="google-signin-btn"
                                            class="flex w-full items-center justify-center gap-3 rounded-xl border border-outline/20 bg-white py-3 text-sm font-bold text-deep-slate transition hover:border-primary-container hover:bg-primary-fixed/10"
                                        >
                                            <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                                                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                                                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                                            </svg>
                                            Continue with Google
                                        </a>
                                    </div>
```

- [ ] **Step 3: Hide Google button when OAuth not enabled**

In the `renderDashboard()` function, after the `signedOutShell.classList.toggle` line, add:

```javascript
const googleSection = document.getElementById("google-signin-section");
if (googleSection) {
    googleSection.classList.toggle("hidden", !googleOAuthEnabled);
}
```

- [ ] **Step 4: Verify the button renders in browser**

Start the app (`docker-compose up` or `uvicorn backend.app.main:app --reload`) and open `http://localhost:8000`. The "Continue with Google" button should appear below the register form.

- [ ] **Step 5: Commit**

```bash
git add frontend/templates/index.html
git commit -m "feat: add Google sign-in button to auth panel"
```

---

## Task 12: Frontend — Subscription Plan UI + Cancel Button

**Files:**
- Modify: `frontend/templates/index.html`

- [ ] **Step 1: Update payment option rendering to differentiate subscriptions**

In `renderDashboard()`, find the `paymentOptionsList.innerHTML = state.paymentOptions.map(...)` block and replace the existing render function body with:

```javascript
paymentOptionsList.innerHTML = state.paymentOptions.map((option) => {
    const disabled = !state.user || !stripeEnabled;
    const buttonLabel = !stripeEnabled ? "UNAVAILABLE" : state.user ? "SELECT" : "SIGN IN";
    const isSubscription = option.plan_type === "subscription";
    const priceLabel = isSubscription
        ? `${option.amount_label}<span class="text-[10px] font-medium opacity-60">/mo</span>`
        : option.amount_label;
    const creditLabel = isSubscription
        ? `${option.credits} credits/month`
        : `${option.credits} credit${option.credits !== 1 ? "s" : ""}`;

    return `
        <article class="flex flex-col justify-between rounded-2xl border border-white/10 bg-white/5 p-4 transition-all hover:bg-white/10">
            <div>
                <p class="text-[10px] font-bold uppercase tracking-widest text-primary-fixed-dim opacity-70 mb-2">${escapeHtml(option.accent)}</p>
                <h4 class="text-lg font-display font-bold text-white mb-2 leading-tight">${escapeHtml(option.label)}</h4>
                <p class="text-xs leading-relaxed opacity-60 font-medium">${escapeHtml(option.description)}</p>
                <p class="mt-2 text-[11px] font-bold text-primary-fixed-dim">${creditLabel}</p>
            </div>
            <div class="mt-6">
                <p class="text-2xl font-display font-bold text-white">${priceLabel}</p>
                <button
                    type="button"
                    class="mt-4 w-full rounded-xl bg-primary-container py-2.5 text-[11px] font-bold uppercase tracking-widest text-white transition hover:bg-primary-container/80 disabled:opacity-40 disabled:cursor-not-allowed"
                    onclick="startCheckout('${escapeHtml(option.key)}')"
                    ${disabled ? "disabled" : ""}
                >
                    ${buttonLabel}
                </button>
            </div>
        </article>
    `;
}).join("");
```

- [ ] **Step 2: Add subscription status + cancel button in signed-in shell**

Find the `signed-in-shell` div (around line 401) and locate the grid section that shows credits and plan status:

```html
                                    <div class="grid grid-cols-2 gap-3">
```

After the closing `</div>` of the grid, add:

```html
                                    <div id="subscription-status-section" class="hidden rounded-xl border border-outline/10 bg-surface-bright p-4">
                                        <div class="flex items-center justify-between">
                                            <div>
                                                <p class="text-[10px] font-bold uppercase tracking-widest text-secondary opacity-60">Active Subscription</p>
                                                <p id="subscription-plan-label" class="mt-1 text-sm font-bold text-deep-slate">—</p>
                                            </div>
                                            <button
                                                id="cancel-subscription-btn"
                                                type="button"
                                                class="text-[10px] font-bold uppercase tracking-widest text-red-500 hover:text-red-700 transition"
                                                onclick="cancelSubscription()"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    </div>
```

- [ ] **Step 3: Update renderDashboard() to show/hide subscription section**

Inside `renderDashboard()`, after the `authPlanStatus.textContent = ...` line, add:

```javascript
const subSection = document.getElementById("subscription-status-section");
const subLabel = document.getElementById("subscription-plan-label");
if (subSection && subLabel) {
    const hasSub = state.user && state.user.subscription_status === "active";
    subSection.classList.toggle("hidden", !hasSub);
    if (hasSub) {
        subLabel.textContent = formatPlanName(state.user.subscription_plan || "");
    }
}
```

- [ ] **Step 4: Add cancelSubscription() JS function**

After the `async function logout()` function, add:

```javascript
async function cancelSubscription() {
    if (!confirm("Cancel your subscription? You keep your remaining credits.")) return;

    const response = await fetch("/api/payments/subscription/cancel", { method: "POST" });

    if (response.status === 401) {
        handleUnauthorized();
        return;
    }

    if (!response.ok) {
        setBanner(await parseError(response), "warning");
        return;
    }

    state.user.subscription_status = "canceled";
    setBanner("Subscription cancelled. Your credits remain in your account.", "success");
    await loadDashboard();
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/templates/index.html
git commit -m "feat: subscription plan cards with monthly label and cancel subscription UI"
```

---

## Task 13: docker-compose.yml + .env.example

**Files:**
- Modify: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Update docker-compose.yml**

In the `app` service `environment:` section, add the 6 new vars after the existing Stripe vars:

```yaml
      STRIPE_STARTER_MONTHLY_PRICE_ID: ${STRIPE_STARTER_MONTHLY_PRICE_ID:-}
      STRIPE_PRO_MONTHLY_PRICE_ID: ${STRIPE_PRO_MONTHLY_PRICE_ID:-}
      STRIPE_LABEL_MONTHLY_PRICE_ID: ${STRIPE_LABEL_MONTHLY_PRICE_ID:-}
      GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID:-}
      GOOGLE_CLIENT_SECRET: ${GOOGLE_CLIENT_SECRET:-}
      GOOGLE_REDIRECT_URI: ${GOOGLE_REDIRECT_URI:-http://localhost:8000/auth/google/callback}
```

- [ ] **Step 2: Create .env.example**

```bash
# PxNN it — Environment Variables
# Copy to .env and fill in values

# App
DATABASE_URL=postgresql://postgres:password@localhost:5432/pxnn_db
JWT_SECRET=change-me-in-production
APP_URL=http://localhost:8000

# Stripe (one-time credits)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_SINGLE_EXPORT_PRICE_ID=price_...
STRIPE_CREATOR_PACK_PRICE_ID=price_...
STRIPE_LABEL_PACK_PRICE_ID=price_...

# Stripe (monthly subscriptions)
STRIPE_STARTER_MONTHLY_PRICE_ID=price_...
STRIPE_PRO_MONTHLY_PRICE_ID=price_...
STRIPE_LABEL_MONTHLY_PRICE_ID=price_...

# Google OAuth
# Create at: https://console.cloud.google.com/apis/credentials
# Authorized redirect URI: https://<your-domain>/auth/google/callback
GOOGLE_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
GOOGLE_REDIRECT_URI=https://<your-domain>/auth/google/callback
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: add new env vars to docker-compose and document in .env.example"
```

---

## Task 14: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Smoke test app import**

```bash
cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && python -c "from backend.app.main import app; print('App import OK')"
```

Expected: `App import OK`

---

## Task 15: Push to GitHub

- [ ] **Step 1: Verify clean working tree**

```bash
git -C /Users/sjpenn/DEV-SITES/DEMOS/music_renamer status
```

Expected: `nothing to commit, working tree clean`

- [ ] **Step 2: Push to GitHub**

```bash
git -C /Users/sjpenn/DEV-SITES/DEMOS/music_renamer push origin main
```

Expected: `Branch 'main' set up to track remote branch 'main' from 'origin'` or `Everything up-to-date`.

---

## Task 16: Railway Deployment

Railway redeploys automatically when the `main` branch receives new commits. Before pushing triggers a deploy, add the following environment variables in the Railway dashboard for this project.

- [ ] **Step 1: Add env vars in Railway dashboard**

Go to your Railway project → Service → Variables tab and add:

| Variable | Value |
|---|---|
| `GOOGLE_CLIENT_ID` | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console |
| `GOOGLE_REDIRECT_URI` | `https://<your-railway-domain>/auth/google/callback` |
| `STRIPE_STARTER_MONTHLY_PRICE_ID` | From Stripe Dashboard (recurring price) |
| `STRIPE_PRO_MONTHLY_PRICE_ID` | From Stripe Dashboard (recurring price) |
| `STRIPE_LABEL_MONTHLY_PRICE_ID` | From Stripe Dashboard (recurring price) |

- [ ] **Step 2: Create Stripe recurring prices (if not done)**

In Stripe Dashboard → Products, create 3 subscription products:
- **Starter** — $9.00/month → copy Price ID → set as `STRIPE_STARTER_MONTHLY_PRICE_ID`
- **Pro** — $29.00/month → copy Price ID → set as `STRIPE_PRO_MONTHLY_PRICE_ID`
- **Label** — $79.00/month → copy Price ID → set as `STRIPE_LABEL_MONTHLY_PRICE_ID`

- [ ] **Step 3: Add Stripe webhook endpoint in Stripe Dashboard**

In Stripe Dashboard → Developers → Webhooks → Add endpoint:
- URL: `https://<your-railway-domain>/api/payments/webhook`
- Events to listen for: `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`, `customer.subscription.updated`
- Copy the signing secret → set as `STRIPE_WEBHOOK_SECRET` in Railway

- [ ] **Step 4: Configure Google OAuth Redirect URI**

In Google Cloud Console → APIs & Services → Credentials → your OAuth 2.0 Client:
- Add authorized redirect URI: `https://<your-railway-domain>/auth/google/callback`

- [ ] **Step 5: Confirm deploy succeeds**

Check Railway deploy logs for a successful startup. Visit `https://<your-railway-domain>` and verify:
- The "Continue with Google" button appears on the auth panel
- Subscription plan cards show monthly pricing
- Existing username/password login still works

---

## Self-Review Checklist

- [x] **Google OAuth routes** — `/auth/google/login` and `/auth/google/callback` covered in Task 8
- [x] **Account linking** — `_resolve_or_create_google_user` with 3 paths: by sub, by email, new user
- [x] **Nullable password_hash** — handled in model (Task 5), bootstrap ALTER TABLE (Task 6), authenticate_user guard (Task 7)
- [x] **Subscription checkout** — `mode="subscription"` + `subscription_data.metadata` (Task 10)
- [x] **invoice.paid webhook** — idempotency via `stripe_invoice_id` unique constraint (Task 10)
- [x] **Subscription cancel** — `POST /api/payments/subscription/cancel` (Task 10)
- [x] **One-time plans unchanged** — existing credit packs still work, `plan_type="one_time"` (Tasks 4, 10)
- [x] **Frontend Google button** — Task 11, hidden when `GOOGLE_CLIENT_ID` not set
- [x] **Frontend subscription UI** — monthly labels, cancel button, subscription status (Task 12)
- [x] **Bootstrap migrations** — all new columns covered via `_ensure_column` + `_run_ddl_safe` (Task 6)
- [x] **GitHub push** — Task 15
- [x] **Railway deploy** — env vars + Stripe webhooks + Google redirect URI (Task 16)
