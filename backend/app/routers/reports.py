"""Team report + reference-tables endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth import get_current_team
from ..db import get_conn
from ..engine_client import get_tables

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports")
def get_report(year: int, quarter: int, ctx: dict = Depends(get_current_team)):
    not_published = JSONResponse(
        status_code=404,
        content={"error": f"Report for Year {year} Quarter {quarter} is not published yet."},
    )
    with get_conn() as conn:
        q = conn.execute(
            """
            SELECT status FROM quarters
            WHERE industry_id = %s AND year = %s AND quarter = %s
            """,
            (ctx["industry_id"], year, quarter),
        ).fetchone()
        if q is None or q["status"] != "published":
            return not_published
        row = conn.execute(
            """
            SELECT report FROM reports
            WHERE team_id = %s AND year = %s AND quarter = %s
            """,
            (ctx["team_id"], year, quarter),
        ).fetchone()
        if row is None or row["report"] is None:
            return not_published
        report = row["report"]
    return report


@router.get("/tables")
def get_reference_tables(ctx: dict = Depends(get_current_team)):
    """Tables 1-23 reference data for the Manual page (SPEC section 5)."""
    return JSONResponse(content=get_tables())
