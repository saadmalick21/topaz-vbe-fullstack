"""Admin endpoints (SPEC section 4). Every mutation writes an audit_log row."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta

import psycopg
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from psycopg.types.json import Json

from ..auth import get_current_admin
from ..db import get_conn
from ..engine_client import EngineError, run_engine_subprocess
from ..schemas import IndustryCreate, QuarterCreate, RollQuarterRequest, ShockUpsert, TeamCreate
from ._common import audit, current_quarter, iso, utcnow

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Quarter-roll execution mode (SPEC section 8):
#   "sync"  (default) — the API runs the engine as a subprocess and waits.
#   "queue"           — the API only locks the quarter and inserts a pending
#                       row into quarter_jobs (202 Accepted); the
#                       engine-worker service claims it and runs the batch.
ROLL_MODE = os.environ.get("QUARTER_ROLL_MODE", "sync").strip().lower()


def _industry_or_none(conn, industry_id: int):
    return conn.execute("SELECT * FROM industries WHERE id = %s", (industry_id,)).fetchone()


def _actor(admin: dict) -> str:
    return f"admin:{admin['username']}"


def _new_identity_number(conn) -> str:
    """Generate "ID-" + 4 random digits, guaranteed unique."""
    for _ in range(100):
        candidate = f"ID-{secrets.randbelow(9000) + 1000:04d}"
        exists = conn.execute(
            "SELECT 1 FROM teams WHERE identity_number = %s", (candidate,)
        ).fetchone()
        if exists is None:
            return candidate
    raise RuntimeError("Could not generate a unique identity number")


def _quarter_summary(conn, industry_id: int):
    q = current_quarter(conn, industry_id)
    if q is None:
        return None
    return {"year": q["year"], "quarter": q["quarter"], "status": q["status"]}


# ---------------------------------------------------------------- industries

@router.get("/industries")
def list_industries(admin: dict = Depends(get_current_admin)):
    with get_conn() as conn:
        industries = conn.execute(
            "SELECT * FROM industries ORDER BY id ASC"
        ).fetchall()
        out = []
        for ind in industries:
            team_count = conn.execute(
                "SELECT COUNT(*) AS c FROM teams WHERE industry_id = %s",
                (ind["id"],),
            ).fetchone()["c"]
            out.append(
                {
                    "id": ind["id"],
                    "name": ind["name"],
                    "simulation_code": ind["simulation_code"],
                    "status": ind["status"],
                    "team_count": team_count,
                    "current_quarter": _quarter_summary(conn, ind["id"]),
                }
            )
    return out


@router.post("/industries", status_code=201)
def create_industry(body: IndustryCreate, admin: dict = Depends(get_current_admin)):
    with get_conn() as conn:
        try:
            row = conn.execute(
                """
                INSERT INTO industries (name, simulation_code, status)
                VALUES (%s, %s, 'active') RETURNING *
                """,
                (body.name, body.simulation_code),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            return JSONResponse(
                status_code=409,
                content={"error": "An industry with this simulation_code already exists."},
            )
        audit(conn, row["id"], _actor(admin), "industry.create",
              {"name": row["name"], "simulation_code": row["simulation_code"]})
    return {
        "id": row["id"],
        "name": row["name"],
        "simulation_code": row["simulation_code"],
        "status": row["status"],
        "team_count": 0,
        "current_quarter": None,
    }


@router.get("/industries/{industry_id}")
def get_industry(industry_id: int, admin: dict = Depends(get_current_admin)):
    with get_conn() as conn:
        ind = _industry_or_none(conn, industry_id)
        if ind is None:
            return JSONResponse(status_code=404, content={"error": "Industry not found."})
        teams = conn.execute(
            """
            SELECT id, name, group_number, company_number, identity_number, active
            FROM teams WHERE industry_id = %s ORDER BY company_number ASC
            """,
            (industry_id,),
        ).fetchall()
        quarters = conn.execute(
            """
            SELECT id, year, quarter, status, auto_pass_minutes, deadline_at, published_at
            FROM quarters WHERE industry_id = %s ORDER BY year ASC, quarter ASC
            """,
            (industry_id,),
        ).fetchall()
        macro = conn.execute(
            "SELECT * FROM macro WHERE industry_id = %s ORDER BY year ASC, quarter ASC",
            (industry_id,),
        ).fetchall()
    return {
        "industry": {
            "id": ind["id"],
            "name": ind["name"],
            "simulation_code": ind["simulation_code"],
            "status": ind["status"],
            "created_at": iso(ind["created_at"]),
        },
        "teams": [
            {
                "id": t["id"],
                "name": t["name"],
                "group_number": t["group_number"],
                "company_number": t["company_number"],
                "identity_number": t["identity_number"],
                "active": t["active"],
            }
            for t in teams
        ],
        "quarters": [
            {
                "id": q_["id"],
                "year": q_["year"],
                "quarter": q_["quarter"],
                "status": q_["status"],
                "auto_pass_minutes": q_["auto_pass_minutes"],
                "deadline_at": iso(q_["deadline_at"]),
                "published_at": iso(q_["published_at"]),
            }
            for q_ in quarters
        ],
        "macro": [
            {
                "id": m["id"],
                "year": m["year"],
                "quarter": m["quarter"],
                "inflation_pct": float(m["inflation_pct"]) if m["inflation_pct"] is not None else None,
                "material_price_change_pct": (
                    float(m["material_price_change_pct"])
                    if m["material_price_change_pct"] is not None else None
                ),
                "recession": m["recession"],
                "note": m["note"],
                "central_bank_rate": float(m["central_bank_rate"]) if m["central_bank_rate"] is not None else None,
                "gdp_growth_pct": float(m["gdp_growth_pct"]) if m["gdp_growth_pct"] is not None else None,
                "unemployment_pct": float(m["unemployment_pct"]) if m["unemployment_pct"] is not None else None,
            }
            for m in macro
        ],
    }


# ---------------------------------------------------------------- teams

@router.post("/industries/{industry_id}/teams", status_code=201)
def create_team(industry_id: int, body: TeamCreate, admin: dict = Depends(get_current_admin)):
    with get_conn() as conn:
        ind = _industry_or_none(conn, industry_id)
        if ind is None:
            return JSONResponse(status_code=404, content={"error": "Industry not found."})
        dup = conn.execute(
            """
            SELECT 1 FROM teams
            WHERE industry_id = %s AND group_number = %s AND company_number = %s
            """,
            (industry_id, body.group_number, body.company_number),
        ).fetchone()
        if dup is not None:
            return JSONResponse(
                status_code=409,
                content={"error": "A team with this group/company number already exists."},
            )
        identity_number = _new_identity_number(conn)
        row = conn.execute(
            """
            INSERT INTO teams (industry_id, group_number, company_number,
                               identity_number, name, active)
            VALUES (%s, %s, %s, %s, %s, true) RETURNING *
            """,
            (industry_id, body.group_number, body.company_number,
             identity_number, body.name),
        ).fetchone()
        audit(conn, industry_id, _actor(admin), "team.create",
              {"team_id": row["id"], "company_number": row["company_number"],
               "name": row["name"]})
    return {
        "id": row["id"],
        "name": row["name"],
        "group_number": row["group_number"],
        "company_number": row["company_number"],
        "identity_number": row["identity_number"],
        "active": row["active"],
    }


# ---------------------------------------------------------------- quarters

@router.post("/industries/{industry_id}/quarters", status_code=201)
def create_quarter(industry_id: int, body: QuarterCreate, admin: dict = Depends(get_current_admin)):
    now = utcnow()
    deadline_at = (
        now + timedelta(minutes=body.auto_pass_minutes)
        if body.auto_pass_minutes is not None
        else None
    )
    with get_conn() as conn:
        ind = _industry_or_none(conn, industry_id)
        if ind is None:
            return JSONResponse(status_code=404, content={"error": "Industry not found."})
        unfinished = conn.execute(
            """
            SELECT 1 FROM quarters
            WHERE industry_id = %s AND status IN ('open', 'locked', 'processing')
            LIMIT 1
            """,
            (industry_id,),
        ).fetchone()
        if unfinished is not None:
            return JSONResponse(
                status_code=409,
                content={"error": "Previous quarter must be published before opening a new one."},
            )
        try:
            row = conn.execute(
                """
                INSERT INTO quarters (industry_id, year, quarter, status,
                                      auto_pass_minutes, deadline_at)
                VALUES (%s, %s, %s, 'open', %s, %s) RETURNING *
                """,
                (industry_id, body.year, body.quarter,
                 body.auto_pass_minutes if body.auto_pass_minutes is not None else 10080,
                 deadline_at),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            return JSONResponse(
                status_code=409,
                content={"error": "This quarter already exists for the industry."},
            )
        audit(conn, industry_id, _actor(admin), "quarter.create",
              {"year": row["year"], "quarter": row["quarter"]})
    return {
        "id": row["id"],
        "industry_id": row["industry_id"],
        "year": row["year"],
        "quarter": row["quarter"],
        "status": row["status"],
        "auto_pass_minutes": row["auto_pass_minutes"],
        "deadline_at": iso(row["deadline_at"]),
    }


# ---------------------------------------------------------------- shocks

@router.post("/industries/{industry_id}/shocks")
def upsert_shock(industry_id: int, body: ShockUpsert, admin: dict = Depends(get_current_admin)):
    with get_conn() as conn:
        ind = _industry_or_none(conn, industry_id)
        if ind is None:
            return JSONResponse(status_code=404, content={"error": "Industry not found."})
        row = conn.execute(
            """
            INSERT INTO macro (industry_id, year, quarter, inflation_pct,
                               material_price_change_pct, recession, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (industry_id, year, quarter) DO UPDATE SET
                inflation_pct = COALESCE(EXCLUDED.inflation_pct, macro.inflation_pct),
                material_price_change_pct = COALESCE(EXCLUDED.material_price_change_pct,
                                                     macro.material_price_change_pct),
                recession = COALESCE(EXCLUDED.recession, macro.recession),
                note = COALESCE(EXCLUDED.note, macro.note)
            RETURNING *
            """,
            (industry_id, body.year, body.quarter, body.inflation_pct,
             body.material_price_change_pct, body.recession, body.note),
        ).fetchone()
        audit(conn, industry_id, _actor(admin), "shock.upsert",
              {"year": row["year"], "quarter": row["quarter"]})
    return {
        "ok": True,
        "macro": {
            "id": row["id"],
            "year": row["year"],
            "quarter": row["quarter"],
            "inflation_pct": float(row["inflation_pct"]) if row["inflation_pct"] is not None else None,
            "material_price_change_pct": (
                float(row["material_price_change_pct"])
                if row["material_price_change_pct"] is not None else None
            ),
            "recession": row["recession"],
            "note": row["note"],
        },
    }


# ---------------------------------------------------------------- roll

def _roll_teams(conn, industry_id: int, year: int, quarter: int):
    rows = conn.execute(
        """
        SELECT t.id, t.company_number, t.name,
               d.submitted AS submitted, d.submitted_at AS submitted_at
        FROM teams t
        LEFT JOIN decisions d ON d.team_id = t.id AND d.year = %s AND d.quarter = %s
        WHERE t.industry_id = %s AND t.active = true
        ORDER BY t.company_number ASC
        """,
        (year, quarter, industry_id),
    ).fetchall()
    return [
        {
            "company_number": r["company_number"],
            "name": r["name"],
            "submitted": bool(r["submitted"]),
            "submitted_at": iso(r["submitted_at"]),
        }
        for r in rows
    ]


@router.get("/industries/{industry_id}/roll-status")
def roll_status(industry_id: int, admin: dict = Depends(get_current_admin)):
    with get_conn() as conn:
        ind = _industry_or_none(conn, industry_id)
        if ind is None:
            return JSONResponse(status_code=404, content={"error": "Industry not found."})
        q = current_quarter(conn, industry_id)
        if q is None:
            return JSONResponse(status_code=404, content={"error": "No quarter to roll."})
        teams = _roll_teams(conn, industry_id, q["year"], q["quarter"])
        try:
            job = conn.execute(
                """
                SELECT id, status, attempts, error, created_at, updated_at
                FROM quarter_jobs
                WHERE industry_id = %s AND year = %s AND quarter = %s
                """,
                (industry_id, q["year"], q["quarter"]),
            ).fetchone()
        except Exception:
            # Migration 003 not applied yet: queue mode unavailable, but the
            # sync roll flow must keep working.
            conn.rollback()
            job = None
        deadline_at = q["deadline_at"]
        deadline_passed = (
            deadline_at is not None and utcnow() >= deadline_at
        )
    return {
        "year": q["year"],
        "quarter": q["quarter"],
        "status": q["status"],
        "deadline_at": iso(deadline_at),
        "all_submitted": all(t["submitted"] for t in teams),
        "deadline_passed": deadline_passed,
        "teams": teams,
        "roll_mode": ROLL_MODE,
        "job": (
            {
                "id": job["id"],
                "status": job["status"],
                "attempts": job["attempts"],
                "error": job["error"],
                "created_at": iso(job["created_at"]),
                "updated_at": iso(job["updated_at"]),
            }
            if job else None
        ),
    }


@router.post("/industries/{industry_id}/roll-quarter")
def roll_quarter(industry_id: int, body: RollQuarterRequest,
                 admin: dict = Depends(get_current_admin)):
    actor = _actor(admin)
    with get_conn() as conn:
        ind = _industry_or_none(conn, industry_id)
        if ind is None:
            return JSONResponse(status_code=404, content={"error": "Industry not found."})
        q = current_quarter(conn, industry_id)
        if q is None:
            return JSONResponse(status_code=404, content={"error": "No quarter to roll."})
        if q["status"] not in ("open", "locked"):
            return JSONResponse(
                status_code=409,
                content={"ok": False,
                         "error": f"Quarter cannot be rolled while status is '{q['status']}'."},
            )
        year, quarter = q["year"], q["quarter"]
        teams = _roll_teams(conn, industry_id, year, quarter)
        missing = [t for t in teams if not t["submitted"]]
        deadline_at = q["deadline_at"]
        now = utcnow()
        deadline_passed = deadline_at is not None and now >= deadline_at

        if missing and not body.force and (deadline_at is None or not deadline_passed):
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": f"Deadlock guard: {len(missing)} team(s) have not submitted.",
                    "missing": [
                        {"company_number": t["company_number"], "name": t["name"]}
                        for t in missing
                    ],
                    "deadline_at": iso(deadline_at),
                },
            )

        auto_passed = [t["company_number"] for t in missing]
        conn.execute("UPDATE quarters SET status = 'locked' WHERE id = %s", (q["id"],))
        audit(conn, industry_id, actor, "quarter.roll.lock",
              {"year": year, "quarter": quarter, "auto_passed": auto_passed})

        if ROLL_MODE == "queue":
            # Event-driven path: enqueue the batch for the engine worker and
            # return immediately. Idempotent: re-rolling while a job is
            # pending/running returns the existing job instead of duplicating.
            try:
                job = conn.execute(
                    """
                    INSERT INTO quarter_jobs (industry_id, year, quarter, auto_passed)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (industry_id, year, quarter) DO NOTHING
                    RETURNING id, status
                    """,
                    (industry_id, year, quarter, Json(auto_passed)),
                ).fetchone()
                if job is None:
                    job = conn.execute(
                        "SELECT id, status FROM quarter_jobs "
                        "WHERE industry_id = %s AND year = %s AND quarter = %s",
                        (industry_id, year, quarter),
                    ).fetchone()
            except Exception as exc:
                conn.rollback()
                return JSONResponse(
                    status_code=500,
                    content={
                        "ok": False,
                        "error": "Queue mode needs migration 003 (quarter_jobs table): "
                                 + str(exc),
                    },
                )
            audit(conn, industry_id, actor, "quarter.roll.queued",
                  {"year": year, "quarter": quarter, "job_id": job["id"],
                   "auto_passed": auto_passed})
            status_code = 202 if job["status"] in ("pending", "running") else 200
            return JSONResponse(
                status_code=status_code,
                content={
                    "ok": True,
                    "queued": True,
                    "job": {"id": job["id"], "status": job["status"]},
                    "summary": {
                        "year": year, "quarter": quarter,
                        "teams_processed": len(teams),
                        "auto_passed": auto_passed,
                    },
                },
            )

    # Run the engine outside the pooled connection so a long simulation does
    # not hold a DB connection. The runner owns the 'processing' -> 'published'
    # transition itself (it rejects quarters already marked 'processing'),
    # so the API must NOT set 'processing' here first.
    try:
        run_engine_subprocess(industry_id, year, quarter)
    except EngineError as exc:
        with get_conn() as conn:
            conn.execute("UPDATE quarters SET status = 'locked' WHERE id = %s", (q["id"],))
            audit(conn, industry_id, actor, "quarter.roll.failed",
                  {"year": year, "quarter": quarter, "error": str(exc)})
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})

    with get_conn() as conn:
        published = conn.execute(
            "SELECT published_at FROM quarters WHERE id = %s", (q["id"],)
        ).fetchone()
        audit(conn, industry_id, actor, "quarter.roll.published",
              {"year": year, "quarter": quarter, "teams_processed": len(teams),
               "auto_passed": auto_passed})
    return {
        "ok": True,
        "summary": {
            "year": year,
            "quarter": quarter,
            "teams_processed": len(teams),
            "auto_passed": auto_passed,
            "published_at": iso(published["published_at"]) if published else None,
        },
    }


# ---------------------------------------------------------------- audit

@router.get("/audit")
def list_audit(admin: dict = Depends(get_current_admin)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, industry_id, actor, action, details, created_at
            FROM audit_log ORDER BY id DESC LIMIT 500
            """
        ).fetchall()
    return [
        {
            "id": r["id"],
            "industry_id": r["industry_id"],
            "actor": r["actor"],
            "action": r["action"],
            "details": r["details"],
            "created_at": iso(r["created_at"]),
        }
        for r in rows
    ]
