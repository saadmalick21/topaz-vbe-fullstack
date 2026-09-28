# Topaz-VBE Replica — Step-by-Step Explanation

A plain-language study and viva guide for this project. Every section names the
actual files and functions it describes, so you can open the code and point at
the exact lines in a viva.

**One-sentence summary:** teams run competing manufacturing companies by
submitting quarterly decisions through a web UI; once a quarter is locked, a
deterministic engine simulates *all* teams together as one batch and publishes a
Management Report for each team.

---

## 1. The big picture: what talks to what

```
 Team's browser (React) ──REST/JSON──▶ FastAPI backend ──▶ PostgreSQL
        ▲                                                        │
        │ JWT Bearer token                                       │ quarter_jobs
        │                                                        ▼
        └──────── Management Reports ◀── engine worker ── claims jobs,
                          (batch)        (pure Python)     runs the batch
```

Four pieces, each in its own folder:

| Piece | Folder | Job |
|---|---|---|
| Frontend | `frontend/` | The screens teams and admins click. Old-school look on purpose: cream background, dark-red headings, blue underlined links, small compact tables — like the original paper/manual era software. |
| Backend | `backend/` | The waiter: checks who you are (JWT), saves decisions, validates them, serves reports, and runs the admin's "roll the quarter". |
| Engine | `engine/` | The brain: pure maths that turns everyone's decisions into Management Reports. No internet, no database inside the maths itself. |
| Database | `db/` | PostgreSQL 16. Stores everything permanently: industries, teams, decisions, reports, plus the job queue. |

**The golden rule of the design:** the engine never trusts the network and the
maths never touches the clock or random numbers. That is what makes results
reproducible (see §10).

---

## 2. The key viva question: why batch processing, not real-time?

In Topaz, companies **compete**. Your sales don't just depend on your price —
they depend on your price *compared to everyone else's* price, your advertising
*compared to theirs*, your product quality *compared to theirs*.

That means **one team's quarter cannot be resolved without all other teams'
decisions**. If team A cuts its price, team B's market share drops — you can
only compute that when you know both decisions side by side.

So the system works like the original board game / paper version:

1. **Real-time phase** — teams log in anytime, edit and save decisions, and
   submit them. The backend just stores these (table `decisions`).
2. **Batch phase** — the admin "rolls the quarter". The engine loads *every*
   team's decisions for that quarter at once, simulates the whole market
   together, writes *every* report, and flips the quarter to `published`.
   All teams receive their Management Report simultaneously — exactly like
   everyone getting the printed report at the same meeting.

Code: `engine/topaz_engine/runner.py::run_quarter()` is the batch;
`backend/app/routers/admin.py::roll_quarter()` is the admin trigger.

---

## 3. The database, table by table

