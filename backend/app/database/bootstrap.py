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


def bootstrap_database() -> None:
    Base.metadata.create_all(bind=engine)

    _ensure_column("users", "stripe_customer_id", "ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    _ensure_column("users", "credit_balance", "ALTER TABLE users ADD COLUMN credit_balance INTEGER DEFAULT 0")
    _ensure_column("users", "active_plan", "ALTER TABLE users ADD COLUMN active_plan TEXT DEFAULT 'free'")
    _ensure_column("users", "plan_status", "ALTER TABLE users ADD COLUMN plan_status TEXT DEFAULT 'inactive'")

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

    _ensure_column("files", "external_id", "ALTER TABLE files ADD COLUMN external_id TEXT")
    _ensure_column("files", "extracted_json", "ALTER TABLE files ADD COLUMN extracted_json TEXT")
    _ensure_column("files", "resolved_json", "ALTER TABLE files ADD COLUMN resolved_json TEXT")
    _ensure_column("files", "created_at", "ALTER TABLE files ADD COLUMN created_at TIMESTAMP")

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
                "ON payment_records (stripe_checkout_session_id)"
            )
        )
