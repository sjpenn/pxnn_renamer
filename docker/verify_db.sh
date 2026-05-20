#!/usr/bin/env bash
# One-shot psql verification of DATABASE_URL: lists databases and current DB.
# Output goes to container stdout for capture via `coolify logs`.
set -u

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "verify_db: DATABASE_URL empty, skipping"
  exit 0
fi

echo "===== verify_db: psql \\l ====="
psql "$DATABASE_URL" -c "\l" 2>&1 || echo "verify_db: psql \\l failed"

echo "===== verify_db: identity + version ====="
psql "$DATABASE_URL" -c "SELECT current_database() AS db, current_user AS usr, inet_server_addr() AS host, version();" 2>&1 || echo "verify_db: identity query failed"

echo "===== verify_db: done ====="
