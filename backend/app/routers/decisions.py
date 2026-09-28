"""Team decision endpoints (SPEC section 4).

PUT /api/decisions/current always stores the draft, but returns 422 with
errors[] when validation fails (the frontend shows errors yet keeps the
draft). Only 200 carries {ok:true, warnings:[]}.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from psycopg.types.json import Json

from ..auth import get_current_team
from ..db import get_conn
from ..engine_client import (
    EngineError,
    get_available_funds,
    get_default_decisions,
    validate_with_warnings,
)
from ..schemas import DecisionPut
from ._common import audit, current_quarter, get_decision_row, iso, utcnow

router = APIRouter(prefix="/api", tags=["decisions"])

_NOT_OPEN = "Quarter is no longer open for submissions."
_ALREADY_SUBMITTED = "Decisions already submitted for this quarter."


def _quarter_or_404(conn, industry_id: int):
    q = current_quarter(conn, industry_id)
    if q is None:
        return None, JSONResponse(
            status_code=404, content={"error": "No current quarter for this industry."}
        )
    return q, None


@router.get("/me")
def me(ctx: dict = Depends(get_current_team)):
    team, industry = ctx["team"], ctx["industry"]
    with get_conn() as conn:
        q = current_quarter(conn, industry["id"])
        submitted = False
        if q is not None:
            d = get_decision_row(conn, team["id"], q["year"], q["quarter"])
            submitted = bool(d and d["submitted"])
    current = (
        {
            "year": q["year"],
            "quarter": q["quarter"],
            "status": q["status"],
            "deadline_at": iso(q["deadline_at"]),
        }
        if q is not None
        else None
    )
    return {
        "team": {
            "id": team["id"],
            "name": team["name"],
            "group_number": team["group_number"],
            "company_number": team["company_number"],
        },
        "industry": {
            "id": industry["id"],
            "name": industry["name"],
            "simulation_code": industry["simulation_code"],
        },
        "current_quarter": current,
        "submitted": submitted,
    }


@router.get("/quarters")
def list_quarters(ctx: dict = Depends(get_current_team)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT year, quarter, status FROM quarters
            WHERE industry_id = %s
            ORDER BY year ASC, quarter ASC
            """,
            (ctx["industry_id"],),
        ).fetchall()
    return [{"year": r["year"], "quarter": r["quarter"], "status": r["status"]} for r in rows]


@router.get("/decisions/current")
def get_current_decisions(ctx: dict = Depends(get_current_team)):
    with get_conn() as conn:
        q, err = _quarter_or_404(conn, ctx["industry_id"])
        if err is not None:
            return err
        d = get_decision_row(conn, ctx["team_id"], q["year"], q["quarter"])
    return {
        "year": q["year"],
        "quarter": q["quarter"],
        "submitted": bool(d and d["submitted"]),
        "submitted_at": iso(d["submitted_at"]) if d else None,
        "auto_pass": bool(d and d["auto_pass"]),
        "data": d["data"] if d else None,
    }


def _upsert_draft(conn, team_id: int, industry_id: int, year: int, quarter: int,
                  data: dict, *, reset_submission: bool):
    now = utcnow()
    existing = get_decision_row(conn, team_id, year, quarter)
    if existing is None:
        conn.execute(
            """
            INSERT INTO decisions (industry_id, team_id, year, quarter, data,
                                   submitted, submitted_at, auto_pass, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, false, NULL, false, %s, %s)
            """,
            (industry_id, team_id, year, quarter, Json(data), now, now),
        )
    else:
        if reset_submission:
            conn.execute(
                """
                UPDATE decisions
                SET data = %s, submitted = false, submitted_at = NULL,
                    auto_pass = false, updated_at = %s
                WHERE id = %s
                """,
                (Json(data), now, existing["id"]),
            )
        else:
            conn.execute(
                "UPDATE decisions SET data = %s, updated_at = %s WHERE id = %s",
                (Json(data), now, existing["id"]),
            )


