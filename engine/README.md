# Topaz-VBE simulation core (`topaz_engine`)

Pure-logic quarter engine. Stdlib only, no I/O, no randomness.

## Files

- `topaz_engine/__init__.py` — `__version__`
- `topaz_engine/constants.py` — `AREAS`, `PRODUCTS`, `TABLES` (T1–T23 values
  from SPEC §5), `DEFAULT_DECISIONS` (SPEC §2), `INITIAL_STATE` (SPEC §9)
- `topaz_engine/validation.py` — `validate_decisions(data, funds) -> list[str]`
  (SPEC §7; missing keys fall back to defaults; exact SPEC error wordings)
- `topaz_engine/simulation.py` — `compute_quarter(industry, year, quarter,
  teams, macro, now_iso=None) -> {team_id: report}` (SPEC §8); also exposes the
  T19 `overdraft_limit(...)` helper
- `topaz_engine/runner.py` — `run_quarter(industry_id, year, quarter)`:
  DB-orchestrated batch (loads teams/decisions/macro, auto-pass, pure
  simulation, writes reports, publishes the quarter)
- `topaz_engine/worker.py` — event-driven consumer of the `quarter_jobs`
  table: claims one `pending` job (`FOR UPDATE SKIP LOCKED`) and runs it via
  `runner.run_quarter`; `python -m topaz_engine.worker --once` processes a
  single job

## Core formulas

- Area demand per product/area: `households × penetration × (1+gdp/100) ×
  (0.85 if recession else 1) × (1−inflation/400)`, export × 0.15.
  Penetration: P1 0.0011, P2 0.0007, P3 0.0004 (documented assumptions).
- Attractiveness: `A = promo × salesforce × quality × price × availability`;
  `promo = 1+0.15·ln(1+promo£'000)`, `salesforce = 1+2·(allocated/(outlets/500))`,
  `quality = 1+0.06·(star−1)` with `star = clamp(1+research£/20000+improvement,1,5)`,
  `price = clamp((avg_price/own_price)², 0.2, 5)` (home price for home areas,
  export price for export); availability via a second pass —
  `avail = min(1, (sellable+opening)/demand_pass1)`, then shares `A/ΣA`,
  `demand = share × area_demand`.
- Production: scheduled units scaled by the tightest of machine hours
  (`machines × T5[shift]`), assembly hours (`workers × (420+Sat+Sun)`),
  material (`stock + delivered`); `produced = floor(scheduled × min_ratio)`,
  allocated pro-rata (deterministic remainder order); rejects =
  `produced × max(0.005, 0.03−0.01·star)`.
- Sales = `min(demand, sellable + opening_stock)`; revenue less T23 credit
  discount; cost of sales = opening stock + materials + wages + running −
  closing stock (T21 valuations); tax = 30% of positive PBT (quarterly
  accrual); dividend = pence/100 × 1,000,000 shares.
- Balance sheet rolls forward with `cash_invested` as the plug
  (`net_worth + CL − non_cash_assets`; negative plug becomes bank overdraft),
  so it always balances; `overdraft_limit` per T19 (reported for
  validation/credit use, not enforced as an in-quarter cap).
- Share price: `prev × (1 + 0.6 × net_profit/prev_net_worth)`, clamped
  [£0.10, £50.00], rounded to pence.

## Documented simplifications vs the manual

- Demand penetration, elasticities and the 0.15 export dampening are
  documented assumptions (no proprietary engine exists to copy).
- Supplier deliveries arrive in full in-quarter; material purchases valued at
  the opening price; closing material stock at 50% of the current price (T21).
- Assembly weekend overtime (Sat+Sun per T16) is always available; no
  overtime decision field exists in this replica.
- Machinist wage £10.50/hr is an assumption (rate not stated in the tables).
- Maintenance = contracted hrs × £60 + 5% × hrs × £120 (fleet total, per the
  task formula); extra 5% is deterministic, not random.
- Transport (T9/T10/T11 vehicle running/driver costs) is not costed; vehicles
  only affect depreciation and the balance sheet.
- Creditors: next-quarter items (research, sales payroll, warehousing,
  material purchases, 50% of machine order) + quarter-after-next items
  (promotion, info, guarantee, maintenance, credit control) for the current
  quarter plus the previous quarter's after-next items (T22, simplified).
- Tax assessed quarterly (manual assesses in Q4); unsecured loans stay 0;
  new machines install the same quarter they are ordered (only the £100k
  order payment falls in-quarter, matching T18/T22).
- `material_price_next_q` echoes the current quarter's price (no forecast).

## Determinism guarantee

Identical inputs → byte-identical reports: pure functions, no `random`
module, no wall-clock in any calculation (`published_at` is metadata only),
ties broken by company_number order, teams processed sorted by company_number.
Proven by `engine/tests/test_determinism.py` (run twice → identical SHA-256;
team input order irrelevant; Q1→Q2 roll-forward reproducible).
