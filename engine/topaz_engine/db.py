"""PostgreSQL orchestration layer for the Topaz-VBE engine runner.

psycopg (v3) only. All functions take an open connection and do NOT commit —
the caller (topaz_engine.runner.run_quarter) owns transaction boundaries.
Schema per SPEC.md section 3.
"""
from __future__ import annotations

import copy
import os
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from topaz_engine.constants import DEFAULT_DECISIONS

MACRO_DEFAULTS: Dict[str, Any] = {
    "central_bank_rate": 8.0,
    "gdp_growth_pct": 2.5,
    "unemployment_pct": 5.0,
    "inflation_pct": 0,
    "recession": False,
}


def connect() -> "psycopg.Connection":
    """Open a psycopg v3 connection from DATABASE_URL (autocommit off).

    Raises RuntimeError with a clear message when DATABASE_URL is unset.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Export it before running the engine, e.g. "
            "DATABASE_URL=postgresql://user:password@localhost:5432/topaz_vbe"
        )
    return psycopg.connect(dsn, row_factory=dict_row)


def get_industry(conn: "psycopg.Connection", industry_id: int) -> Dict[str, Any]:
    """Return {id, name, simulation_code} for an industry (raises if missing)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, simulation_code FROM industries WHERE id = %s",
            (industry_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"No industry with id={industry_id}")
    return dict(row)


def get_quarter(
    conn: "psycopg.Connection", industry_id: int, year: int, quarter: int
) -> Optional[Dict[str, Any]]:
    """Return the quarter row for (industry, year, quarter), or None."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, industry_id, year, quarter, status, deadline_at, auto_pass_minutes
               FROM quarters
               WHERE industry_id = %s AND year = %s AND quarter = %s""",
            (industry_id, year, quarter),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def set_quarter_status(
    conn: "psycopg.Connection", quarter_id: int, status: str
) -> None:
    """Set a quarter's status; stamps published_at=now() when 'published'."""
    if status not in ("open", "locked", "processing", "published"):
        raise ValueError(f"Invalid quarter status: {status!r}")
    if status == "published":
        conn.execute(
            "UPDATE quarters SET status = %s, published_at = now() WHERE id = %s",
            (status, quarter_id),
        )
    else:
        conn.execute(
            "UPDATE quarters SET status = %s WHERE id = %s", (status, quarter_id)
        )


def get_active_teams(
    conn: "psycopg.Connection", industry_id: int
) -> List[Dict[str, Any]]:
    """Return active teams of an industry, ordered by company_number."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, industry_id, group_number, company_number, identity_number, name
               FROM teams
               WHERE industry_id = %s AND active = true
               ORDER BY company_number""",
            (industry_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_or_autopass_decision(
    conn: "psycopg.Connection",
    team: Dict[str, Any],
    industry_id: int,
    year: int,
    quarter: int,
) -> Tuple[Dict[str, Any], bool]:
    """Return (decisions_dict, auto_passed_bool) for a team.

    Uses the submitted decisions row for this quarter when present; otherwise
    falls back to the team's most recent submitted decisions (any earlier
    quarter) with auto_passed=True; otherwise a deep copy of
    DEFAULT_DECISIONS with auto_passed=True (SPEC section 7 edge case).
    """
    team_id = team["id"]
    with conn.cursor() as cur:
        cur.execute(
            """SELECT data FROM decisions
               WHERE team_id = %s AND industry_id = %s
                 AND year = %s AND quarter = %s AND submitted = true""",
            (team_id, industry_id, year, quarter),
        )
        row = cur.fetchone()
        if row is not None:
            return copy.deepcopy(dict(row)["data"]), False

        cur.execute(
            """SELECT data FROM decisions
               WHERE team_id = %s AND industry_id = %s AND submitted = true
               ORDER BY year DESC, quarter DESC
               LIMIT 1""",
            (team_id, industry_id),
        )
        row = cur.fetchone()
        if row is not None:
            return copy.deepcopy(dict(row)["data"]), True

    return copy.deepcopy(DEFAULT_DECISIONS), True


def get_prev_report(
    conn: "psycopg.Connection",
    team_id: int,
    industry_id: int,
    year: int,
    quarter: int,
) -> Optional[Dict[str, Any]]:
    """Return the latest PUBLISHED report strictly before (year, quarter), or None."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT r.report
               FROM reports r
               JOIN quarters q
                 ON q.industry_id = r.industry_id
                AND q.year = r.year
                AND q.quarter = r.quarter
               WHERE r.team_id = %s AND r.industry_id = %s
                 AND q.status = 'published'
                 AND (r.year < %s OR (r.year = %s AND r.quarter < %s))
               ORDER BY r.year DESC, r.quarter DESC
               LIMIT 1""",
            (team_id, industry_id, year, year, quarter),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return copy.deepcopy(dict(row)["report"])


def get_macro(
    conn: "psycopg.Connection", industry_id: int, year: int, quarter: int
) -> Dict[str, Any]:
    """Return the macro row, or SPEC defaults when no row exists."""
    macro: Dict[str, Any] = dict(MACRO_DEFAULTS)
    with conn.cursor() as cur:
        cur.execute(
            """SELECT central_bank_rate, gdp_growth_pct, unemployment_pct,
                      inflation_pct, recession
               FROM macro
               WHERE industry_id = %s AND year = %s AND quarter = %s""",
            (industry_id, year, quarter),
        )
        row = cur.fetchone()
    if row is not None:
        for key, value in dict(row).items():
            if value is None or key not in macro:
                continue
            macro[key] = bool(value) if isinstance(value, bool) else float(value)
    return macro


def save_report(
    conn: "psycopg.Connection",
    industry_id: int,
    team_id: int,
    year: int,
    quarter: int,
    report: Dict[str, Any],
) -> None:
    """Upsert a team's report row (UNIQUE(team_id, year, quarter))."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO reports (industry_id, team_id, year, quarter, report)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (team_id, year, quarter)
               DO UPDATE SET report = EXCLUDED.report""",
            (industry_id, team_id, year, quarter, Json(report)),
        )


def audit(
    conn: "psycopg.Connection",
    industry_id: int,
    actor: str,
    action: str,
    details: Dict[str, Any],
) -> None:
    """Append a row to the audit log."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log (industry_id, actor, action, details) "
            "VALUES (%s, %s, %s, %s)",
            (industry_id, actor, action, Json(details)),
        )
