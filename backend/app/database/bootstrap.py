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

    # Users — admin flag
    _ensure_column("users", "is_admin", "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
    _ensure_column("users", "is_testing", "ALTER TABLE users ADD COLUMN is_testing BOOLEAN DEFAULT FALSE")

    # Make password_hash nullable on existing PostgreSQL deployments
    _run_ddl_safe("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")

    # Add unique index for google_sub (partial index — only non-NULL values)
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

    # Announcements — Phase 1 admin feature
    _ensure_column("announcements", "target_funnel_stage", "ALTER TABLE announcements ADD COLUMN target_funnel_stage TEXT")
    _ensure_column("announcements", "target_plan_status", "ALTER TABLE announcements ADD COLUMN target_plan_status TEXT")

    # UserSession table is handled by create_all above — no migration helper needed.

    # UIComment table is handled by create_all above — no migration helper needed.

    # Promote configured admin email (idempotent)
    from .models import User as _UserModel
    from ..core.config import settings as _settings

    email = (_settings.ADMIN_BOOTSTRAP_EMAIL or "").strip().lower()
    if email:
        from sqlalchemy.orm import Session as _Session
        db = _Session(bind=engine)
        try:
            match = (
                db.query(_UserModel)
                .filter(_UserModel.email.ilike(email))
                .first()
            )
            if match and not match.is_admin:
                match.is_admin = True
                db.commit()
        finally:
            db.close()
