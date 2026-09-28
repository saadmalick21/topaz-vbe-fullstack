"""Engine worker: event-driven quarter-roll consumer.

Polls the ``quarter_jobs`` table, claims one ``pending`` job at a time with
``SELECT ... FOR UPDATE SKIP LOCKED`` (so any number of worker replicas can
run without double-processing), and executes the deterministic batch via
:func:`topaz_engine.runner.run_quarter`.

Environment:
    DATABASE_URL          PostgreSQL connection string (required)
    WORKER_POLL_SECONDS   idle sleep between polls (default 5)
    WORKER_ID             human-readable owner tag for claimed jobs
                          (default: hostname-pid)

Usage:
    python -m topaz_engine.worker            # run forever
    python -m topaz_engine.worker --once     # process one job then exit
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import time
import traceback

import psycopg
from psycopg.rows import dict_row

from topaz_engine import runner

log = logging.getLogger("topaz.worker")

CLAIM_SQL = """
UPDATE quarter_jobs
SET status = 'running',
    locked_by = %s,
    locked_at = now(),
    attempts = attempts + 1,
    updated_at = now()
WHERE id = (
    SELECT id FROM quarter_jobs
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING id, industry_id, year, quarter, attempts, auto_passed
"""

FINISH_SQL = """
UPDATE quarter_jobs
SET status = %s, error = %s, updated_at = now()
WHERE id = %s
"""


def _connect():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg.connect(database_url, row_factory=dict_row)


def _audit(conn, industry_id, actor, action, detail):
    conn.execute(
        "INSERT INTO audit_log (industry_id, actor, action, details) "
        "VALUES (%s, %s, %s, %s)",
        (industry_id, actor, action, psycopg.types.json.Json(detail)),
    )


def process_one(worker_id: str) -> bool:
    """Claim and run a single pending job. Returns True if a job was found."""
    with _connect() as conn:
        with conn.transaction():
            job = conn.execute(CLAIM_SQL, (worker_id,)).fetchone()
        if job is None:
            return False
        jid, ind, year, qtr = (job["id"], job["industry_id"],
                              job["year"], job["quarter"])
        log.info("worker %s claimed job %s (industry %s Y%sQ%s, attempt %s)",
                 worker_id, jid, ind, year, qtr, job["attempts"])
        try:
            summary = runner.run_quarter(ind, year, qtr)
        except Exception as exc:  # noqa: BLE001 - must mark the job failed
            err = f"{type(exc).__name__}: {exc}"
            log.error("job %s failed: %s\n%s", jid, err,
                      traceback.format_exc())
            with conn.transaction():
                conn.execute(FINISH_SQL, ("failed", err[:2000], jid))
                _audit(conn, ind, f"worker:{worker_id}", "quarter.roll.failed",
                       {"job_id": jid, "year": year, "quarter": qtr,
                        "error": err[:500]})
            return True
        with conn.transaction():
            conn.execute(FINISH_SQL, ("done", None, jid))
            _audit(conn, ind, f"worker:{worker_id}", "quarter.roll.published",
                   {"job_id": jid, "year": year, "quarter": qtr,
                    "teams_processed": summary.get("teams_processed"),
                    "auto_passed": summary.get("auto_passed", [])})
        log.info("job %s done: %s", jid, summary)
        return True


def run_forever(worker_id: str, poll_seconds: float) -> None:
    log.info("worker %s started (poll every %ss)", worker_id, poll_seconds)
    while True:
        try:
            found = process_one(worker_id)
        except Exception:  # noqa: BLE001 - never let the loop die
            log.exception("worker loop error; retrying after poll interval")
            found = False
        if not found:
            time.sleep(poll_seconds)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Topaz-VBE engine worker")
    parser.add_argument("--once", action="store_true",
                        help="process a single pending job then exit")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    worker_id = os.environ.get("WORKER_ID",
                               f"{socket.gethostname()}-{os.getpid()}")
    poll = float(os.environ.get("WORKER_POLL_SECONDS", "5"))

    if args.once:
        return 0 if process_one(worker_id) else 0
    run_forever(worker_id, poll)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
