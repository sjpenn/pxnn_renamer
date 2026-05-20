"""Create target Postgres database if missing. Idempotent.

Reads DATABASE_URL, connects to the server's default 'postgres' db,
and issues CREATE DATABASE only when the target db doesn't exist.
No-op for non-postgres URLs.
"""
import os
import sys
from urllib.parse import urlparse, urlunparse

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ensure_db: DATABASE_URL not set, skipping", flush=True)
        return 0

    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgres"):
        print(f"ensure_db: non-postgres scheme '{parsed.scheme}', skipping", flush=True)
        return 0

    target_db = (parsed.path or "/").lstrip("/")
    if not target_db:
        print("ensure_db: no db in URL path, skipping", flush=True)
        return 0

    admin = parsed._replace(path="/postgres")
    admin_url = urlunparse(admin)

    try:
        conn = psycopg2.connect(admin_url, connect_timeout=10)
    except Exception as exc:
        print(f"ensure_db: admin connect failed: {exc}", flush=True)
        return 0

    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
        if cur.fetchone():
            print(f"ensure_db: '{target_db}' exists", flush=True)
        else:
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db))
            )
            print(f"ensure_db: created '{target_db}'", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
