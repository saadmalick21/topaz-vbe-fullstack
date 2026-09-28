# Topaz-VBE replica — database layer

PostgreSQL 16 schema, demo seed, and demo report seeder. Conforms to
`../SPEC.md` sections 3 (schema), 9 (initial company state) and 10 (demo seed)
— the spec is the single source of truth.

## Layout

```
db/
├── migrations/
│   ├── 001_init.sql        # full schema: industries, teams, admins, quarters,
│   │                       #   decisions, reports, macro, audit_log
│   └── 002_seed.sql        # demo seed: TOPAZ-DEMO industry, 4 teams,
│                           #   Y1Q1/Y1Q2 published, Y1Q3 open, macro rows
├── seed_demo_reports.py    # builds submitted decisions + internally consistent
│                           #   demo reports for 4 teams × Y1Q1/Y1Q2, with
│                           #   invariant checks (PASS/FAIL per report)
└── README.md               # this file
```

## Prerequisites

- PostgreSQL 16 server and a database, e.g. `createdb topaz`
- `DATABASE_URL` set, e.g.
  `export DATABASE_URL="postgresql://user:pass@localhost:5432/topaz"`
- For the report seeder: Python 3.12 + `psycopg`
  (`pip install "psycopg[binary]"`)

## Apply the migrations (in order)

```bash
psql "$DATABASE_URL" -f db/migrations/001_init.sql
psql "$DATABASE_URL" -f db/migrations/002_seed.sql
```

- `001_init.sql` creates all 8 tables with primary keys, foreign keys,
  the required UNIQUE constraints (`teams`: `(industry_id, group_number,
  company_number)`; `decisions`/`reports`: `(team_id, year, quarter)`;
  `quarters`/`macro`: `(industry_id, year, quarter)`), the quarter-status
  CHECK, `CHECK (quarter BETWEEN 1 AND 4)`, NOT NULLs, `now()` defaults,
  NUMERIC money columns, JSONB for `decisions.data` / `reports.report`,
  indexes on `(industry_id, year, quarter)`, and a trigger keeping
  `decisions.updated_at` fresh.
- `002_seed.sql` inserts industry **Demo Industry** (`TOPAZ-DEMO`), teams
  **Alpha Manufacturing / Beta Industries / Gamma Traders / Delta Works**
  (group 1, companies 1–4, identity numbers `ID-1001`…`ID-1004`),
  quarters Y1Q1 + Y1Q2 `published`, Y1Q3 `open` with
  `deadline_at = now() + interval '7 days'`, and macro rows for Y1Q1/Y1Q2
  (bank rate 8.0, GDP 2.5%, unemployment 5.0%, inflation 1.5%, no recession).
  It deliberately does **not** seed `admins` — the backend auto-creates the
  demo admin from env vars on startup. Every statement is
  `INSERT … ON CONFLICT DO NOTHING`, so re-running is safe.

## Seed the demo reports

```bash
python3 db/seed_demo_reports.py            # validate + insert into the DB
python3 db/seed_demo_reports.py --dry-run  # validate only, no DB writes
```

The script reads the demo industry/teams/quarters/macro from the database
(requires `002_seed.sql` applied), then for each of the 4 teams × Y1Q1/Y1Q2:

1. builds a full decision form (every field name from SPEC section 2, varied
   but plausible prices/volumes per team — validated against the SPEC
   section 7 rules: prices > 0, assembly minutes ≥ 100/150/300, salary ≥ £2k,
   management budget ≥ £40k, …);
2. builds the report bottom-up from 12 product/area rows so the accounts tie
   out: every top-level key from SPEC section 6 is present
   (`meta` with `demo_data=true`, `auto_pass=false`; `decisions` echo;
   `resources`; `products`; `overheads`; `pnl`; `balance_sheet`;
   `cash_flow`; `group` — the same 4 companies with that quarter's share
   prices/net profits/net worths plus per-cell market shares; `economic`);
3. asserts per report and prints **PASS/FAIL** for:
   - (a) `pnl.sales_revenue == Σ sales×price` over the 12 product rows (±0.01)
   - (b) `pnl.net_profit == profit_before_tax − tax_assessed` (±0.01)
   - (c) `balance_sheet.net_assets == total_assets − current_liabilities`
   - (d) `balance_sheet.net_worth == share_capital + reserves`
   - (e) `net_assets == net_worth` (±0.01)
   plus structural checks (exact SPEC key sets, 12 product rows,
   `demo_data`/`auto_pass` flags) and bonus cash-flow consistency.

Inserts use `ON CONFLICT … DO UPDATE`, so re-running replaces the demo rows
idempotently. **Nothing is written unless every check passes** (exit code 1
otherwise). The generator is deterministic — no randomness — so re-runs
produce identical report JSON.

## Notes / documented demo assumptions

- Demo economics are illustrative, not the engine: machine book values,
  machinist wage (£10.50/h), guarantee servicing (£0.80/£1.20/£1.60 per unit
  sold), supplier-1 £200 fixed fee, creditor/tax timing, debtors at
  `revenue × days_credit/90`, and cash as the balance-sheet balancing plug.
- Share prices follow the SPEC section 8 rule
  (`new = old × (1 + 0.6 × net_profit/net_worth_prev)`, bounded £0.10–£50,
  rounded to pence) from the SPEC section 9 opening price of £1.50.
- Tax is accrued at 30% of quarterly profit before tax (the SPEC section 8
  documented simplification); last quarter's bill is paid this quarter.
