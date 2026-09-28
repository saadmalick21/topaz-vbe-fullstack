# Topaz-VBE Replica

A complete full-stack simulation of the **Topaz / Edit 515** business management
game ("Topaz-VBE" style): teams run competing manufacturing companies over
quarterly decision rounds, and a deterministic batch engine simulates all teams
together to produce periodic Management Reports.

Built from the public Edit 515 reference (see below) plus the game's published
manual parameters (Tables 1–23). **No proprietary backend code was used or
copied** — every formula here is an original implementation of the documented
rules.

## What it is

| Layer | Tech | What it does |
|---|---|---|
| `frontend/` | React + Vite | Old-school management UI (cream background, dark-red headings, compact bordered tables). Team login, decision forms, reports, admin control centre. |
| `backend/` | FastAPI (Python) | JWT auth, decision CRUD + validation, reports API, Tables 1–23 API, admin industry/team/quarter/shock endpoints, quarter-roll orchestration, audit log. |
| `engine/` | Pure Python | Deterministic simulation core: demand, attractiveness, price/cross-elasticity, production constraints, P&L, balance sheet, cash flow, share price. Plus the **engine worker** (event-driven quarter consumer). |
| `db/` | PostgreSQL 16 | Schema migrations, demo-industry seed, demo report generator. |

Key design facts:

- A quarter flows `open → locked → processing → published`.
- Teams submit decisions in real time, but the quarter is simulated **as one
  batch** because demand and market share depend on competitors' decisions.
- The engine is **deterministic**: identical inputs → byte-identical report JSON
  (proven by `engine/tests/test_determinism.py`).
- A team that misses the deadline **auto-passes**: its latest submitted decision
  is carried forward.
- Two roll modes (`QUARTER_ROLL_MODE`): `sync` (API runs the engine as a
  subprocess and waits) and `queue` (API enqueues a `quarter_jobs` row with
  `202 Accepted`; the engine-worker service claims it with
  `SELECT … FOR UPDATE SKIP LOCKED` and runs the batch). Docker Compose uses
  `queue`; the worker scales horizontally without double-processing.

## Reference analysis

- https://edit515.co.uk/ — Edit 515 ceased UK trading on 11 July 2023 and
  transferred its GMC-related source code. The live game is no longer operable
  there, so this replica re-implements the documented behaviour.
- https://edit515.co.uk/013.htm — confirms the game shape this replica models:
  up to 8 competing teams; 3 products across 4 areas; marketing (pricing,
  advertising, selling, quality, design); two-stage manufacturing/assembly;
  machine time, assembly workers, personnel and finance integrated; periodic
  Management Reports driving the next round of decisions.

## Quick start (Docker — one command)

```bash
cd ~/workspace/topaz-vbe
cp .env.example .env
docker compose up --build
```

Open:

- Frontend: http://localhost:8080/
- API docs: http://localhost:8000/docs

What happens on first start: `db` (PostgreSQL 16) starts → `migrate` applies
`db/migrations/001_init.sql`, `002_seed.sql`, `003_jobs.sql` → `api` starts
(and creates the demo admin) → `worker` starts polling `quarter_jobs` →
`frontend` serves the UI and proxies `/api/` to the backend.

### Demo credentials (seeded by migration 002)

**Team login** — simulation code `TOPAZ-DEMO`, group number `1`:

| Company | Company no. | Identity no. |
|---|---|---|
| Alpha Manufacturing | 1 | ID-1001 |
| Beta Industries | 2 | ID-1002 |
| Gamma Traders | 3 | ID-1003 |
| Delta Works | 4 | ID-1004 |

**Admin login** — username `admin`, password `admin123`
(overridable via `ADMIN_USER` / `ADMIN_PASSWORD` in `.env`).

> ⚠️ **Security warning (demo-grade):** the admin password is stored as a plain
> SHA-256 hex digest (see `backend/app/auth.py` / `main.py` bootstrap). This is a
> deliberate simplification for the university assignment. Any shared or
> production deployment **must** replace it with bcrypt/Argon2 + per-user salt,
> set a strong `SECRET_KEY`, and put the deployment behind HTTPS.

## Local setup (without Docker)

Prerequisites: Python 3.12+, Node 20+, PostgreSQL 16.