@router.put("/decisions/current")
def put_current_decisions(body: DecisionPut, ctx: dict = Depends(get_current_team)):
    with get_conn() as conn:
        q, err = _quarter_or_404(conn, ctx["industry_id"])
        if err is not None:
            return err
        if q["status"] != "open":
            return JSONResponse(status_code=409, content={"ok": False, "error": _NOT_OPEN})
        existing = get_decision_row(conn, ctx["team_id"], q["year"], q["quarter"])
        if existing and existing["submitted"]:
            return JSONResponse(
                status_code=409, content={"ok": False, "error": _ALREADY_SUBMITTED}
            )
        funds = get_available_funds(ctx["team_id"])
        try:
            errors, warnings = validate_with_warnings(body.data, funds)
        except EngineError as exc:
            return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})
        # Draft is ALWAYS stored; validation only decides the status code.
        _upsert_draft(conn, ctx["team_id"], ctx["industry_id"], q["year"], q["quarter"],
                      body.data, reset_submission=False)
    if errors:
        return JSONResponse(status_code=422, content={"ok": False, "errors": errors})
    return {"ok": True, "warnings": warnings}


@router.post("/decisions/current/reset")
def reset_current_decisions(ctx: dict = Depends(get_current_team)):
    with get_conn() as conn:
        q, err = _quarter_or_404(conn, ctx["industry_id"])
        if err is not None:
            return err
        if q["status"] != "open":
            return JSONResponse(status_code=409, content={"ok": False, "error": _NOT_OPEN})
        existing = get_decision_row(conn, ctx["team_id"], q["year"], q["quarter"])
        if existing and existing["submitted"]:
            return JSONResponse(
                status_code=409, content={"ok": False, "error": _ALREADY_SUBMITTED}
            )
        defaults = get_default_decisions()
        _upsert_draft(conn, ctx["team_id"], ctx["industry_id"], q["year"], q["quarter"],
                      defaults, reset_submission=True)
    return {"ok": True, "data": defaults}


@router.post("/decisions/current/submit")
def submit_current_decisions(ctx: dict = Depends(get_current_team)):
    with get_conn() as conn:
        q, err = _quarter_or_404(conn, ctx["industry_id"])
        if err is not None:
            return err
        if q["status"] != "open":
            return JSONResponse(status_code=409, content={"ok": False, "error": _NOT_OPEN})
        existing = get_decision_row(conn, ctx["team_id"], q["year"], q["quarter"])
        if existing and existing["submitted"]:
            return JSONResponse(
                status_code=409, content={"ok": False, "error": _ALREADY_SUBMITTED}
            )
        data = existing["data"] if existing else get_default_decisions()
        funds = get_available_funds(ctx["team_id"])
        try:
            errors, _warnings = validate_with_warnings(data, funds)
        except EngineError as exc:
            return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})
        if errors:
            # Keep the draft stored but refuse submission.
            _upsert_draft(conn, ctx["team_id"], ctx["industry_id"], q["year"],
                          q["quarter"], data, reset_submission=False)
            return JSONResponse(status_code=422, content={"ok": False, "errors": errors})
        now = utcnow()
        if existing is None:
            conn.execute(
                """
                INSERT INTO decisions (industry_id, team_id, year, quarter, data,
                                       submitted, submitted_at, auto_pass, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, true, %s, false, %s, %s)
                """,
                (ctx["industry_id"], ctx["team_id"], q["year"], q["quarter"],
                 Json(data), now, now, now),
            )
        else:
            conn.execute(
                "UPDATE decisions SET submitted = true, submitted_at = %s, updated_at = %s WHERE id = %s",
                (now, now, existing["id"]),
            )
        audit(conn, ctx["industry_id"], f"team:{ctx['team_id']}", "decisions.submit",
              {"year": q["year"], "quarter": q["quarter"]})
    confirmation = (
        f"Decisions for Year {q['year']} Quarter {q['quarter']} submitted at "
        f"{iso(now)}. Status: LOCKED \u2014 awaiting quarter processing."
    )
    return {"ok": True, "confirmation": confirmation}
