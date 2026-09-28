# Topaz-VBE Replica — Locked Specification (single source of truth)

All builders (db, backend, engine, frontend) MUST conform to this file.
It is derived from the public Topaz-VBE manual material (decision-form screenshot
+ Tables 1–23). No proprietary backend code exists; everything is re-implemented.

## 1. Concepts & terminology (keep original wording)

- Industry = a simulation run containing up to 8 competing teams (companies).
- Team/Company identified by: Simulation Code, Group Number, Company Number, Identity Number.
- Time is discrete: Year + Quarter (Q1..Q4). Quarters move: `open` → `locked` → `processing` → `published`.
- Batch processing: teams submit decisions while quarter is `open`; the engine
  simulates the quarter for ALL teams at once; reports are published simultaneously.
- "SHARE PRICE IS THE CRITERION BY WHICH PERFORMANCE IS JUDGED." (manual)
- Money: pounds (£). Form labels marked (£'000) are entered in thousands.

## 2. Decision form fields (from the decision-form screenshot)

JSON object stored as `decisions.data` (JSONB). Field names are LOCKED:

```jsonc
{
  "product_improvements": [false, false, false],        // tick per product 1..3
  "prices": {
    "export": [120.0, 180.0, 260.0],                   // £ per unit, product 1..3
    "home":   [110.0, 165.0, 240.0]                    // £ per unit (all home areas)
  },
  "promotion": {                                       // £'000 per product 1..3
    "trade_press":   [8.0, 6.0, 4.0],
    "advertising":   [20.0, 15.0, 10.0],
    "support":       [5.0, 4.0, 3.0],
    "merchandising": [6.0, 5.0, 4.0]
  },
  "assembly_time_minutes": [110, 160, 320],            // per product
  "salespeople": {"export": 2, "south": 4, "west": 3, "north": 5},
  "sales_remuneration": {"quarterly_salary_000": 3.0, "commission_pct": 5.0},
  "assembly_wage": {"pounds": 9, "pence": 50},         // hourly rate
  "shift_level": 1,                                    // 1=Single, 2=Double, 3=Treble
  "management_budget_000": 45.0,
  "contract_maintenance_hours": 40,
  "machines_to_sell": 0,
  "dividend_rate_pence": 4.0,
  "days_credit_allowed": 30,
  "vans_to_buy": 0, "vans_to_sell": 0,                 // "vans" = vehicles
  "info_wanted": {"other_companies": false, "market_shares": false},
  "make_deliver": {                                    // units scheduled per area/product
    "export": [800, 500, 300],
    "south":  [600, 400, 200],
    "west":   [400, 300, 150],
    "north":  [900, 600, 350]
  },
  "research_expenditure_000": 12.0,
  "salespeople_changes": {"recruit": 0, "dismiss": 0, "train": 2},
  "assembly_changes":   {"recruit": 2, "dismiss": 0, "train": 4},
  "raw_material": {"units_to_order": 4000, "supplier_no": 1, "num_deliveries": 2},
  "new_machines_to_order": 0
}
```

## 3. Database schema (PostgreSQL)

```sql
-- industries(id SERIAL PK, name TEXT, simulation_code TEXT UNIQUE NOT NULL,
--            status TEXT DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT now())
-- teams(id SERIAL PK, industry_id INT FK, group_number INT, company_number INT,
--       identity_number TEXT UNIQUE NOT NULL, name TEXT, active BOOL DEFAULT true,
--       created_at TIMESTAMPTZ DEFAULT now(),
--       UNIQUE(industry_id, group_number, company_number))
-- admins(id SERIAL PK, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)
-- quarters(id SERIAL PK, industry_id INT FK, year INT, quarter INT,
--          status TEXT DEFAULT 'open' CHECK (status IN ('open','locked','processing','published')),
--          auto_pass_minutes INT DEFAULT 10080, deadline_at TIMESTAMPTZ,
--          published_at TIMESTAMPTZ, UNIQUE(industry_id, year, quarter))
-- decisions(id SERIAL PK, industry_id INT FK, team_id INT FK, year INT, quarter INT,
--           data JSONB NOT NULL, submitted BOOL DEFAULT false,
--           submitted_at TIMESTAMPTZ, auto_pass BOOL DEFAULT false,
--           created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(),
--           UNIQUE(team_id, year, quarter))
-- reports(id SERIAL PK, industry_id INT FK, team_id INT FK, year INT, quarter INT,
--         report JSONB NOT NULL, created_at TIMESTAMPTZ DEFAULT now(),
--         UNIQUE(team_id, year, quarter))
-- macro(id SERIAL PK, industry_id INT FK, year INT, quarter INT,
--       inflation_pct NUMERIC DEFAULT 0, material_price_change_pct NUMERIC DEFAULT 0,
--       recession BOOL DEFAULT false, note TEXT,
--       central_bank_rate NUMERIC DEFAULT 8.0, gdp_growth_pct NUMERIC DEFAULT 2.5,
--       unemployment_pct NUMERIC DEFAULT 5.0, UNIQUE(industry_id, year, quarter))
-- audit_log(id SERIAL PK, industry_id INT FK NULL, actor TEXT, action TEXT,
--           details JSONB, created_at TIMESTAMPTZ DEFAULT now())
```

## 4. REST API contract (base path /api, JSON, JWT Bearer auth)

Team auth = login with simulation_code + group_number + company_number + identity_number
(identity_number is the secret credential). Admin auth = username + password.

- `POST /api/auth/login` {simulation_code, group_number, company_number, identity_number}
  → 200 {token, role:"team", team:{id,name,group_number,company_number}, industry:{id,name,simulation_code}}
  → 401 {error:"Invalid team credentials ..."} on any mismatch (do not say which field).
- `POST /api/auth/admin-login` {username, password} → 200 {token, role:"admin"} / 401.
- `GET /api/me` (team) → {team:{...}, industry:{...}, current_quarter:{year,quarter,status,deadline_at}, submitted:bool}
- `GET /api/quarters` (team) → [{year, quarter, status}] for my industry, ascending.
- `GET /api/decisions/current` (team) → {year, quarter, submitted, submitted_at, auto_pass, data:{...}|null}
  (data = draft if unsubmitted, else the submitted decisions; editable again only while quarter `open`).
- `PUT /api/decisions/current` (team) {data:{...full object...}}
  → 200 {ok:true, warnings:[...]} ; → 422 {ok:false, errors:["Price for Product 2 (Home market) must be greater than 0.", ...]}
  Draft save ALSO validates; frontend shows errors and blocks submit, but draft is stored.
- `POST /api/decisions/current/reset` (team) → {ok:true, data:{...defaults...}} resets form to defaults.
- `POST /api/decisions/current/submit` (team) → 200 {ok:true, confirmation:"Decisions for Year 1 Quarter 2 submitted at <ISO time>. Status: LOCKED — awaiting quarter processing."}
  → 409 {ok:false, error:"Quarter is no longer open for submissions."} if quarter not open.
  → 422 {ok:false, errors:[...]} on validation failure.
- `GET /api/reports?year=Y&quarter=Q` (team) → full report JSON (§6). 404 {error:"Report not published yet..."} if quarter not published. Teams may read any PUBLISHED quarter of their own industry (own report + group/competitor section inside it).
- `GET /api/tables` (team) → Tables 1–23 reference data (§5) for the Manual page.
- Admin (role admin required, 403 otherwise):
  - `GET /api/admin/industries` → [{id,name,simulation_code,status,team_count,current_quarter}]
  - `POST /api/admin/industries` {name, simulation_code} → 201 {id,...}
  - `GET /api/admin/industries/{id}` → {industry, teams:[{id,name,group_number,company_number,identity_number,active}], quarters:[...], macro:[...]}
  - `POST /api/admin/industries/{id}/teams` {name, group_number, company_number} → 201 {id, identity_number, ...} (server generates identity_number like "ID-XXXX")
  - `POST /api/admin/industries/{id}/quarters` {year, quarter, auto_pass_minutes?} → 201 (opens new quarter; previous must be published)
  - `POST /api/admin/industries/{id}/shocks` {year, quarter, inflation_pct?, material_price_change_pct?, recession?, note?} → upsert macro row
  - `GET /api/admin/industries/{id}/roll-status` → {year, quarter, status, deadline_at, all_submitted:bool, deadline_passed:bool, teams:[{company_number,name,submitted,submitted_at}]}
  - `POST /api/admin/industries/{id}/roll-quarter` {force?:bool}
    → 200 {ok:true, summary:{year,quarter,teams_processed,auto_passed:[...], published_at}}
    → 409 {ok:false, error:"Deadlock guard: ...", missing:[{company_number,name}], deadline_at} when not all submitted AND deadline not passed AND !force.
  - `GET /api/admin/audit` → audit_log rows desc.

Validation errors (§7) are returned as plain-language strings in `errors[]`.

## 5. Engine parameters — Tables 1–23 (exact values from the manual)

- AREAS = south, west, north, export. PRODUCTS = 1, 2, 3.
- T3 manufacturing: P1 {mach 60min, assy 100min, mat 1}; P2 {75, 150, 2}; P3 {120, 300, 3}.
- T5 machine hours/quarter: single 576 (4 machinists/machine), double 1068 (8), treble 1602 (12).
- T4 maintenance: contracted £60/hr/machine; uncontracted £120/hr.
- T8: supervision £10,000/shift; production overheads £2,000/machine; machine running £7/hr; planning £1/unit.
- T6 scrap: £20/£40/£60. T7 guarantee servicing: £60/£120/£200.
- T9 vehicle capacity: 40/40/20 units (mixed loads allowed).
- T10 journey days: south 1, west 2, north 4, export 6.
- T11: driver wages etc £7,000/vehicle; own running £50/day; hire £200/day.
- T12: factory storage 2000 units; warehouse fixed £3,750/q; admin £3,250/q; per order £750; external storage £1.50/unit; market-area product storage £2/unit.
- T14 suppliers: 0:{0%,nil,1,1}; 1:{10%,£200,1,1}; 2:{15%,£300,1000,10000}; 3:{30%,£100,n/a,50000, 12 weekly deliveries → num_deliveries must be 0}.
- T15 personnel dept: salesperson {1500,5000,6000}; assembly {1200,3000,4500}; machinist {750,1500,n/a} (recruit,dismiss,train).
- T16 worker hours/q: basic 420; Saturday +84 (single) / +42 (double,treble); Sunday +72; shift premium 0 / 1/3 / 2/3.
- T17: machinist min paid 400h/q; assembly min wage £8.50/h; unskilled:skilled 65%; min sales salary £2,000/q; min management budget £40,000/q.
- T18: machine £200,000 (£100k at order, £100k on installation); vehicle £15,000; depreciation machine 2.5%/q, vehicle 6.25%/q.
- T19 overdraft limit = 100%×cash_invested + 50%×(product_stocks + machines + material_stocks + debtors) + 25%×property − 100%×(tax_due + creditors); negative → 0. Creditworthiness for machines = overdraft_limit − bank_overdraft − unsecured_loans − £100,000×machines_ordered_last_q.
- T20: tax 30%/yr; fixed overheads £10,000/q; variable overhead 0.25%; credit control £1.50/unit sold; interest: investments = bank_rate−2%, overdraft = bank_rate+4%, unsecured = bank_rate+10%.
- T21: product stock valuation £80/£120/£200 per unit; materials = 50% of last quarter's material price.
- T22 creditor timing: advertising/guarantee/hired-transport/maintenance/external-stock/business-intel → paid quarter-after-next (creditors); product-development/personnel/warehousing/misc/materials-purchased(100%)/machines(50%) → paid next quarter. (Engine: simplified per §8, documented.)
- T23 credit discount: ≤7 days 10%; 8–15 7.5%; 16–29 5%; ≥30 nil. (Engine uses days_credit_allowed → discount tier for revenue adjustment; documented.)
- T1 households: south 7m (1/2/4), west 4m (1/1/2), north 13m (1/3/9), export 80m (10/15/55); outlets 3000/2000/4000/20000.
- T2: salesperson expenses £3,000/q; competitor info £5,000; market-share info £5,000 (charged when info_wanted ticks are set).

## 6. Report JSON (engine output, stored in reports.report) — keys LOCKED

Top-level keys: meta, decisions, resources, products, overheads, pnl, balance_sheet,
cash_flow, group, economic. (Detailed sub-keys per the parent task description;
engine builder defines exact sub-keys but MUST include all of:)
- meta: industry_id, simulation_code, group_number, company_number, company_name, year, quarter, published_at, auto_pass(bool), demo_data(bool)
- decisions: echo of the submitted decision data
- resources: machines{owned,new_installed,sold,hours_available,hours_used,utilisation_pct,machinists}, assembly{workers,hours_available,hours_used,utilisation_pct,wage_rate}, vehicles{owned,bought,sold}, materials{opening_stock,ordered,delivered,used,closing_stock,price_per_1000}
- products: 12 rows {product, area, scheduled, produced, rejected, demand, sales, backlog, closing_stock, price, improvement}
- overheads: advertising, trade_press, support, merchandising, sales_force, research, management, maintenance, supervision, production_overheads, info_charges, credit_control, guarantee_servicing, warehousing, total
- pnl: sales_revenue, opening_stock_value, materials, assembly_wages, machinists_wages, machine_running, closing_stock_value, cost_of_sales, gross_profit, total_overheads, operating_profit, interest_received, interest_paid, depreciation, profit_before_tax, tax_assessed, net_profit, dividend_paid, retained_profit
- balance_sheet: property, machines, vehicles, fixed_assets, product_stocks, material_stocks, debtors, cash_invested, total_assets, tax_due, creditors, bank_overdraft, unsecured_loans, current_liabilities, net_assets, share_capital, reserves, net_worth, overdraft_limit
- cash_flow: trading_receipts, trading_payments, tax_paid, net_operating, interest_received, capital_receipts, capital_payments, net_investing, interest_paid, dividends_paid, net_financing, net_cash_flow
- group: companies[{company_number, company_name, share_price, dividend_pct, net_profit, net_worth}], market_shares{area:{product:[shares per company]}}
- economic: gdp_growth_pct, unemployment_pct, central_bank_rate, inflation_pct, recession, material_price_next_q

## 7. Validation rules (backend enforces on PUT/POST decisions; engine assumes valid)

1. All 6 prices > 0 → else "Price for Product N (Export market) must be greater than 0." (price of 0 is rejected, never simulated).
2. assembly_time_minutes[p] ≥ minimum assembly minutes (100/150/300) → "Assembly time for Product N cannot be below the minimum of M minutes."
3. shift_level ∈ {1,2,3}.
4. sales quarterly salary ≥ £2,000 (2.0 in £'000); management budget ≥ £40,000 (40.0).
5. supplier_no ∈ {0,1,2,3}; supplier 3 requires num_deliveries = 0 (12 automatic weekly deliveries).
6. All counts/quantities ≥ 0 integers; percentages 0–100.
7. Affordability: estimated committed spend = (promotion total + research + management budget)×1000 + salesperson payroll estimate + assembly wage bill estimate + material order cost (units × supplier price) + machines×£100,000 + vehicles×£15,000 ≤ cash_invested + overdraft_limit (from last published report; initial state if none). Else: "Committed spend £X exceeds available funds £Y (cash + overdraft limit). Reduce ..."
8. dividend_rate_pence ≥ 0; days_credit_allowed ≥ 0.
Edge cases: unsubmitted team at roll → auto-pass carries forward last submitted decisions (flagged auto_pass:true in decisions + report meta); negative overdraft limit → 0; identical inputs → identical outputs (determinism).

## 8. Engine quarter flow (deterministic; document any simplification vs the manual)

1. Load quarter (status must be open/locked → set processing), industry, macro, all active teams sorted by company_number, their decisions (auto-pass fallback).
2. Macro demand per product/area from T1 households × penetration × (1+gdp_growth) × recession factor × (1−inflation drag). Penetration & elasticities are DOCUMENTED ASSUMPTIONS in engine/README (no proprietary engine exists to copy).
3. Attractiveness index per team/product/area:
   A = promo_factor × salesforce_factor × quality_factor × price_factor × availability_factor
   - price_factor = (avg_market_price / own_price)^2.0, clamped [0.2, 5]  → price elasticity
   - cross-elasticity emerges from share_i = A_i / ΣA (competitor cuts lower your share automatically)
   - promo_factor = 1 + 0.15×ln(1 + advertising_£/1000); salesforce_factor from allocated salespeople vs area outlets; quality_factor from research spend + major improvements (star rating 1–5).
4. demand_units = share × area_demand. sales = min(demand, produced + opening_stock).
5. Production: scheduled = Σ make_deliver. machine_hours_needed = Σ units×mach_min/60 ≤ machines×T5(shift); assembly_hours_needed = Σ units×max(assembly_time, min)/60 ≤ workers×420(+overtime); material_needed = Σ units×mat_content ≤ stock + deliveries. produced = min across constraints; rejects = deterministic quality function.
6. Financials per manual line items (§5/§6): revenue (less T23 credit discount), cost of sales (opening stock + materials + wages + running − closing stock), overheads, depreciation (2.5%/6.25%), interest (T20 on avg balances), tax 30% accrued quarterly (documented simplification: manual assesses in Q4), dividends = dividend_rate_pence/100 × 1,000,000 shares, retained → reserves.
7. Balance sheet roll-forward; overdraft_limit per T19; share_price update deterministic: new = old × (1 + 0.6 × net_profit/net_worth_prev) bounded [£0.10, £50], rounded to pence.
8. Cash flow per manual sections (simplified creditor timing per T22, documented).
9. Write reports rows (demo_data=false), set quarter published, audit log entry. All teams read simultaneously.

Determinism: pure functions; NO random module in simulation math (any tie-break by company_number). Tests must prove: run twice → byte-identical report JSON; Table 19 example check; price=0 never reaches engine (validation test).

## 9. Initial company state (new team, before Q1)

machines 8, vehicles 6, salespeople 12, assembly_workers 48, machinists 32,
cash_invested £400,000, bank_overdraft £0, unsecured_loans £0,
share_capital £1,000,000 (1,000,000 × £1 shares), reserves £200,000, property £250,000,
material_stock 2000 units @ £500/1000 units, product stocks 60 units per product per area,
share_price £1.50, shift_level 1, assembly wage £9.00.

## 10. Demo seed

Industry "Demo Industry", simulation_code "TOPAZ-DEMO"; 4 teams (companies 1–4,
group 1, names: "Alpha Manufacturing", "Beta Industries", "Gamma Traders", "Delta Works");
identity numbers ID-1001..ID-1004; admin admin/admin123 (DEMO — change in production).
Quarters: Y1Q1 published, Y1Q2 published, Y1Q3 open. Q1/Q2 reports are clearly-labeled
demonstration data (meta.demo_data=true), internally consistent (revenue = price×sales etc.).