```bash
# 1. Database
createdb topaz
export DATABASE_URL=postgresql://<user>@localhost:5432/topaz

# 2. Migrations (idempotent; safe to re-run)
python3 db/migrate.py

# 3. Demo history (optional): generates Y1Q1+Y1Q2 reports through the real engine
python3 db/seed_demo_reports.py          # writes to DB
python3 db/seed_demo_reports.py --dry-run # validate only, no DB writes

# 4. Engine (no install needed; pure Python + psycopg)
pip install "psycopg[binary]" pytest
python3 -m pytest engine/tests -q
# run one quarter manually:
PYTHONPATH=engine python3 -m topaz_engine.cli --industry 1 --year 1 --quarter 3

# 5. Backend API
pip install -r backend/requirements.txt
SECRET_KEY=dev-secret QUARTER_ROLL_MODE=sync \
  PYTHONPATH=engine:backend uvicorn app.main:app --app-dir backend --port 8000

# 6. Engine worker (only needed when QUARTER_ROLL_MODE=queue)
PYTHONPATH=engine WORKER_POLL_SECONDS=5 python3 -m topaz_engine.worker

# 7. Frontend
cd frontend && npm install && npm run dev   # dev server on :5173 (proxies /api)
npm run build                                # production bundle in frontend/dist
```

## API overview

Team: `POST /api/auth/login`, `GET /api/me`, `GET /api/quarters`,
`GET|PUT /api/decisions/current`, `POST /api/decisions/current/submit`,
`POST /api/decisions/current/reset`, `GET /api/reports?year=&quarter=`,
`GET /api/tables`.

Admin: `POST /api/auth/admin-login`, `GET|POST /api/admin/industries`,
`GET /api/admin/industries/{id}`, `POST /api/admin/industries/{id}/teams`,
`POST /api/admin/industries/{id}/quarters`, `POST /api/admin/industries/{id}/shocks`,
`GET /api/admin/industries/{id}/roll-status`,
`POST /api/admin/industries/{id}/roll-quarter` (`{"force": true}` to bypass the
deadlock guard), `GET /api/admin/audit`.

Full contracts live in `SPEC.md` (section 4).

## Simplifications vs. the proprietary game

This is a teaching replica, not the original code. Deliberate simplifications:

- The engine formulas implement the *documented* rules (manual Tables 1–23);
  exact proprietary calibration constants are not public and were not copied.
- Price elasticity is modelled as `(avg_price / own_price)²` clamped to
  `[0.25, 4]`; cross-elasticity via attractiveness normalisation
  (SPEC section 6). Real Topaz used its own tuned curves.
- One macro scenario per quarter (GDP, unemployment, bank rate, inflation,
  recession flag, material-price shock) instead of the full economic model.
- No email/print distribution of reports; teams read them in the UI.
- Authentication is demo-grade (see security warning above).

## Edge cases handled

- **Deadlock guard:** rolling with unsubmitted teams and no deadline/force →
  `409` listing the missing teams.
- **Auto-pass:** unsubmitted teams roll with their latest submitted decision
  (flagged `auto_pass` in the report meta).
- **Zero/negative price, unaffordable plans:** rejected at validation with field
  errors before anything is saved.
- **Overdraft limit:** Table 19 formula enforced; breaching it blocks the roll
  with a clear error.
- **Determinism:** `compute_quarter(..., now_iso=...)` fixes the publication
  timestamp; production passes the current UTC time.
- **Worker crash mid-job:** the quarter is restored to `locked`, the job is
  marked `failed` with the error, and the admin can re-roll (idempotent job
  insert).

## Verification status (honest)

What was actually run on 2026-09-26 (no Docker daemon was available, so
Compose itself could not be booted; `docker compose config` could not be
validated — the YAML was structure-checked with a parser instead):

- `python3 -m pytest engine/tests -q` → **14/14 passed** (incl. byte-identical
  determinism test).
- `python3 db/seed_demo_reports.py --dry-run` → 8/8 reports, 13/13
  accounting/structural checks each.
- Full live E2E against a real local PostgreSQL 16: migrate → seed → API
  (`QUARTER_ROLL_MODE=queue`) → admin login → deadlock guard `409` →
  force-roll `202` (job queued) → `python -m topaz_engine.worker --once` →
  job `done`, quarter `published` → team login → Y1Q3 report fetched
  (revenue £692,963.00, net profit £94,365.35, balance-sheet identity 0.0).
  This E2E caught and fixed a real bug (worker audit used a wrong column name).
- `npm run build` → production bundle built successfully.
- Frontend ↔ backend contract cross-check: every `api.js` path matches a
  backend route; authenticated routes return `401` without a token.
- `python3 -m py_compile` on backend + engine + db scripts: clean.
- No `TODO`/`FIXME`/placeholder markers in the codebase.

What was **not** verified: an actual `docker compose up` boot (no Docker
daemon), and real multi-browser gameplay.

## Docs

- `SPEC.md` — locked source of truth (decision fields, schema, API contracts,
  Tables 1–23, engine formulas).
- `ARCHITECTURE.md` — batch-processing architecture and data flow.
- `STEP_BY_STEP_EXPLANATION.md` — plain-language university study/viva guide
  tied to the actual code.
- `engine/README.md`, `backend/README.md`, `db/README.md`, `frontend/README.md`
  — per-component notes.
