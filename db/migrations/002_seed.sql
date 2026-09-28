-- =============================================================================
-- Topaz-VBE replica — migration 002: demo seed
-- Conforms to SPEC.md section 10 (single source of truth).
--
-- Seeds: industry "Demo Industry" (TOPAZ-DEMO), 4 teams, quarters
-- Y1Q1/Y1Q2 (published) + Y1Q3 (open, deadline = now() + 7 days),
-- macro rows for Y1Q1/Y1Q2.
--
-- Deliberately does NOT seed the admins table: the backend auto-creates the
-- demo admin from env vars on startup (SPEC section 10).
--
-- Idempotent-ish: every INSERT uses ON CONFLICT DO NOTHING, so re-running
-- this file is safe (existing rows are left untouched).
--
--   psql "$DATABASE_URL" -f db/migrations/002_seed.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Industry
-- ---------------------------------------------------------------------------
INSERT INTO industries (name, simulation_code, status)
VALUES ('Demo Industry', 'TOPAZ-DEMO', 'active')
ON CONFLICT (simulation_code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Teams: group 1, companies 1..4
-- ---------------------------------------------------------------------------
INSERT INTO teams (industry_id, group_number, company_number, identity_number, name, active)
SELECT i.id, 1, t.company_number, t.identity_number, t.name, true
FROM (SELECT id FROM industries WHERE simulation_code = 'TOPAZ-DEMO') AS i
CROSS JOIN (VALUES
    (1, 'ID-1001', 'Alpha Manufacturing'),
    (2, 'ID-1002', 'Beta Industries'),
    (3, 'ID-1003', 'Gamma Traders'),
    (4, 'ID-1004', 'Delta Works')
) AS t (company_number, identity_number, name)
ON CONFLICT (industry_id, group_number, company_number) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Quarters: Y1Q1 + Y1Q2 published, Y1Q3 open with a 7-day deadline.
-- auto_pass_minutes 10080 = 7 days (matches the schema default).
-- ---------------------------------------------------------------------------
INSERT INTO quarters (industry_id, year, quarter, status, auto_pass_minutes, deadline_at, published_at)
SELECT i.id,
       q.year, q.quarter, q.status, q.auto_pass_minutes,
       q.deadline_at, q.published_at
FROM (SELECT id FROM industries WHERE simulation_code = 'TOPAZ-DEMO') AS i
CROSS JOIN (VALUES
    (1, 1, 'published', 10080, NULL::timestamptz,           now()),
    (1, 2, 'published', 10080, NULL::timestamptz,           now()),
    (1, 3, 'open',      10080, now() + interval '7 days',   NULL::timestamptz)
) AS q (year, quarter, status, auto_pass_minutes, deadline_at, published_at)
ON CONFLICT (industry_id, year, quarter) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Macro (economic environment) for the two published quarters
-- ---------------------------------------------------------------------------
INSERT INTO macro (industry_id, year, quarter,
                   central_bank_rate, gdp_growth_pct, unemployment_pct,
                   inflation_pct, recession)
SELECT i.id,
       m.year, m.quarter,
       m.central_bank_rate, m.gdp_growth_pct, m.unemployment_pct,
       m.inflation_pct, m.recession
FROM (SELECT id FROM industries WHERE simulation_code = 'TOPAZ-DEMO') AS i
CROSS JOIN (VALUES
    (1, 1, 8.0, 2.5, 5.0, 1.5, false),
    (1, 2, 8.0, 2.5, 5.0, 1.5, false)
) AS m (year, quarter, central_bank_rate, gdp_growth_pct,
        unemployment_pct, inflation_pct, recession)
ON CONFLICT (industry_id, year, quarter) DO NOTHING;

COMMIT;
