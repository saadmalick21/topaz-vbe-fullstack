#!/usr/bin/env python3
"""
Topaz-VBE replica — demo report seeder.

For each of the 4 demo teams x quarters (Y1Q1, Y1Q2) this script inserts:

  * a submitted decisions row (full decision JSON per SPEC section 2), and
  * a published report row whose JSON carries every top-level key from
    SPEC section 6 (meta, decisions, resources, products, overheads, pnl,
    balance_sheet, cash_flow, group, economic) with internally consistent
    numbers, meta.demo_data = true and meta.auto_pass = false.

The demo numbers are built bottom-up from 12 product/area rows so the
accounting identities hold by construction; every report is then checked
against five invariants and PASS/FAIL is printed per report. Nothing is
written to the database unless every check passes.

All figures are deterministic (no randomness): re-running the script
produces byte-identical report JSON (apart from submitted_at/published_at
timestamps taken from the database).

Requires the demo seed from db/migrations/002_seed.sql to be applied first
(industry TOPAZ-DEMO, 4 teams, published quarters Y1Q1/Y1Q2, macro rows).

Usage:
    export DATABASE_URL="postgresql://user:pass@host:5432/topaz"
    python3 db/seed_demo_reports.py            # insert into the database
    python3 db/seed_demo_reports.py --dry-run  # build + validate, no DB writes

Dependencies: Python 3.12 stdlib + psycopg (only needed for real DB mode;
--dry-run works with the stdlib alone).
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants from SPEC section 5 (manual tables) and section 9 (initial state)
# ---------------------------------------------------------------------------

AREAS = ["south", "west", "north", "export"]          # SPEC T1 areas
PRODUCTS = [1, 2, 3]

MACH_MINUTES = {1: 60, 2: 75, 3: 120}                # T3 machine minutes / unit
ASSY_MIN_FLOOR = {1: 100, 2: 150, 3: 300}            # T3 minimum assembly minutes
MAT_CONTENT = {1: 1, 2: 2, 3: 3}                     # T3 material units / unit
STOCK_VALUATION = {1: 80.0, 2: 120.0, 3: 200.0}      # T21 product stock £/unit

MACHINE_HOURS_Q = 576.0          # T5: single-shift machine hours / quarter
WORKER_HOURS_Q = 420.0           # T16: basic worker hours / quarter
MACHINE_RUNNING_PER_HR = 7.0     # T8: machine running cost £/hour
SUPERVISION_PER_SHIFT = 10000.0  # T8: supervision £/shift
PROD_OVERHEAD_PER_MACHINE = 2000.0  # T8: production overheads £/machine
MACHINIST_WAGE = 10.50           # demo assumption: machinist £/hour
MACHINE_DEPR_Q = 0.025           # T18: machine depreciation / quarter
VEHICLE_DEPR_Q = 0.0625          # T18: vehicle depreciation / quarter
TAX_RATE = 0.30                  # T20: corporation tax
CREDIT_CONTROL_PER_UNIT = 1.50   # T20: credit control £/unit sold
SALES_EXPENSE_PER_Q = 3000.0     # T2: salesperson expenses £/quarter
INFO_CHARGE = 5000.0             # T2: competitor / market-share info charge
MAINT_RATE_PER_HR = 60.0         # T4: contracted maintenance £/hour
WAREHOUSE_FIXED = 3750.0         # T12: warehousing fixed £/quarter
WAREHOUSE_PER_ORDER = 750.0      # T12: warehousing £/order
GUARANTEE_PER_UNIT = {1: 0.80, 2: 1.20, 3: 1.60}  # demo assumption £/unit sold
SUPPLIER1_FIXED_FEE = 200.0      # T14 supplier 1 fixed charge (demo assumption)
SHARES_OUTSTANDING = 1_000_000   # SPEC section 8: dividends per 1,000,000 shares

MATERIAL_PRICE = {(1, 1): 500.0, (1, 2): 512.0}      # £ per 1000 units
MATERIAL_PRICE_NEXT = {(1, 1): 512.0, (1, 2): 525.0}  # demo assumption for Q3

# Base demand (units sold) per product/area for a "typical" team/quarter.
# Sized so machine hours (~3,900h incl. team/quarter uplifts) stay within the
# 8-machine single-shift capacity of 8 x 576 = 4,608h (SPEC section 9).
BASE_SALES = {
    1: {"south": 350, "west": 240, "north": 500, "export": 430},
    2: {"south": 230, "west": 165, "north": 320, "export": 275},
    3: {"south": 120, "west": 90,  "north": 190, "export": 170},
}

BASE_PRICES_HOME = [118.0, 178.0, 262.0]    # £/unit, products 1..3
BASE_PRICES_EXPORT = [128.0, 192.0, 282.0]  # £/unit, products 1..3

BASE_PROMO_000 = {  # £'000 per product 1..3
    "trade_press":   [7.0, 5.0, 4.0],
    "advertising":   [16.0, 12.0, 8.0],
    "support":       [4.0, 3.0, 2.0],
    "merchandising": [5.0, 4.0, 3.0],
}

# Per-team commercial posture (varied but plausible; deterministic).
TEAM_PARAMS = {
    1: {"price_mult": 1.00, "vol_mult": 1.00, "promo_mult": 1.00,
        "salary_000": 3.0, "commission_pct": 5.0, "wage": (9, 50),
        "mgmt_000": 45.0, "maint_hours": 40, "div_pence": 4.0,
        "credit_days": 30, "research_000": 12.0,
        "improvements": [False, False, False], "info": (True, False),
        "assy_minutes": [110, 160, 320],
        "salespeople": {"export": 2, "south": 4, "west": 3, "north": 5}},
    2: {"price_mult": 1.10, "vol_mult": 0.92, "promo_mult": 1.00,
        "salary_000": 3.2, "commission_pct": 6.0, "wage": (9, 75),
        "mgmt_000": 48.0, "maint_hours": 44, "div_pence": 3.0,
        "credit_days": 30, "research_000": 14.0,
        "improvements": [True, False, False], "info": (True, True),
        "assy_minutes": [115, 165, 325],
        "salespeople": {"export": 2, "south": 5, "west": 3, "north": 5}},
    3: {"price_mult": 0.93, "vol_mult": 1.10, "promo_mult": 0.80,
        "salary_000": 2.8, "commission_pct": 4.0, "wage": (9, 25),
        "mgmt_000": 42.0, "maint_hours": 36, "div_pence": 2.5,
        "credit_days": 15, "research_000": 10.0,
        "improvements": [False, False, True], "info": (False, False),
        "assy_minutes": [105, 155, 315],
        "salespeople": {"export": 3, "south": 4, "west": 2, "north": 4}},
    4: {"price_mult": 1.00, "vol_mult": 0.96, "promo_mult": 1.10,
        "salary_000": 3.0, "commission_pct": 5.5, "wage": (10, 0),
        "mgmt_000": 46.0, "maint_hours": 42, "div_pence": 2.0,
        "credit_days": 45, "research_000": 13.0,
        "improvements": [False, True, False], "info": (False, True),
        "assy_minutes": [112, 162, 322],
        "salespeople": {"export": 2, "south": 4, "west": 4, "north": 4}},
}

# Quarter-2 adjustments: modest volume growth, small price rises, slightly
# higher pay/research/management budgets, a touch more promotion, and each
# team's own dividend decision.
Q2_VOLUME_FACTOR = 1.06
Q2_PRICE_BUMP = [2.0, 3.0, 4.0]
Q2_DIV_PENCE = {1: 4.5, 2: 3.5, 3: 3.0, 4: 2.5}

# Opening balance sheet, SPEC section 9. machines_net is the balancing plug:
# net_worth (£1,200,000) + current_liabilities (£205,000) - all other assets
# (£959,000) = £446,000, so the opening books balance exactly.
INIT_STATE = {
    "machines_net": 446000.0,
    "vehicles_net": 72000.0,
    "property": 250000.0,
    "share_capital": 1000000.0,
    "reserves": 200000.0,
    "cash": 400000.0,
    "tax_due": 45000.0,
    "creditors": 160000.0,
    "debtors": 140000.0,
    "material_units": 2000,
    "share_price": 1.50,
    "tax_assessed_prev": 0.0,
}

REQUIRED_TOP_KEYS = ["meta", "decisions", "resources", "products", "overheads",
                     "pnl", "balance_sheet", "cash_flow", "group", "economic"]

REQUIRED_META_KEYS = ["industry_id", "simulation_code", "group_number",
                      "company_number", "company_name", "year", "quarter",
                      "published_at", "auto_pass", "demo_data"]

# All decision-form field names from SPEC section 2 (locked).
DECISION_KEYS = ["product_improvements", "prices", "promotion",
                 "assembly_time_minutes", "salespeople", "sales_remuneration",
                 "assembly_wage", "shift_level", "management_budget_000",
                 "contract_maintenance_hours", "machines_to_sell",
                 "dividend_rate_pence", "days_credit_allowed", "vans_to_buy",
                 "vans_to_sell", "info_wanted", "make_deliver",
                 "research_expenditure_000", "salespeople_changes",
                 "assembly_changes", "raw_material", "new_machines_to_order"]

TOL = 0.01
EPS = 1e-9


def r2(x):
    """Round money to 2dp; normalise -0.0 to 0.0."""
    v = round(float(x), 2)
    return 0.0 if v == 0 else v


# ---------------------------------------------------------------------------
# Decision form (SPEC section 2 field names, locked)
# ---------------------------------------------------------------------------

def build_decisions(cn, year, quarter, sched_by_area, units_to_order):
    p = TEAM_PARAMS[cn]
    is_q2 = (year, quarter) == (1, 2)

    bump = Q2_PRICE_BUMP if is_q2 else [0.0, 0.0, 0.0]
    prices_home = [r2((b + d) * p["price_mult"]) for b, d in zip(BASE_PRICES_HOME, bump)]
    prices_export = [r2((b + d) * p["price_mult"]) for b, d in zip(BASE_PRICES_EXPORT, bump)]

    pm = p["promo_mult"] * (1.05 if is_q2 else 1.0)
    promo = {k: [r2(v * pm) for v in vals] for k, vals in BASE_PROMO_000.items()}

    salary_000 = r2(p["salary_000"] + (0.1 if is_q2 else 0.0))
    research_000 = r2(p["research_000"] + (1.0 if is_q2 else 0.0))
    mgmt_000 = r2(p["mgmt_000"] + (1.0 if is_q2 else 0.0))
    div_pence = Q2_DIV_PENCE[cn] if is_q2 else p["div_pence"]
    wage_pounds, wage_pence = p["wage"]

    return {
        "product_improvements": list(p["improvements"]),
        "prices": {"export": prices_export, "home": prices_home},
        "promotion": promo,
        "assembly_time_minutes": list(p["assy_minutes"]),
        "salespeople": dict(p["salespeople"]),
        "sales_remuneration": {"quarterly_salary_000": salary_000,
                              "commission_pct": p["commission_pct"]},
        "assembly_wage": {"pounds": wage_pounds, "pence": wage_pence},
        "shift_level": 1,
        "management_budget_000": mgmt_000,
        "contract_maintenance_hours": p["maint_hours"],
        "machines_to_sell": 0,
        "dividend_rate_pence": div_pence,
        "days_credit_allowed": p["credit_days"],
        "vans_to_buy": 0,
        "vans_to_sell": 0,
        "info_wanted": {"other_companies": p["info"][0],
                        "market_shares": p["info"][1]},
        "make_deliver": {area: [sched_by_area[area][0],
                                sched_by_area[area][1],
                                sched_by_area[area][2]] for area in AREAS},
        "research_expenditure_000": research_000,
        "salespeople_changes": {"recruit": 0, "dismiss": 0, "train": 2},
        "assembly_changes": {"recruit": 2, "dismiss": 0, "train": 4},
        "raw_material": {"units_to_order": int(units_to_order),
                         "supplier_no": 1,
                         "num_deliveries": 2},
        "new_machines_to_order": 0,
    }


# ---------------------------------------------------------------------------
# Quarter simulation: bottom-up from 12 product/area rows
# ---------------------------------------------------------------------------

def simulate_quarter(cn, company_name, year, quarter, state, macro,
                     meta_extra):
    """Build (decisions, report_core, end_state) for one team/quarter.

    report_core has every SPEC section 6 top-level key except "group",
    which is attached later once all teams' results for the quarter exist.
    """
    p = TEAM_PARAMS[cn]
    is_q2 = (year, quarter) == (1, 2)
    qf = Q2_VOLUME_FACTOR if is_q2 else 1.0
    qidx = 1 if is_q2 else 0

    # ---- 1. production plan: 12 product/area rows -------------------------
    rows = []
    for prod in PRODUCTS:
        for ai, area in enumerate(AREAS):
            sales = int(round(BASE_SALES[prod][area] * p["vol_mult"] * qf))
            closing = 40 + ((cn * 7 + prod * 13 + ai * 5 + qidx * 3) % 41)
            opening = state["product_opening"][(prod, area)]
            produced = sales + closing - opening
            scheduled = int(round(produced * 1.02))
            backlog = int(round(sales * 0.04)) if (cn + prod + ai + qidx) % 3 == 0 else 0
            demand = sales + backlog
            rejected = int(round(produced * (0.01 + ((cn + prod + ai) % 3) * 0.005)))
            rows.append({"product": prod, "area": area, "sales": sales,
                         "produced": produced, "scheduled": scheduled,
                         "closing": closing, "opening": opening,
                         "demand": demand, "backlog": backlog,
                         "rejected": rejected})

    # ---- 2. decisions (needs scheduled volumes + material order) ----------
    mat_used = sum(r["produced"] * MAT_CONTENT[r["product"]] for r in rows)
    units_to_order = int(math.ceil(mat_used * 1.15 / 100.0) * 100)
    sched_by_area = {area: [0, 0, 0] for area in AREAS}
    for r in rows:
        sched_by_area[r["area"]][r["product"] - 1] = r["scheduled"]
    decisions = build_decisions(cn, year, quarter, sched_by_area, units_to_order)

    prices = decisions["prices"]
    wage_rate = decisions["assembly_wage"]["pounds"] + decisions["assembly_wage"]["pence"] / 100.0
    assy_minutes = decisions["assembly_time_minutes"]
    n_salespeople = sum(decisions["salespeople"].values())

    for r in rows:
        r["price"] = prices["export"][r["product"] - 1] if r["area"] == "export" \
            else prices["home"][r["product"] - 1]

    # ---- 3. profit & loss -------------------------------------------------
    sales_revenue = r2(sum(r["sales"] * r["price"] for r in rows))
    total_units_sold = sum(r["sales"] for r in rows)

    opening_stock_value = r2(sum(r["opening"] * STOCK_VALUATION[r["product"]] for r in rows))
    closing_stock_value = r2(sum(r["closing"] * STOCK_VALUATION[r["product"]] for r in rows))

    mat_price = MATERIAL_PRICE[(year, quarter)]
    materials_cost = r2(mat_used * mat_price / 1000.0)

    assembly_hours = sum(r["produced"] * assy_minutes[r["product"] - 1] / 60.0 for r in rows)
    assembly_wages = r2(assembly_hours * wage_rate)

    machinist_hours = sum(r["produced"] * MACH_MINUTES[r["product"]] / 60.0 for r in rows)
    machinists_wages = r2(machinist_hours * MACHINIST_WAGE)
    machine_running = r2(machinist_hours * MACHINE_RUNNING_PER_HR)

    cost_of_sales = r2(opening_stock_value + materials_cost + assembly_wages
                       + machinists_wages + machine_running - closing_stock_value)
    gross_profit = r2(sales_revenue - cost_of_sales)

    promo = decisions["promotion"]
    advertising = r2(sum(promo["advertising"]) * 1000)
    trade_press = r2(sum(promo["trade_press"]) * 1000)
    support = r2(sum(promo["support"]) * 1000)
    merchandising = r2(sum(promo["merchandising"]) * 1000)
    sales_force = r2(n_salespeople * (decisions["sales_remuneration"]["quarterly_salary_000"] * 1000
                                      + SALES_EXPENSE_PER_Q)
                     + decisions["sales_remuneration"]["commission_pct"] / 100.0 * sales_revenue)
    research = r2(decisions["research_expenditure_000"] * 1000)
    management = r2(decisions["management_budget_000"] * 1000)
    maintenance = r2(decisions["contract_maintenance_hours"] * MAINT_RATE_PER_HR)
    supervision = r2(SUPERVISION_PER_SHIFT * decisions["shift_level"])
    production_overheads = r2(PROD_OVERHEAD_PER_MACHINE * 8)
    info_charges = r2((INFO_CHARGE if decisions["info_wanted"]["other_companies"] else 0.0)
                      + (INFO_CHARGE if decisions["info_wanted"]["market_shares"] else 0.0))
    credit_control = r2(CREDIT_CONTROL_PER_UNIT * total_units_sold)
    guarantee_servicing = r2(sum(
        sum(r["sales"] for r in rows if r["product"] == prod) * GUARANTEE_PER_UNIT[prod]
        for prod in PRODUCTS))
    warehousing = r2(WAREHOUSE_FIXED + WAREHOUSE_PER_ORDER * decisions["raw_material"]["num_deliveries"])
    total_overheads = r2(advertising + trade_press + support + merchandising + sales_force
                         + research + management + maintenance + supervision
                         + production_overheads + info_charges + credit_control
                         + guarantee_servicing + warehousing)

    operating_profit = r2(gross_profit - total_overheads)

    bank_rate = float(macro["central_bank_rate"])
    interest_received = r2(state["cash"] * max(bank_rate - 2.0, 0.0) / 100.0 / 4.0)
    interest_paid = 0.0  # demo: no overdraft / unsecured loans drawn
    depreciation = r2(state["machines_net"] * MACHINE_DEPR_Q
                      + state["vehicles_net"] * VEHICLE_DEPR_Q)

    profit_before_tax = r2(operating_profit + interest_received - interest_paid - depreciation)
    tax_assessed = r2(TAX_RATE * profit_before_tax) if profit_before_tax > 0 else 0.0
    net_profit = r2(profit_before_tax - tax_assessed)
    dividend_paid = r2(decisions["dividend_rate_pence"] / 100.0 * SHARES_OUTSTANDING)
    retained_profit = r2(net_profit - dividend_paid)

    # ---- 4. balance sheet -------------------------------------------------
    machines_end = r2(state["machines_net"] * (1 - MACHINE_DEPR_Q))
    vehicles_end = r2(state["vehicles_net"] * (1 - VEHICLE_DEPR_Q))
    fixed_assets = r2(state["property"] + machines_end + vehicles_end)

    product_stocks = closing_stock_value
    mat_closing_units = state["material_units"] + units_to_order - mat_used
    material_stocks = r2(mat_closing_units * mat_price / 1000.0)
    debtors = r2(sales_revenue * decisions["days_credit_allowed"] / 90.0)

    tax_paid = state["tax_assessed_prev"]  # last quarter's bill paid this quarter
    tax_due = r2(state["tax_due"] + tax_assessed - tax_paid)

    order_cost = r2(units_to_order * mat_price / 1000.0 + SUPPLIER1_FIXED_FEE)
    promo_total = r2(advertising + trade_press + support + merchandising)
    creditors = r2((order_cost + promo_total + research + management
                    + maintenance + warehousing) * 0.35 + state["creditors"] * 0.2)

    bank_overdraft = 0.0
    unsecured_loans = 0.0
    current_liabilities = r2(tax_due + creditors + bank_overdraft + unsecured_loans)

    reserves_end = r2(state["reserves"] + retained_profit)
    net_worth = r2(state["share_capital"] + reserves_end)

    non_cash_assets = r2(fixed_assets + product_stocks + material_stocks + debtors)
    cash_end = r2(net_worth + current_liabilities - non_cash_assets)  # balancing plug
    total_assets = r2(non_cash_assets + cash_end)
    net_assets = r2(total_assets - current_liabilities)

    # T19 overdraft limit (negative -> 0)
    overdraft_limit = r2(max(0.0,
                             cash_end
                             + 0.5 * (product_stocks + machines_end + material_stocks + debtors)
                             + 0.25 * state["property"]
                             - (tax_due + creditors)))

    # ---- 5. cash flow (trading_payments is the plug so net cash = Δcash) --
    trading_receipts = r2(sales_revenue - (debtors - state["debtors"]))
    capital_receipts, capital_payments = 0.0, 0.0
    net_investing = r2(capital_receipts - capital_payments)
    dividends_paid = dividend_paid
    net_financing = r2(-interest_paid - dividends_paid)
    delta_cash = r2(cash_end - state["cash"])
    net_operating_target = delta_cash - interest_received - net_investing - net_financing
    trading_payments = r2(trading_receipts - tax_paid - net_operating_target)
    net_operating = r2(trading_receipts - trading_payments - tax_paid)
    net_cash_flow = r2(net_operating + interest_received + net_investing + net_financing)

    # ---- 6. resources -----------------------------------------------------
    resources = {
        "machines": {
            "owned": 8, "new_installed": 0, "sold": 0,
            "hours_available": r2(8 * MACHINE_HOURS_Q),
            "hours_used": round(machinist_hours, 1),
            "utilisation_pct": round(machinist_hours / (8 * MACHINE_HOURS_Q) * 100.0, 1),
            "machinists": 32,
        },
        "assembly": {
            "workers": 48,
            "hours_available": r2(48 * WORKER_HOURS_Q),
            "hours_used": round(assembly_hours, 1),
            "utilisation_pct": round(assembly_hours / (48 * WORKER_HOURS_Q) * 100.0, 1),
            "wage_rate": r2(wage_rate),
        },
        "vehicles": {"owned": 6, "bought": 0, "sold": 0},
        "materials": {
            "opening_stock": int(state["material_units"]),
            "ordered": int(units_to_order),
            "delivered": int(units_to_order),
            "used": int(mat_used),
            "closing_stock": int(mat_closing_units),
            "price_per_1000": r2(mat_price),
        },
    }

    # ---- 7. report sections -----------------------------------------------
    products = [{
        "product": r["product"], "area": r["area"],
        "scheduled": r["scheduled"], "produced": r["produced"],
        "rejected": r["rejected"], "demand": r["demand"], "sales": r["sales"],
        "backlog": r["backlog"], "closing_stock": r["closing"],
        "price": r2(r["price"]), "improvement": bool(decisions["product_improvements"][r["product"] - 1]),
    } for r in rows]

    overheads = {
        "advertising": advertising, "trade_press": trade_press,
        "support": support, "merchandising": merchandising,
        "sales_force": sales_force, "research": research,
        "management": management, "maintenance": maintenance,
        "supervision": supervision, "production_overheads": production_overheads,
        "info_charges": info_charges, "credit_control": credit_control,
        "guarantee_servicing": guarantee_servicing, "warehousing": warehousing,
        "total": total_overheads,
    }

    pnl = {
        "sales_revenue": sales_revenue,
        "opening_stock_value": opening_stock_value,
        "materials": materials_cost,
        "assembly_wages": assembly_wages,
        "machinists_wages": machinists_wages,
        "machine_running": machine_running,
        "closing_stock_value": closing_stock_value,
        "cost_of_sales": cost_of_sales,
        "gross_profit": gross_profit,
        "total_overheads": total_overheads,
        "operating_profit": operating_profit,
        "interest_received": interest_received,
        "interest_paid": interest_paid,
        "depreciation": depreciation,
        "profit_before_tax": profit_before_tax,
        "tax_assessed": tax_assessed,
        "net_profit": net_profit,
        "dividend_paid": dividend_paid,
        "retained_profit": retained_profit,
    }

    balance_sheet = {
        "property": r2(state["property"]),
        "machines": machines_end,
        "vehicles": vehicles_end,
        "fixed_assets": fixed_assets,
        "product_stocks": product_stocks,
        "material_stocks": material_stocks,
        "debtors": debtors,
        "cash_invested": cash_end,
        "total_assets": total_assets,
        "tax_due": tax_due,
        "creditors": creditors,
        "bank_overdraft": bank_overdraft,
        "unsecured_loans": unsecured_loans,
        "current_liabilities": current_liabilities,
        "net_assets": net_assets,
        "share_capital": r2(state["share_capital"]),
        "reserves": reserves_end,
        "net_worth": net_worth,
        "overdraft_limit": overdraft_limit,
    }

    cash_flow = {
        "trading_receipts": trading_receipts,
        "trading_payments": trading_payments,
        "tax_paid": r2(tax_paid),
        "net_operating": net_operating,
        "interest_received": interest_received,
        "capital_receipts": capital_receipts,
        "capital_payments": capital_payments,
        "net_investing": net_investing,
        "interest_paid": interest_paid,
        "dividends_paid": dividends_paid,
        "net_financing": net_financing,
        "net_cash_flow": net_cash_flow,
    }

    economic = {
        "gdp_growth_pct": float(macro["gdp_growth_pct"]),
        "unemployment_pct": float(macro["unemployment_pct"]),
        "central_bank_rate": float(macro["central_bank_rate"]),
        "inflation_pct": float(macro["inflation_pct"]),
        "recession": bool(macro["recession"]),
        "material_price_next_q": r2(MATERIAL_PRICE_NEXT[(year, quarter)]),
    }

    meta = {
        "industry_id": meta_extra["industry_id"],
        "simulation_code": meta_extra["simulation_code"],
        "group_number": meta_extra["group_number"],
        "company_number": cn,
        "company_name": company_name,
        "year": year,
        "quarter": quarter,
        "published_at": meta_extra["published_at"],
        "auto_pass": False,
        "demo_data": True,
    }

    report_core = {
        "meta": meta,
        "decisions": decisions,
        "resources": resources,
        "products": products,
        "overheads": overheads,
        "pnl": pnl,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
        "economic": economic,
        # "group" attached later (needs every team's results for the quarter)
    }

    # ---- 8. share price update (SPEC section 8 rule) ----------------------
    net_worth_prev = state["share_capital"] + state["reserves"]
    if net_worth_prev > 0:
        new_price = state["share_price"] * (1 + 0.6 * net_profit / net_worth_prev)
    else:
        new_price = state["share_price"]
    new_price = min(max(new_price, 0.10), 50.0)
    share_price = r2(new_price)

    end_state = {
        "machines_net": machines_end,
        "vehicles_net": vehicles_end,
        "property": state["property"],
        "share_capital": state["share_capital"],
        "reserves": reserves_end,
        "cash": cash_end,
        "tax_due": tax_due,
        "creditors": creditors,
        "debtors": debtors,
        "material_units": int(mat_closing_units),
        "share_price": share_price,
        "tax_assessed_prev": tax_assessed,
        "product_opening": {(r["product"], r["area"]): r["closing"] for r in rows},
    }

    summary = {
        "company_number": cn, "company_name": company_name,
        "net_profit": net_profit, "net_worth": net_worth,
        "share_price": share_price,
        "div_pence": decisions["dividend_rate_pence"],
        "sales_revenue": sales_revenue,
        "cash_end": cash_end, "cash_start": r2(state["cash"]),
        "trading_payments": trading_payments,
    }
    return decisions, report_core, end_state, summary


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------

def check_report(report):
    """Return a list of (name, passed, detail) for one report."""
    results = []

    def add(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    # -- structural: all SPEC section 6 top-level keys -----------------------
    top = set(report.keys())
    add("top-level keys == SPEC section 6 set",
        top == set(REQUIRED_TOP_KEYS),
        "missing=%s extra=%s" % (sorted(set(REQUIRED_TOP_KEYS) - top),
                                 sorted(top - set(REQUIRED_TOP_KEYS))))
    add("meta has all required sub-keys",
        all(k in report.get("meta", {}) for k in REQUIRED_META_KEYS))
    dec = report.get("decisions", {})
    add("decisions echo has all 22 SPEC section 2 fields",
        set(dec.keys()) == set(DECISION_KEYS),
        "missing=%s extra=%s" % (sorted(set(DECISION_KEYS) - set(dec.keys())),
                                 sorted(set(dec.keys()) - set(DECISION_KEYS))))
    prods = report.get("products", [])
    add("products has 12 rows (3 products x 4 areas)", len(prods) == 12,
        "got %d" % len(prods))
    add("meta.demo_data is true", report.get("meta", {}).get("demo_data") is True)
    add("meta.auto_pass is false", report.get("meta", {}).get("auto_pass") is False)

    pnl = report.get("pnl", {})
    bs = report.get("balance_sheet", {})
    cf = report.get("cash_flow", {})

    # -- (a) revenue = sum over 12 product rows of sales x price ------------
    rev_rows = r2(sum(r["sales"] * r["price"] for r in prods))
    add("(a) pnl.sales_revenue == sum(sales x price) over 12 rows",
        abs(pnl.get("sales_revenue", 0) - rev_rows) <= TOL + EPS,
        "pnl=%s rows=%s" % (pnl.get("sales_revenue"), rev_rows))

    # -- (b) net profit identity -------------------------------------------
    pbt, tax = pnl.get("profit_before_tax", 0), pnl.get("tax_assessed", 0)
    add("(b) pnl.net_profit == profit_before_tax - tax_assessed",
        abs(pnl.get("net_profit", 0) - r2(pbt - tax)) <= TOL + EPS,
        "net=%s pbt-tax=%s" % (pnl.get("net_profit"), r2(pbt - tax)))

    # -- (c) balance sheet identity ----------------------------------------
    add("(c) balance_sheet.net_assets == total_assets - current_liabilities",
        abs(bs.get("net_assets", 0)
            - r2(bs.get("total_assets", 0) - bs.get("current_liabilities", 0))) <= TOL + EPS,
        "net_assets=%s" % bs.get("net_assets"))

    # -- (d) net worth identity --------------------------------------------
    add("(d) balance_sheet.net_worth == share_capital + reserves",
        abs(bs.get("net_worth", 0)
            - r2(bs.get("share_capital", 0) + bs.get("reserves", 0))) <= TOL + EPS,
        "net_worth=%s" % bs.get("net_worth"))

    # -- (e) balance sheet balances ----------------------------------------
    add("(e) net_assets == net_worth",
        abs(bs.get("net_assets", 0) - bs.get("net_worth", 0)) <= TOL + EPS,
        "net_assets=%s net_worth=%s" % (bs.get("net_assets"), bs.get("net_worth")))

    # -- bonus: cash flow ties to the balance sheet cash movement -----------
    cash_start = cf.get("_cash_start")
    add("(bonus) cash_flow.net_cash_flow == Δcash_invested",
        cash_start is not None
        and abs(cf.get("net_cash_flow", 0) - r2(bs.get("cash_invested", 0) - cash_start)) <= 0.02 + EPS,
        "net_cash_flow=%s Δcash=%s" % (cf.get("net_cash_flow"),
                                      r2(bs.get("cash_invested", 0) - (cash_start or 0))))
    add("(bonus) trading_payments positive",
        cf.get("trading_payments", -1) > 0,
        "trading_payments=%s" % cf.get("trading_payments"))

    return results


def check_opening_balance():
    """The SPEC section 9 opening books must balance exactly."""
    s = INIT_STATE
    assets = (s["property"] + s["machines_net"] + s["vehicles_net"]
              + 4 * (60 * 80.0 + 60 * 120.0 + 60 * 200.0)   # 60 units/product/area
              + s["material_units"] * 500.0 / 1000.0
              + s["debtors"] + s["cash"])
    liab = s["tax_due"] + s["creditors"]
    worth = s["share_capital"] + s["reserves"]
    ok = abs(r2(assets - liab) - worth) <= TOL + EPS
    return ok, "assets-liab=%s net_worth=%s" % (r2(assets - liab), worth)


# ---------------------------------------------------------------------------
# Metadata: from the database, or built-in demo values for --dry-run
# ---------------------------------------------------------------------------

DRY_RUN_META = {
    "industry_id": 1,
    "simulation_code": "TOPAZ-DEMO",
    "group_number": 1,
    "teams": [
        {"id": 1, "company_number": 1, "name": "Alpha Manufacturing"},
        {"id": 2, "company_number": 2, "name": "Beta Industries"},
        {"id": 3, "company_number": 3, "name": "Gamma Traders"},
        {"id": 4, "company_number": 4, "name": "Delta Works"},
    ],
    "quarters": {
        (1, 1): "2026-09-20T12:00:00+00:00",
        (1, 2): "2026-09-20T12:00:00+00:00",
    },
    "macro": {
        (1, 1): {"central_bank_rate": 8.0, "gdp_growth_pct": 2.5,
                 "unemployment_pct": 5.0, "inflation_pct": 1.5, "recession": False},
        (1, 2): {"central_bank_rate": 8.0, "gdp_growth_pct": 2.5,
                 "unemployment_pct": 5.0, "inflation_pct": 1.5, "recession": False},
    },
}


def load_db_metadata(conn):
    """Read industry / teams / quarters / macro from the database."""
    meta = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, simulation_code FROM industries WHERE simulation_code = 'TOPAZ-DEMO'")
        row = cur.fetchone()
        if row is None:
            sys.exit("ERROR: industry 'TOPAZ-DEMO' not found. "
                     "Apply db/migrations/001_init.sql and 002_seed.sql first.")
        meta["industry_id"], meta["simulation_code"] = row[0], row[1]
        meta["group_number"] = 1

        cur.execute(
            "SELECT id, company_number, name FROM teams "
            "WHERE industry_id = %s AND group_number = 1 AND active ORDER BY company_number",
            (meta["industry_id"],))
        teams = [{"id": r[0], "company_number": r[1], "name": r[2]} for r in cur.fetchall()]
        if len(teams) != 4 or [t["company_number"] for t in teams] != [1, 2, 3, 4]:
            sys.exit("ERROR: expected 4 active demo teams (companies 1..4, group 1); "
                     "found %d. Apply db/migrations/002_seed.sql first." % len(teams))
        meta["teams"] = teams

        cur.execute(
            "SELECT year, quarter, status, published_at FROM quarters "
            "WHERE industry_id = %s AND (year, quarter) IN ((1, 1), (1, 2))",
            (meta["industry_id"],))
        quarters = {}
        for year, quarter, status, published_at in cur.fetchall():
            if status != "published":
                sys.exit("ERROR: quarter Y%dQ%d is '%s', not 'published'." % (year, quarter, status))
            quarters[(year, quarter)] = published_at.isoformat() if published_at else None
        if set(quarters) != {(1, 1), (1, 2)}:
            sys.exit("ERROR: quarters (1,1) and (1,2) not found. "
                     "Apply db/migrations/002_seed.sql first.")
        meta["quarters"] = quarters

        cur.execute(
            "SELECT year, quarter, central_bank_rate, gdp_growth_pct, "
            "       unemployment_pct, inflation_pct, recession "
            "FROM macro WHERE industry_id = %s AND (year, quarter) IN ((1, 1), (1, 2))",
            (meta["industry_id"],))
        macro = {(r[0], r[1]): {"central_bank_rate": float(r[2]),
                                "gdp_growth_pct": float(r[3]),
                                "unemployment_pct": float(r[4]),
                                "inflation_pct": float(r[5]),
                                "recession": bool(r[6])}
                 for r in cur.fetchall()}
        if set(macro) != {(1, 1), (1, 2)}:
            sys.exit("ERROR: macro rows for (1,1) and (1,2) not found. "
                     "Apply db/migrations/002_seed.sql first.")
        meta["macro"] = macro
    return meta


def insert_all(conn, payload):
    """Insert decisions + reports (idempotent: upsert on the unique keys)."""
    from psycopg.types.json import Json

    with conn.cursor() as cur:
        for item in payload:
            cur.execute(
                """INSERT INTO decisions
                       (industry_id, team_id, year, quarter, data,
                        submitted, submitted_at, auto_pass, updated_at)
                   VALUES (%s, %s, %s, %s, %s, true, now(), false, now())
                   ON CONFLICT (team_id, year, quarter) DO UPDATE SET
                       data = EXCLUDED.data,
                       submitted = true,
                       submitted_at = now(),
                       auto_pass = false,
                       updated_at = now()""",
                (item["industry_id"], item["team_id"], item["year"],
                 item["quarter"], Json(item["decisions"])))
            cur.execute(
                """INSERT INTO reports (industry_id, team_id, year, quarter, report)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (team_id, year, quarter) DO UPDATE SET
                       report = EXCLUDED.report""",
                (item["industry_id"], item["team_id"], item["year"],
                 item["quarter"], Json(item["report"])))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_all(meta):
    """Simulate every team x quarter; attach the industry-wide group section."""
    per_quarter = {(1, 1): [], (1, 2): []}   # (year, quarter) -> [(team, decisions, core, summary)]
    states = {}
    for team in meta["teams"]:
        cn = team["company_number"]
        state = dict(INIT_STATE)
        state["product_opening"] = {(prod, area): 60 for prod in PRODUCTS for area in AREAS}
        for year, quarter in [(1, 1), (1, 2)]:
            macro = meta["macro"][(year, quarter)]
            meta_extra = {
                "industry_id": meta["industry_id"],
                "simulation_code": meta["simulation_code"],
                "group_number": meta["group_number"],
                "published_at": meta["quarters"][(year, quarter)],
            }
            decisions, core, state, summary = simulate_quarter(
                cn, team["name"], year, quarter, state, macro, meta_extra)
            per_quarter[(year, quarter)].append((team, decisions, core, summary))
        states[cn] = state

    # Attach the group section: the SAME 4 companies in every team's report,
    # with that quarter's share prices / net profits / net worths.
    payload = []
    for (year, quarter), items in per_quarter.items():
        companies = [{
            "company_number": s["company_number"],
            "company_name": s["company_name"],
            "share_price": s["share_price"],
            "dividend_pct": r2(s["div_pence"] / s["share_price"]),
            "net_profit": s["net_profit"],
            "net_worth": s["net_worth"],
        } for (_, _, _, s) in items]

        market_shares = {}
        for area in AREAS:
            market_shares[area] = {}
            for prod in PRODUCTS:
                cell_sales = [next(r["sales"] for r in core["products"]
                                   if r["area"] == area and r["product"] == prod)
                              for (_, _, core, _) in items]
                total = sum(cell_sales)
                shares = [round(s / total, 4) for s in cell_sales] if total else [0.0] * 4
                if shares:  # fix rounding so the four shares sum to exactly 1
                    shares[-1] = round(1.0 - sum(shares[:-1]), 4)
                market_shares[area][str(prod)] = shares

        for (team, decisions, core, summary) in items:
            core["group"] = {"companies": companies, "market_shares": market_shares}
            # stash cash_start for the bonus cash-flow check (not part of SPEC)
            core["cash_flow"]["_cash_start"] = summary["cash_start"]
            payload.append({
                "industry_id": meta["industry_id"],
                "team_id": team["id"],
                "team_name": team["name"],
                "company_number": team["company_number"],
                "year": year, "quarter": quarter,
                "decisions": decisions,
                "report": core,
                "summary": summary,
            })
    return payload


def main():
    ap = argparse.ArgumentParser(
        description="Seed demo decisions + reports for the Topaz-VBE demo industry.")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and validate everything without touching the database")
    args = ap.parse_args()

    ok, detail = check_opening_balance()
    print("[opening balance sheet] %s (%s)" % ("PASS" if ok else "FAIL", detail))
    if not ok:
        return 1

    if args.dry_run:
        meta = DRY_RUN_META
        conn = None
    else:
        try:
            import psycopg
        except ImportError:
            sys.exit("ERROR: psycopg is not installed. Run: pip install 'psycopg[binary]'")
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            sys.exit("ERROR: DATABASE_URL environment variable is not set.")
        conn = psycopg.connect(db_url)
        meta = load_db_metadata(conn)

    payload = build_all(meta)

    all_ok = True
    for item in payload:
        label = "Y%dQ%d team %d (%s)" % (item["year"], item["quarter"],
                                        item["company_number"], item["team_name"])
        results = check_report(item["report"])
        failed = [name for name, passed, _ in results if not passed]
        # drop the internal helper key (used only by the bonus cash check)
        item["report"]["cash_flow"].pop("_cash_start", None)
        if failed:
            all_ok = False
            print("[FAIL] %s" % label)
            for name, passed, detail in results:
                if not passed:
                    print("       - %s :: %s" % (name, detail))
        else:
            print("[PASS] %s (%d/%d checks)" % (label, len(results), len(results)))

    s = payload[0]["summary"]
    print("\nSample economics (team 1, Y1Q1): revenue £%s | net profit £%s | "
          "share price £%s | cash £%s" % (
              f"{s['sales_revenue']:,.2f}", f"{s['net_profit']:,.2f}",
              f"{s['share_price']:,.2f}", f"{s['cash_end']:,.2f}"))

    if not all_ok:
        print("\nSome checks FAILED — nothing was written to the database.")
        return 1

    if args.dry_run:
        print("\nDry run: all %d reports valid, nothing written." % len(payload))
        return 0

    insert_all(conn, payload)
    conn.commit()
    conn.close()
    print("\nInserted %d decisions rows and %d reports rows "
          "(4 teams x 2 quarters)." % (len(payload), len(payload)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
