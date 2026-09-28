"""Engine quarter runner: DB-orchestrated deterministic batch roll.

Implements SPEC.md section 8 (Engine quarter flow): loads the quarter,
industry, macro and all active teams, applies the auto-pass fallback for
missing decisions, runs the pure simulation core, persists one report per
team, publishes the quarter, and audits the roll.

Per SPEC section 7, decision validation is the backend's job; the engine
assumes valid decisions. Determinism lives in topaz_engine.simulation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from topaz_engine import db
from topaz_engine.simulation import compute_quarter

ROLLABLE_STATUSES = ("open", "locked")


def run_quarter(industry_id: int, year: int, quarter: int) -> Dict[str, Any]:
    """Simulate and publish one quarter. Returns a summary dict.

    Raises ValueError when the quarter does not exist, has no rollable status,
    or the industry has no active teams; raises RuntimeError when
    DATABASE_URL is unset. On failure the quarter is restored to 'locked'
    (transaction rolled back) and the original exception is re-raised.
    """
    conn = db.connect()
    try:
        q = db.get_quarter(conn, industry_id, year, quarter)
        if q is None:
            raise ValueError(
                f"No quarter found for industry {industry_id} "
                f"year {year} quarter {quarter}"
            )
        if q["status"] not in ROLLABLE_STATUSES:
            raise ValueError(
                f"Cannot roll year {year} quarter {quarter}: "
                f"status is {q['status']!r} (must be one of {ROLLABLE_STATUSES})"
            )
        quarter_id = q["id"]

        db.set_quarter_status(conn, quarter_id, "processing")
        try:
            industry = db.get_industry(conn, industry_id)
            macro = db.get_macro(conn, industry_id, year, quarter)
            teams = db.get_active_teams(conn, industry_id)
            if not teams:
                raise ValueError(
                    f"Cannot roll year {year} quarter {quarter}: "
                    f"industry {industry_id} has no active teams"
                )

            team_items: List[Dict[str, Any]] = []
            for team in teams:
                decisions, auto_passed = db.get_or_autopass_decision(
                    conn, team, industry_id, year, quarter
                )
                prev = db.get_prev_report(
                    conn, team["id"], industry_id, year, quarter
                )
                team_items.append(
                    {
                        "team_id": team["id"],
                        "team": {
                            "company_number": team["company_number"],
                            "name": team["name"],
                            "group_number": team["group_number"],
                        },
                        "decisions": decisions,
                        "prev": prev,
                        "auto_pass": auto_passed,
                    }
                )

            reports = compute_quarter(industry, year, quarter, team_items, macro)
            for team in teams:
                db.save_report(
                    conn, industry_id, team["id"], year, quarter, reports[team["id"]]
                )

            db.set_quarter_status(conn, quarter_id, "published")

            auto_passed_numbers = [
                item["team"]["company_number"]
                for item in team_items
                if item["auto_pass"]
            ]
            details = {
                "year": year,
                "quarter": quarter,
                "teams_processed": len(teams),
                "auto_passed": auto_passed_numbers,
            }
            db.audit(conn, industry_id, "engine", "roll_quarter", details)

            conn.commit()
            return {
                "year": year,
                "quarter": quarter,
                "teams_processed": len(teams),
                "auto_passed": auto_passed_numbers,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            conn.rollback()
            # Best-effort restore: the failed roll leaves the quarter re-rollable.
            try:
                db.set_quarter_status(conn, quarter_id, "locked")
                conn.commit()
            except Exception:
                conn.rollback()
            raise
    finally:
        conn.close()
