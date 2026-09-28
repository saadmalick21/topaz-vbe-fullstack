-- =============================================================================
-- Topaz-VBE replica — migration 001: initial schema
-- Conforms to SPEC.md section 3 (single source of truth).
-- PostgreSQL 16. Apply once, in order, before 002_seed.sql.
--   psql "$DATABASE_URL" -f db/migrations/001_init.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- industries: one row per simulation run (up to 8 competing teams each)
-- ---------------------------------------------------------------------------
CREATE TABLE industries (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    simulation_code TEXT UNIQUE NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- teams: companies inside an industry.
-- Identified by (simulation_code, group_number, company_number, identity_number).
-- ---------------------------------------------------------------------------
CREATE TABLE teams (
    id              SERIAL PRIMARY KEY,
    industry_id     INT NOT NULL REFERENCES industries (id) ON DELETE CASCADE,
    group_number    INT NOT NULL,
    company_number  INT NOT NULL,
    identity_number TEXT UNIQUE NOT NULL,      -- secret credential for team login
    name            TEXT NOT NULL,
    active          BOOL NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (industry_id, group_number, company_number)
);

-- ---------------------------------------------------------------------------
-- admins: back-office users (username + password hash). NOT seeded by 002;
-- the backend auto-creates the demo admin from env vars on startup.
-- ---------------------------------------------------------------------------
CREATE TABLE admins (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- quarters: discrete time buckets. Status flow:
--   open -> locked -> processing -> published
-- ---------------------------------------------------------------------------
CREATE TABLE quarters (
    id                SERIAL PRIMARY KEY,
    industry_id       INT NOT NULL REFERENCES industries (id) ON DELETE CASCADE,
    year              INT NOT NULL,
    quarter           INT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    status            TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'locked', 'processing', 'published')),
    auto_pass_minutes INT NOT NULL DEFAULT 10080,  -- 7 days
    deadline_at       TIMESTAMPTZ,                 -- null = no deadline
    published_at      TIMESTAMPTZ,
    UNIQUE (industry_id, year, quarter)
);

-- ---------------------------------------------------------------------------
-- decisions: one decision form per team per quarter (JSONB, SPEC section 2).
-- ---------------------------------------------------------------------------
CREATE TABLE decisions (
    id           SERIAL PRIMARY KEY,
    industry_id  INT NOT NULL REFERENCES industries (id) ON DELETE CASCADE,
    team_id      INT NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    year         INT NOT NULL,
    quarter      INT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    data         JSONB NOT NULL,                    -- decision form, SPEC section 2
    submitted    BOOL NOT NULL DEFAULT false,
    submitted_at TIMESTAMPTZ,
    auto_pass    BOOL NOT NULL DEFAULT false,       -- carried forward at roll
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (team_id, year, quarter)
);

-- ---------------------------------------------------------------------------
-- reports: engine output per team per quarter (JSONB, SPEC section 6).
-- ---------------------------------------------------------------------------
CREATE TABLE reports (
    id           SERIAL PRIMARY KEY,
    industry_id  INT NOT NULL REFERENCES industries (id) ON DELETE CASCADE,
    team_id      INT NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    year         INT NOT NULL,
    quarter      INT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    report       JSONB NOT NULL,                    -- full report, SPEC section 6
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (team_id, year, quarter)
);

-- ---------------------------------------------------------------------------
-- macro: economic environment ("shocks") per industry per quarter.
-- Money-adjacent fields are NUMERIC.
-- ---------------------------------------------------------------------------
CREATE TABLE macro (
    id                        SERIAL PRIMARY KEY,
    industry_id               INT NOT NULL REFERENCES industries (id) ON DELETE CASCADE,
    year                      INT NOT NULL,
    quarter                   INT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    inflation_pct             NUMERIC NOT NULL DEFAULT 0,
    material_price_change_pct NUMERIC NOT NULL DEFAULT 0,
    recession                 BOOL NOT NULL DEFAULT false,
    note                      TEXT,
    central_bank_rate         NUMERIC NOT NULL DEFAULT 8.0,
    gdp_growth_pct            NUMERIC NOT NULL DEFAULT 2.5,
    unemployment_pct          NUMERIC NOT NULL DEFAULT 5.0,
    UNIQUE (industry_id, year, quarter)
);

-- ---------------------------------------------------------------------------
-- audit_log: append-only record of admin/engine actions.
-- ---------------------------------------------------------------------------
CREATE TABLE audit_log (
    id          SERIAL PRIMARY KEY,
    industry_id INT REFERENCES industries (id) ON DELETE SET NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_teams_industry          ON teams (industry_id);
CREATE INDEX idx_quarters_industry_yq   ON quarters (industry_id, year, quarter);
CREATE INDEX idx_decisions_industry_yq  ON decisions (industry_id, year, quarter);
CREATE INDEX idx_decisions_team         ON decisions (team_id);
CREATE INDEX idx_reports_industry_yq    ON reports (industry_id, year, quarter);
CREATE INDEX idx_reports_team           ON reports (team_id);
CREATE INDEX idx_macro_industry_yq      ON macro (industry_id, year, quarter);
CREATE INDEX idx_audit_log_industry_ts  ON audit_log (industry_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Keep decisions.updated_at fresh on UPDATE
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_decisions_updated_at
    BEFORE UPDATE ON decisions
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMIT;