Schema: `db/migrations/001_init.sql`. Job queue: `db/migrations/003_jobs.sql`.
Migrations are applied in order by `db/migrate.py` (safe to re-run — it tracks
what's done in `schema_migrations`).

1. **`industries`** — one row per simulation run ("Demo Industry",
   code `TOPAZ-DEMO`). Up to 8 teams compete inside one industry.
2. **`teams`** — the companies. Columns that matter: `company_number` (1–8,
   also the sort order for determinism), `name`, `group_number`,
   `identity_number` (the team's secret password, e.g. `ID-1001`), `active`.
3. **`admins`** — admin logins (`username`, SHA-256 `password_hash` — demo-grade,
   see the security note in `README.md`).
4. **`quarters`** — one row per (industry, year, quarter). The `status` column
   is the state machine: `open → locked → processing → published`.
   Also stores `deadline_at` (auto-pass deadline).
5. **`decisions`** — one row per (team, year, quarter): the team's decision
   JSON (`data`), whether it was `submitted`, and when.
6. **`reports`** — one row per (team, year, quarter): the finished Management
   Report JSON produced by the engine. This is the engine's *output*.
7. **`macro`** — the economic scenario per quarter: GDP growth, unemployment,
   central-bank rate, inflation, a `recession` flag, and material-price shocks.
   Set by the admin ("economic shocks").
8. **`audit_log`** — who did what, when: logins, decision saves/submits,
   quarter locks/rolls/publishes, job claims. Every admin mutation writes a row
   (see `backend/app/routers/_common.py::audit()`).
9. **`quarter_jobs`** — the engine-worker queue (one row per
   `(industry_id, year, quarter)`, unique). `status` is
   `pending → running → done` (or `failed`). Workers claim rows with
   `SELECT … FOR UPDATE SKIP LOCKED` so two workers never grab the same job.

---

## 4. The decisions: what a team actually decides

The decision JSON (`engine/topaz_engine/constants.py::DEFAULT_DECISIONS`) is the
"Decision Form". Groups, in plain language:

**Marketing**
- `prices.home` / `prices.export` — selling price per product (3 products).
  Default home: £110 / £165 / £240.
- `promotion.trade_press|advertising|support|merchandising` — £000s spent per
  product on each channel (defaults e.g. advertising £20k/£15k/£10k).
- `salespeople.{export,south,west,north}` — headcount per area (default 2/4/3/5).
- `sales_remuneration` — quarterly salary (£000s) + commission %.
- `product_improvements` — R&D flag per product (true/false).
- `days_credit_allowed` — customer credit terms (default 30 days).

**Production**
- `assembly_time_minutes` — minutes of assembly labour per unit per product
  (default 110 / 160 / 320).
- `make_deliver.{area}` — units to make *and* deliver per product per area
  (e.g. south: 600 / 400 / 200). This is the production schedule.
- `shift_level` — 1/2/3 shifts (more hours, but a wage premium — Table 16).
- `contract_maintenance_hours`, `machines_to_sell`, `new_machines_to_order`,
  `vans_to_buy` / `vans_to_sell` — capacity decisions.
- `raw_material` — units to order, supplier number, number of deliveries.

**Personnel**
- `assembly_wage` (pounds + pence, default £9.50/hr), `management_budget_000`.
- `salespeople_changes` / `assembly_changes` — recruit / dismiss / train counts.
  (Training and wages feed morale/productivity via Tables 12–14.)

**Finance**
- `dividend_rate_pence` — dividend per share.
- `research_expenditure_000` — R&D spend.
- `info_wanted.other_companies|market_shares` — paid competitor intelligence
  (shows up in the report only if bought).

Validation (`engine/topaz_engine/validation.py`, called by the backend before
saving) rejects nonsense early: price must be > 0, you can't spend more than
cash + overdraft limit, headcounts can't go negative, etc. The exact error
wordings are pinned in `SPEC.md` §7.

---

## 5. The quarter lifecycle (the state machine)

```
open ──▶ locked ──▶ processing ──▶ published
```

- **`open`** — teams can save and submit decisions. Nothing is final.
- **`locked`** — admin pressed "Roll the Quarter" (or will). No more edits.
- **`processing`** — the engine batch is running right now.
- **`published`** — reports are written; teams can read them. The next quarter
  becomes `open`.

**Deadlock guard** (the anti-stall rule): if some teams haven't submitted and
the deadline hasn't passed, rolling is refused with HTTP `409` and a list of
the missing teams — one lazy team can't be ignored silently. The admin can
override with `force: true`, or wait for the deadline.

**Auto-pass** (the anti-stall fix): any team still unsubmitted at roll time is
simulated with its *latest submitted decision* carried forward, flagged
`auto_pass: true` in the report. Nobody's company freezes because someone
forgot to click submit.

Code: guard + lock in `backend/app/routers/admin.py::roll_quarter()`;
auto-pass in `engine/topaz_engine/db.py::get_or_autopass_decision()`.

---

## 6. What happens when the admin presses "Roll the Quarter"

Two modes, chosen by the `QUARTER_ROLL_MODE` environment variable:

**`sync` mode** (simple, local dev): the API locks the quarter, runs the engine
as a subprocess (`python -m topaz_engine.cli …`), waits, and returns the
result. One moving part.

**`queue` mode** (docker-compose default — the event-driven architecture):

1. API passes the deadlock guard, sets quarter to `locked`, inserts a
   `pending` row into `quarter_jobs` (idempotent — re-rolling returns the
   existing job), writes `quarter.roll.queued` to the audit log, and returns
   **HTTP 202** immediately. The admin's browser doesn't hang.
2. The **engine worker** (`engine/topaz_engine/worker.py`, running as its own
   Docker service) polls `quarter_jobs`, claims one row with
   `SELECT … FOR UPDATE SKIP LOCKED`, and calls `runner.run_quarter()`.
   Because of `SKIP LOCKED`, you can run 3 workers and a job is still only ever
   processed once.
3. The runner sets the quarter to `processing`, runs the pure simulation for
   all teams, writes one `reports` row per team, flips the quarter to
   `published`, marks the job `done`, and audits everything.
4. If the worker crashes mid-job, the quarter is restored to `locked` and the
   job is marked `failed` with the error text — the admin can simply re-roll.
5. The admin UI polls `roll-status` (which includes the job's status) until the
   quarter shows `published`.

This was verified end-to-end against a real PostgreSQL: force-roll → `202`
job `pending` → `python -m topaz_engine.worker --once` → job `done`, quarter
`published`, team report readable (revenue £692,963.00, net profit
£94,365.35 — see §9).

---

## 7. Inside the engine, step by step

`engine/topaz_engine/simulation.py::compute_quarter()` takes
`(industry, year, quarter, teams, macro)` and returns `{team_id: report}`.
It runs in two phases.

### Phase A — demand and production (`_phase_a`, per team)

**Step 1 — macro demand.** Each product×area has a base demand (Table 1).
The macro scenario scales it: GDP growth lifts it, **recession cuts it to 85%**,
each area can have its own trend, exports get a damping factor. Formula sketch:

```
demand = base × (1 + gdp_effect) × (0.85 if recession) × area_factor
```

**Step 2 — attractiveness index.** For every team × product × area, the engine
computes a single score from the marketing decisions:

```
a1 = base_index
   × price_factor        ← (avg_price / own_price)², clamped to [0.25, 4]
   × advertising_factor  ← diminishing returns on ad spend (Table 6)
   × salesforce_factor   ← salespeople per unit of demand (Table 9)
   × quality_factor      ← product improvements + research (Tables 10–11)
   × credit_factor       ← generous credit terms help a little
```

**Step 3 — market shares (cross-elasticity).** Each team's share of demand is
its attractiveness divided by the *sum of all teams'* attractiveness:

```
share_i = a1_i / Σ a1
demand_units_i = share_i × area_demand
```

This is cross-elasticity: if *you* cut your price, your `a1` rises, the total
Σa1 rises, and *everyone else's* share automatically falls — without any team
being modelled explicitly against another.

**Step 4 — production.** The schedule (`make_deliver`) is cut down by three
hard constraints, and the *tightest* one wins:

- **Machine hours** available = machines × shift hours (Table 5); each product
  needs its machine-minutes per unit.
- **Assembly hours** available = assembly workers × (420 + Saturday + Sunday
  hours); each product needs its `assembly_time_minutes`.
- **Materials** on hand; each unit consumes Table 7 quantities.

Then a small rejection rate (quality, Table 10) is scrapped.

### Phase B — money (`_phase_b`, per team)

- **Sales** = min(demand_units, sellable stock + opening stock). Whatever demand
  you can't supply becomes **backlog**.
- **Revenue** = Σ(sales × own price), less early-payment discount for credit
  terms.
- **Cost of sales** = opening stock value + materials used + assembly wages
  (+ shift premium) + machinists' wages + machine running costs − closing stock
  value (valued at Table 21 rates).
- **Overheads**: management budget, promotion spend, sales salaries +
  commission, maintenance, training, R&D, vehicle costs…
- **Depreciation** (Tables 17–18), **interest** (Table 20; overdraft rate =
  central-bank rate + margin), **corporation tax** (Table 22).
- **Dividends** paid per `dividend_rate_pence`.
- **Balance sheet**: fixed assets + stock + debtors − creditors ± cash =
  net assets; share capital + retained profit = net worth. The engine asserts
  **net assets − net worth = 0.0** (verified on every seeded and live report).
- **Cash flow** reconciles: operating ± investing ± financing = change in cash.
- **Share price** moves with profitability and dividends (Table 23 logic) —
  the number teams watch most.

---

## 8. Worked numeric example: the 15% price cut

Verified by running the real engine (4 teams, Year 1 Quarter 1, Product 1,
South area). Teams 1–3 keep the default home price **£110**; team 4 cuts to
**£93.50** (−15%). Everything else identical.

**Price elasticity** (step 2 above):

```
avg_price  = (110 + 110 + 110 + 93.50) / 4 = £105.875
team 4 factor = (105.875 / 93.50)² = 1.2817   ← 28% more attractive on price
others factor = (105.875 / 110)²   = 0.9263
```

**Attractiveness** (all other factors equal): team 4 `a1 = 4.8146`,
others `a1 = 3.4786` (ratio 4.8146/3.4786 = 1.384 = 1.2817/0.9263 ✓).

**Cross-elasticity** (step 3): Σa1 = 4.8146 + 3×3.4786 = 15.2504

```
team 4 demand share = 4.8146 / 15.2504 = 31.57%
each other          = 3.4786 / 15.2504 = 22.81%
area demand ≈ 7,892 units
→ team 4 demand = 2,492 units vs 1,800 each for the others  (+38% demand!)
```

**But production wins the argument:** every team only had ~443 sellable units
(388 produced + 60 opening stock − rejections), so **all four sold 443** and
the market share *of sales* was 25% each. Team 4's price cut bought it 38%
more demand — and a backlog of ~2,049 unfilled units — but not one extra sale.

**The lesson for the viva:** marketing (price, ads, salesforce) decides
*demand*; production (machines, labour, materials) decides *sales*. The engine
models both, in that order, and the report shows both numbers side by side
(`demand` vs `sales` per product×area) so you can see which constraint bit you.

---

## 9. The financial statements (where each number comes from)

Every report JSON has the same top-level sections
(`engine/topaz_engine/simulation.py::_phase_b`):

- **`products`** — 12 rows (3 products × 4 areas): scheduled, produced,
  rejected, demand, sales, backlog, closing stock, price.
- **`pnl`** — sales revenue → cost of sales → gross profit → overheads →
  operating profit → interest → profit before tax → tax → net profit →
  dividends → retained profit.
- **`balance_sheet`** — fixed assets, stock, debtors, creditors, cash,
  overdraft; net assets and net worth (must be equal — identity checked 0.0).
- **`cash_flow`** — trading receipts/payments, tax paid, capital
  receipts/payments, dividends, interest: the full reconciliation of cash.
- **`resources`** — machine/assembly utilisation %, workforce, morale.
- **`group`** — all companies' share prices, dividends, net profits, net
  worths, and market shares of sales per product×area (per the manual: market
  share is "calculated on the number of sales, not orders").
- **`economic`** — the macro scenario that applied, plus next quarter's
  material price (so teams can plan).
- **`meta`** — year/quarter, `published_at`, `auto_pass` flag, `demo_data` flag.

Real numbers from the live end-to-end test (Team 1, Y1Q3, queue mode):
sales revenue **£692,963.00**, net profit **£94,365.35**, share price **£1.66**,
balance-sheet identity **0.0**.

---

## 10. Determinism: same inputs → byte-identical outputs

Three rules, enforced in code:

1. **No random numbers anywhere** in `simulation.py` (grep it — there is no
   `random` import).
2. **Fixed team order** — teams are always processed sorted by
   `company_number`, so dict ordering can't leak in.
3. **No hidden clock** — the report's `published_at` used to call
   `datetime.now()` inside the pure function, which broke byte-identical
   output. Now `compute_quarter(..., now_iso=None)` takes the timestamp as an
   *explicit input*: production passes the current UTC time; tests pass a fixed
   string.

Proof: `engine/tests/test_determinism.py::test_byte_identical_with_fixed_timestamp`
runs the whole quarter twice with `now_iso="2026-01-01T00:00:00+00:00"` and
compares the raw JSON **byte for byte** — passes, along with 13 other tests
(order-independence, roll-forward determinism, table/validation tests).

Why it matters: in a competition, teams must trust that re-running the quarter
(or auditing it later) gives exactly the same Management Reports.

---

## 11. Validation and edge cases

The backend validates every decision save against
`engine/topaz_engine/validation.py` (same code the engine trusts, so the rules
can't drift). Highlights:

- Price ≤ 0 → rejected with an exact error (a £0 price is never simulated).
- Planned spend beyond cash + overdraft limit → rejected (Table 19 overdraft
  formula is exposed as `overdraft_limit(...)` and unit-tested).
- Negative headcounts, impossible shift levels, unknown suppliers → rejected.
- Missing keys fall back to documented defaults (a half-filled form still
  simulates sanely).

Edge cases the system handles deliberately:

- **Nobody submits** → everyone auto-passes on their last submitted decision;
  the quarter still rolls.
- **Worker dies mid-batch** → quarter restored to `locked`, job marked
  `failed` with the error; admin re-rolls (job insert is idempotent).
- **Two admins press roll at once** → the second gets the existing job
  (unique constraint), never a duplicate batch.
- **Recession shock** → demand × 0.85 across the board (verified: P1-south
  demand 7,892 → 6,709).
- **Selling more machines than owned / over-ordering materials** → clamped or
  rejected at validation, never negative assets.

---

## 12. API and events between components (the request trail)

A typical quarter, as HTTP requests:

```
Team:    POST /api/auth/login            → { token }            (JWT, Bearer)
Team:    PUT  /api/decisions/current    → { ok }               (validated + saved)
Team:    POST /api/decisions/current/submit → { ok }           (locked for editing)
Admin:   GET  /api/admin/industries/1/roll-status → { teams:[{submitted…}] }
Admin:   POST /api/admin/industries/1/roll-quarter {"force":true}
                                              → 202 { queued:true, job:{id:1} }
Worker:  claims job 1 … runs batch … job done, quarter published
Team:    GET  /api/reports?year=1&quarter=3 → { pnl, balance_sheet, … }
```

Events worth naming in a viva: login → JWT issue; save → validate → store;
submit → freeze; roll → deadlock-guard → lock → enqueue (`queue`) or subprocess
(`sync`); worker claim (`SKIP LOCKED`) → simulate → publish → audit. Every one
of these leaves an `audit_log` row.

---

## 13. Running and verifying it yourself

```bash
cp .env.example .env && docker compose up --build   # full stack
python3 -m pytest engine/tests -q                    # 14/14 incl. determinism
python3 db/seed_demo_reports.py --dry-run            # 8/8 reports, 13/13 checks
cd frontend && npm run build                         # production bundle
```

Demo logins: team `TOPAZ-DEMO` / group `1` / company `1`–`4` /
identity `ID-1001`–`ID-1004`; admin `admin` / `admin123`.

---

## 14. Likely viva questions (short answers)

**"Why can't you simulate one team at a time?"** — Because market share is
relative: my share = my attractiveness ÷ everyone's attractiveness. You need
all decisions before computing any share. (§2)

**"Where does price elasticity appear in the code?"** —
`simulation.py::_phase_a`, `price_factor = (avg/own)²` clamped to [0.25, 4];
worked example in §8.

**"What stops two workers doing the same quarter twice?"** —
`SELECT … FOR UPDATE SKIP LOCKED` in `worker.py`, plus a unique constraint on
`(industry_id, year, quarter)`. (§6)

**"How do you know the accounts balance?"** — The engine computes net assets
and net worth independently and the seed/test suite asserts their difference
is 0.0 on every report. (§9)

**"What happens if a team never submits?"** — Auto-pass: last submitted
decision carried forward, flagged in the report. (§5)

**"Prove the engine is deterministic."** — No RNG, fixed team ordering, explicit
timestamp input; the byte-identical test in `test_determinism.py`. (§10)

**"Sync vs queue roll — when would you use each?"** — Sync for local/dev and
tiny classes (no extra service); queue for real deployments (admin UI never
blocks, workers scale, crashes are recoverable). (§6)
