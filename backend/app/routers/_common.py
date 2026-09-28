"""Shared helpers for routers."""

from __future__ import annotations

from datetime import datetime, timezone

from psycopg.types.json import Json


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def current_quarter(conn, industry_id: int):
    """Latest quarter row for an industry (max year, then quarter), or None."""
    return conn.execute(
        """
        SELECT * FROM quarters
        WHERE industry_id = %s
        ORDER BY year DESC, quarter DESC
        LIMIT 1
        """,
        (industry_id,),
    ).fetchone()


def get_decision_row(conn, team_id: int, year: int, quarter: int):
    return conn.execute(
        """
        SELECT * FROM decisions
        WHERE team_id = %s AND year = %s AND quarter = %s
        """,
        (team_id, year, quarter),
    ).fetchone()


def audit(conn, industry_id: int | None, actor: str, action: str, details: dict | None = None):
    conn.execute(
        "INSERT INTO audit_log (industry_id, actor, action, details) VALUES (%s, %s, %s, %s)",
        (industry_id, actor, action, Json(details or {})),
    )
