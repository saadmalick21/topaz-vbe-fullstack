-- =============================================================================
-- Topaz-VBE replica — migration 003: quarter job queue for the engine worker
-- Conforms to SPEC.md section 8 (Engine quarter flow).
--
-- The admin "roll quarter" endpoint can run in two modes
-- (QUARTER_ROLL_MODE env on the backend):
--   sync   (default) — the API runs the engine as a subprocess and waits.
--   queue  (docker-compose default) — the API only locks the quarter and
--            inserts a 'pending' row here; the engine-worker service claims
--            it (SELECT ... FOR UPDATE SKIP LOCKED) and runs the batch.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS quarter_jobs (
    id            SERIAL PRIMARY KEY,
    industry_id   INTEGER NOT NULL REFERENCES industries (id) ON DELETE CASCADE,
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'running', 'done', 'failed', 'cancelled')),
    attempts      INTEGER NOT NULL DEFAULT 0,
    locked_by     TEXT,
    locked_at     TIMESTAMPTZ,
    error         TEXT,
    auto_passed   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (industry_id, year, quarter)
);

CREATE INDEX IF NOT EXISTS idx_quarter_jobs_status
    ON quarter_jobs (status);

COMMIT;
