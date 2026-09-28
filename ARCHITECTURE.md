# Topaz-VBE Replica — Architecture

Re-implementation of the Edit 515 **Topaz-VBE (Virtual Business Environment)**
business simulation as a decoupled, batch-processing platform. All economics are
re-implemented from the public manual (Tables 1–23); no proprietary code exists
or is copied. See `SPEC.md` (locked, single source of truth) and
`STEP_BY_STEP_EXPLANATION.md` (study guide).

## Why batch processing, not real-time

Topaz-VBE is a *competitive* simulation: a team's market share, sales and share
price depend on what **all other teams** decided in the same quarter (relative
pricing, relative advertising, relative quality). You cannot resolve one team's
quarter without every other team's decisions. Therefore:

- Teams interact with the system in real time (read reports, edit/save/submit
  decisions) via a normal REST API.
- Quarter resolution is a **batch job**: once the quarter is locked (all teams
  submitted, or the admin auto-pass deadline expired, or admin forces it), a
  standalone engine process loads *all* decisions for the industry+quarter,
  simulates every team deterministically, writes every report, then flips the
  quarter to `published`. All teams see their new Management Report
  simultaneously.

This mirrors the original: teams hand in a Decision Form, the controller runs
the period, everyone receives the Management Report together.

## Components

```
┌──────────────┐   REST/JSON    ┌──────────────┐  subprocess   ┌──────────────┐
│ React SPA    │ ────────────► │ FastAPI      │ ────────────► │ Simulation   │
│ (old-school  │                │ backend      │  batch job    │ engine       │
│  cream/red   │ ◄──────────── │ (auth, CRUD, │  (per quarter)│ (pure Python,│
│  manual look)│   JWT Bearer   │ validation,  │               │ deterministic)│
└──────────────┘                │ admin, roll) │               └──────┬───────┘
                                └──────┬───────┘                      │ psycopg
                                       │ psycopg                      ▼
                                ┌──────▼──────────────────────────────────────┐
                                │ PostgreSQL 16                               │
                                │ industries · teams · admins · quarters      │
                                │ decisions (JSONB/quarter) · reports (JSONB) │
                                │ macro (shocks) · audit_log                  │
                                └─────────────────────────────────────────────┘
```

- **frontend/** — Vite + React, plain CSS, zero UI libraries. Hash-routed pages:
  Login → Main → Marketing / Production / Personnel / Finance → Reports
  (period selector) → Review → Submit; Manual (Tables 1–23); Admin portal
  (industries, teams, macro shocks, roll-the-quarter with deadlock guard).
  Styled like the original: cream background, dark-red headings, blue links,
  compact bordered tables, dense forms.
- **backend/** — FastAPI. Team auth = simulation code + group/company number +
  identity number (the secret). Admin auth = username + password (demo default
  `admin`/`admin123` from env, clearly labeled). Endpoints per `SPEC.md` §4.
  Validation imported from the engine package so rules can't drift. The
  roll-quarter endpoint enforces the deadlock guard, then runs the engine as a
  subprocess batch job.
- **engine/** — `topaz_engine` package: `constants.py` (Tables 1–23, defaults,
  initial state), `validation.py` (decision rules), `simulation.py` (pure,
  deterministic quarter math — no RNG, no I/O), `runner.py` + `db.py`
  (DB orchestration incl. auto-pass), `cli.py`
  (`python -m topaz_engine.cli --industry 1 --year 1 --quarter 3`).
- **db/migrations/** — `001_init.sql` (schema), `002_seed.sql` (demo industry,
  4 teams, quarters), `003_jobs.sql` (`quarter_jobs` queue table),
  `migrate.py` (idempotent migration runner), `seed_demo_reports.py` (two
  quarters of clearly-labeled demonstration reports with asserted accounting
  invariants).

## Quarter-roll execution modes

`QUARTER_ROLL_MODE` on the backend selects how step 4 below runs:

- **`sync`** (default for local dev) — the API runs the engine as a subprocess
  (`python -m topaz_engine.cli …`) and waits for it. Simple, no extra service.
- **`queue`** (docker-compose default) — event-driven:
  1. `POST …/roll-quarter` passes the deadlock guard, locks the quarter, and
     inserts a `pending` row into `quarter_jobs` (idempotent on
     `(industry_id, year, quarter)`), returning **202 Accepted** with the job id.
  2. The **engine-worker** service (`engine/topaz_engine/worker.py`, Docker
     image `engine/Dockerfile`) polls `quarter_jobs` and claims one job with
     `SELECT … FOR UPDATE SKIP LOCKED` — any number of worker replicas can run;
     a job is never processed twice.
  3. The worker calls `runner.run_quarter(...)` (the same function the CLI
     uses), which sets the quarter `processing`, runs the pure simulation,
     writes one `reports` row per team, flips the quarter to `published`, and
     marks the job `done` (or `failed` with the error text; the quarter is
     restored to `locked` so the admin can re-roll).
  4. The admin UI polls `roll-status` (which now includes the job) until the
     quarter is `published`.
- Every step writes `audit_log` rows (`quarter.roll.lock/queued/published`,
  `quarter.roll.failed`), so the whole batch is traceable.

## Data flow of one quarter

1. Admin opens quarter (status `open`, auto-pass deadline set).
2. Teams GET/PUT `/api/decisions/current`, then POST `.../submit`
   (validation: price > 0, affordability vs cash + overdraft limit, etc.).
3. Admin checks `/api/admin/.../roll-status`; presses **Roll the Quarter**.
   Deadlock guard: if any active team hasn't submitted AND the deadline hasn't
   passed AND `force` is false → HTTP 409 listing the missing teams.
4. Backend marks quarter `locked`, then — depending on `QUARTER_ROLL_MODE` —
   either runs the engine subprocess itself (`sync`) or inserts a pending
   `quarter_jobs` row and returns 202 while the engine worker claims and runs
   the batch (`queue`; see "Quarter-roll execution modes" above).
   Unsubmitted teams are auto-passed (last submitted decisions carried forward,
   flagged `auto_pass`).
5. Engine computes macro demand → attractiveness/market share (price elasticity
   + cross-elasticity) → production constraints (machine/assembly/material
   hours) → full financials (P&L, balance sheet, cash flow) → share prices.
   Writes one `reports` row per team, marks quarter `published`, audit entry.
6. Teams GET `/api/reports?year=&quarter=` — all reports appear at once.

## Determinism

`simulation.py` uses no random numbers; team order is by company_number;
all rounding is fixed. Identical decisions + identical macro → byte-identical
report JSON (proven by `engine/tests/test_determinism.py`).

## Key files

| File | Role |
|---|---|
| `SPEC.md` | Locked data model, API contract, Tables 1–23, validation rules |
| `STEP_BY_STEP_EXPLANATION.md` | Study guide (viva prep) |
| `docker-compose.yml` | One-command run: postgres + migrate + api + worker + frontend |
| `db/migrations/003_jobs.sql` | `quarter_jobs` table for the engine worker |
| `engine/topaz_engine/worker.py` | Event-driven quarter consumer (`--once` for one job) |
| `db/migrations/001_init.sql` | Schema |
| `engine/topaz_engine/simulation.py` | Quarter math |
| `backend/app/main.py` | API wiring |
| `frontend/src/` | React app |
