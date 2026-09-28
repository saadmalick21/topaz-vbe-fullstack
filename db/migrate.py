#!/usr/bin/env python3
"""Apply pending SQL migrations in db/migrations/ in filename order.

Tracks what has been applied in the schema_migrations table, so it is safe
to run on every deploy (docker-compose runs it as a one-shot `migrate`
service before the API starts).

Usage:
    DATABASE_URL=postgresql://... python db/migrate.py
    # or: docker compose run --rm migrate
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    sys.exit("psycopg is required: pip install 'psycopg[binary]'")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL environment variable is not set")

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        sys.exit(f"No migration files found in {MIGRATIONS_DIR}")

    # autocommit=True because the migration files manage their own
    # transactions (they contain BEGIN; ... COMMIT; blocks).
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename   TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            r[0] for r in conn.execute("SELECT filename FROM schema_migrations")
        }
        for path in files:
            if path.name in applied:
                print(f"  skip  {path.name} (already applied)")
                continue
            print(f"  apply {path.name} ...")
            sql = path.read_text(encoding="utf-8")
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (path.name,),
            )
            print(f"  done  {path.name}")
    print("migrations up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
