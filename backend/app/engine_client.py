"""Bridge between the FastAPI backend and the simulation engine package.

Engine layout (built by the engine builder):
    ~/workspace/topaz-vbe/engine/          -> package ``topaz_engine``
    topaz_engine.validation.validate(data, funds) -> errors (or (errors, warnings))
    topaz_engine.constants.{TABLES, DEFAULT_DECISIONS, ...}
    python -m topaz_engine.cli --industry I --year Y --quarter Q

The engine directory is resolved, in order, from:
    1. ENGINE_DIR environment variable
    2. /app/engine (Docker layout)
    3. ~/workspace/topaz-vbe/engine (dev layout)

Static constants that the SPEC pins (TABLES from section 5, DEFAULT_DECISIONS
from section 2) are also embedded here as fallbacks so the /api/tables and
decision-reset endpoints keep working even if the engine package is absent.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("topaz.engine")

ENGINE_DIR = (
    os.environ.get("ENGINE_DIR")
    or ("/app/engine" if Path("/app/engine").is_dir() else None)
    or str(Path.home() / "workspace" / "topaz-vbe" / "engine")
)

_path_added = False


def engine_dir() -> str:
    return ENGINE_DIR


def _ensure_path() -> None:
    global _path_added
    if not _path_added:
        if ENGINE_DIR not in sys.path:
            sys.path.insert(0, ENGINE_DIR)
        _path_added = True


class EngineError(RuntimeError):
    """Raised when the engine cannot be used (missing package or CLI failure).

    Subclasses RuntimeError so the app can boot and serve every non-roll
    endpoint even when the engine package has not been built yet.
    """


_modules: dict[str, object] = {}


def _module(name: str):
    """Lazily import ``topaz_engine.<name>`` (function-level import).

    Never runs at module import time, so the FastAPI app boots and serves
    every non-roll endpoint while the engine package is still being built.
    Raises EngineError (a RuntimeError) with a clear message when the engine
    package -- or the required submodule -- cannot be found at ENGINE_DIR.
    """
    if name in _modules:
        return _modules[name]
    _ensure_path()
    try:
        # A bare/empty engine directory imports as an empty namespace package,
        # so require the actual submodule: this raises ImportError (a subclass
        # of which is ModuleNotFoundError) when the engine is not really there.
        mod = __import__(f"topaz_engine.{name}", fromlist=[name])
    except ImportError as exc:
        raise EngineError(
            f"simulation engine not found at {ENGINE_DIR} "
            "(set ENGINE_DIR or build the topaz_engine package there)."
        ) from exc
    _modules[name] = mod
    return mod


def validate(data: dict, funds: float) -> list[str]:
    """Validate decision data against available funds.

    Returns the list of error strings (SPEC section 7 wording).
    """
    errors, _warnings = validate_with_warnings(data, funds)
    return errors


def validate_with_warnings(data: dict, funds: float) -> tuple[list[str], list[str]]:
    """Return (errors, warnings); tolerates several engine return shapes."""
    mod = _module("validation")
    try:
        result = mod.validate(data, funds)
    except AttributeError as exc:
        raise EngineError("topaz_engine.validation.validate() is not defined.") from exc

    if isinstance(result, dict):
        return list(result.get("errors", [])), list(result.get("warnings", []))
    if isinstance(result, (tuple, list)) and len(result) == 2 and all(
        isinstance(x, (list, tuple)) for x in result
    ):
        return list(result[0]), list(result[1])
    return list(result), []


def get_constants():
    """Return the engine ``constants`` module (raises EngineError if missing)."""
    return _module("constants")


# ---------------------------------------------------------------------------
# SPEC-pinned static fallbacks (sections 2 and 5 of SPEC.md)
# ---------------------------------------------------------------------------

DEFAULT_DECISIONS_FALLBACK: dict = {
    "product_improvements": [False, False, False],
    "prices": {"export": [120.0, 180.0, 260.0], "home": [110.0, 165.0, 240.0]},
    "promotion": {
        "trade_press": [8.0, 6.0, 4.0],
        "advertising": [20.0, 15.0, 10.0],
        "support": [5.0, 4.0, 3.0],
        "merchandising": [6.0, 5.0, 4.0],
    },
    "assembly_time_minutes": [110, 160, 320],
    "salespeople": {"export": 2, "south": 4, "west": 3, "north": 5},
    "sales_remuneration": {"quarterly_salary_000": 3.0, "commission_pct": 5.0},
    "assembly_wage": {"pounds": 9, "pence": 50},
    "shift_level": 1,
    "management_budget_000": 45.0,
    "contract_maintenance_hours": 40,
    "machines_to_sell": 0,
    "dividend_rate_pence": 4.0,
    "days_credit_allowed": 30,
    "vans_to_buy": 0,
    "vans_to_sell": 0,
    "info_wanted": {"other_companies": False, "market_shares": False},
    "make_deliver": {
        "export": [800, 500, 300],
        "south": [600, 400, 200],
        "west": [400, 300, 150],
        "north": [900, 600, 350],
    },
    "research_expenditure_000": 12.0,
    "salespeople_changes": {"recruit": 0, "dismiss": 0, "train": 2},
    "assembly_changes": {"recruit": 2, "dismiss": 0, "train": 4},
    "raw_material": {"units_to_order": 4000, "supplier_no": 1, "num_deliveries": 2},
    "new_machines_to_order": 0,
}

TABLES_FALLBACK: dict = {
    "areas": ["south", "west", "north", "export"],
    "products": [1, 2, 3],
    "T3_manufacturing": {
        "1": {"machine_minutes": 60, "assembly_minutes": 100, "material_units": 1},
        "2": {"machine_minutes": 75, "assembly_minutes": 150, "material_units": 2},
        "3": {"machine_minutes": 120, "assembly_minutes": 300, "material_units": 3},
    },
    "T5_machine_hours_per_quarter": {
        "1": {"label": "Single", "hours": 576, "machinists_per_machine": 4},
        "2": {"label": "Double", "hours": 1068, "machinists_per_machine": 8},
        "3": {"label": "Treble", "hours": 1602, "machinists_per_machine": 12},
    },
    "T4_maintenance_gbp_per_hr": {"contracted": 60, "uncontracted": 120},
    "T8_overheads": {
        "supervision_per_shift_gbp": 10000,
        "production_overheads_per_machine_gbp": 2000,
        "machine_running_gbp_per_hr": 7,
        "planning_gbp_per_unit": 1,
    },
    "T6_scrap_gbp_per_unit": {"1": 20, "2": 40, "3": 60},
    "T7_guarantee_servicing_gbp_per_unit": {"1": 60, "2": 120, "3": 200},
    "T9_vehicle_capacity_units": {"1": 40, "2": 40, "3": 20},
    "T10_journey_days": {"south": 1, "west": 2, "north": 4, "export": 6},
    "T11_vehicles_gbp": {
        "driver_wages_per_vehicle_per_q": 7000,
        "own_running_per_day": 50,
        "hire_per_day": 200,
    },
    "T12_storage_gbp": {
        "factory_capacity_units": 2000,
        "warehouse_fixed_per_q": 3750,
        "admin_per_q": 3250,
        "per_order": 750,
        "external_per_unit": 1.50,
        "market_area_product_per_unit": 2,
    },
    "T14_suppliers": {
        "0": {"discount_pct": 0, "admin_charge_gbp": 0, "min_order": 1, "max_order": 1},
        "1": {"discount_pct": 10, "admin_charge_gbp": 200, "min_order": 1, "max_order": 1},
        "2": {"discount_pct": 15, "admin_charge_gbp": 300, "min_order": 1000, "max_order": 10000},
        "3": {
            "discount_pct": 30,
            "admin_charge_gbp": 100,
            "min_order": None,
            "max_order": 50000,
            "note": "12 automatic weekly deliveries; num_deliveries must be 0",
        },
    },
    "T15_personnel_costs_gbp": {
        "salesperson": {"recruit": 1500, "dismiss": 5000, "train": 6000},
        "assembly": {"recruit": 1200, "dismiss": 3000, "train": 4500},
        "machinist": {"recruit": 750, "dismiss": 1500, "train": None},
    },
    "T16_worker_hours_per_q": {
        "basic": 420,
        "saturday_overtime": {"1": 84, "2": 42, "3": 42},
        "sunday_overtime": 72,
        "shift_premium": {"1": 0, "2": "1/3", "3": "2/3"},
    },
    "T17_minima": {
        "machinist_min_paid_hours_per_q": 400,
        "assembly_min_wage_gbp_per_hr": 8.50,
        "unskilled_to_skilled_pct": 65,
        "min_sales_salary_gbp_per_q": 2000,
        "min_management_budget_gbp_per_q": 40000,
    },
    "T18_capital_gbp": {
        "machine": {"cost": 200000, "at_order": 100000, "on_installation": 100000,
                    "depreciation_pct_per_q": 2.5},
        "vehicle": {"cost": 15000, "depreciation_pct_per_q": 6.25},
    },
    "T19_overdraft_limit": {
        "formula": "100% x cash_invested + 50% x (product_stocks + machines + material_stocks + debtors) + 25% x property - 100% x (tax_due + creditors); negative -> 0",
    },
    "T20_tax_interest": {
        "tax_pct_per_yr": 30,
        "fixed_overheads_gbp_per_q": 10000,
        "variable_overhead_pct": 0.25,
        "credit_control_gbp_per_unit_sold": 1.50,
        "interest_vs_bank_rate": {"investments": -2, "overdraft": 4, "unsecured": 10},
    },
    "T21_stock_valuation_gbp_per_unit": {"product": {"1": 80, "2": 120, "3": 200},
                                        "materials": "50% of last quarter's material price"},
    "T22_creditor_timing": {
        "paid_quarter_after_next": ["advertising", "guarantee", "hired_transport",
                                    "maintenance", "external_stock", "business_intel"],
        "paid_next_quarter": ["product_development", "personnel", "warehousing",
                              "misc", "materials_purchased_100pct", "machines_50pct"],
    },
    "T23_credit_discount_pct": {"up_to_7_days": 10, "8_to_15_days": 7.5,
                                "16_to_29_days": 5, "30_plus_days": 0},
    "T1_households_millions_and_penetration": {
        "south": {"households_m": 7, "penetration": [1, 2, 4]},
        "west": {"households_m": 4, "penetration": [1, 1, 2]},
        "north": {"households_m": 13, "penetration": [1, 3, 9]},
        "export": {"households_m": 80, "penetration": [10, 15, 55]},
        "outlets": {"south": 3000, "west": 2000, "north": 4000, "export": 20000},
    },
    "T2_info_charges_gbp_per_q": {
        "salesperson_expenses": 3000,
        "competitor_info": 5000,
        "market_share_info": 5000,
    },
}


def get_default_decisions() -> dict:
    """Return a deep copy of constants.DEFAULT_DECISIONS (SPEC section 2)."""
    try:
        const = get_constants()
        return copy.deepcopy(const.DEFAULT_DECISIONS)
    except EngineError:
        log.warning("Engine constants unavailable; using SPEC-embedded defaults.")
        return copy.deepcopy(DEFAULT_DECISIONS_FALLBACK)


def get_tables() -> dict:
    """Return constants.TABLES (SPEC section 5), with a SPEC-embedded fallback."""
    try:
        const = get_constants()
        return copy.deepcopy(const.TABLES)
    except EngineError:
        log.warning("Engine constants unavailable; using SPEC-embedded TABLES.")
        return copy.deepcopy(TABLES_FALLBACK)


# ---------------------------------------------------------------------------
# Funds / affordability helpers (SPEC section 7, rule 7)
# ---------------------------------------------------------------------------

INITIAL_STATE = {
    "machines": 8,
    "machine_unit_cost_gbp": 200000,
    "vehicles": 6,
    "cash_invested_gbp": 400000,
    "bank_overdraft_gbp": 0,
    "unsecured_loans_gbp": 0,
    "property_gbp": 250000,
    "material_stock_units": 2000,
    "material_price_per_1000_gbp": 500,
    "product_stock_units_per_product_per_area": 60,
    "product_stock_value_gbp_per_unit": {1: 80, 2: 120, 3: 200},
    "debtors_gbp": 0,
    "tax_due_gbp": 0,
    "creditors_gbp": 0,
}


def overdraft_limit_t19(*, cash_invested: float, product_stocks: float,
                        machines_value: float, material_stocks: float,
                        debtors: float, property_value: float,
                        tax_due: float, creditors: float) -> float:
    """Table 19 overdraft limit; negative -> 0."""
    limit = (
        1.0 * cash_invested
        + 0.5 * (product_stocks + machines_value + material_stocks + debtors)
        + 0.25 * property_value
        - 1.0 * (tax_due + creditors)
    )
    return max(0.0, limit)


def initial_available_funds() -> float:
    """Available funds for a brand-new team (SPEC section 9).

    cash_invested + T19 overdraft limit computed on the initial state.
    """
    s = INITIAL_STATE
    product_stocks = (
        s["product_stock_units_per_product_per_area"]
        * 4  # areas
        * sum(s["product_stock_value_gbp_per_unit"].values())
    )
    machines_value = s["machines"] * s["machine_unit_cost_gbp"]
    material_stocks = s["material_stock_units"] * s["material_price_per_1000_gbp"] / 1000.0
    limit = overdraft_limit_t19(
        cash_invested=s["cash_invested_gbp"],
        product_stocks=product_stocks,
        machines_value=machines_value,
        material_stocks=material_stocks,
        debtors=s["debtors_gbp"],
        property_value=s["property_gbp"],
        tax_due=s["tax_due_gbp"],
        creditors=s["creditors_gbp"],
    )
    return s["cash_invested_gbp"] + limit


def get_available_funds(team_id: int) -> float:
    """Available funds for affordability validation (SPEC section 7 rule 7).

    Last published report's balance_sheet.cash_invested + overdraft_limit;
    falls back to the initial-state computation when no report exists yet.
    """
    from .db import get_conn  # local import to avoid circulars

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT r.report
            FROM reports r
            JOIN quarters q ON q.industry_id = r.industry_id
                           AND q.year = r.year AND q.quarter = r.quarter
            WHERE r.team_id = %s AND q.status = 'published'
            ORDER BY r.year DESC, r.quarter DESC
            LIMIT 1
            """,
            (team_id,),
        ).fetchone()
    if row and row["report"]:
        bs = (row["report"] or {}).get("balance_sheet", {})
        try:
            cash = float(bs.get("cash_invested", 0) or 0)
            limit = float(bs.get("overdraft_limit", 0) or 0)
            return cash + max(0.0, limit)
        except (TypeError, ValueError):
            pass
    return initial_available_funds()


# ---------------------------------------------------------------------------
# Engine subprocess runner (quarter batch processing)
# ---------------------------------------------------------------------------

def run_engine_subprocess(industry_id: int, year: int, quarter: int,
                          timeout_s: int = 1800) -> str:
    """Run the engine CLI for one quarter; return its stdout.

    Raises EngineError on nonzero exit or launch failure. DATABASE_URL is
    passed through to the child process so the engine reaches the same DB.
    """
    cmd = [
        sys.executable, "-m", "topaz_engine.cli",
        "--industry", str(industry_id),
        "--year", str(year),
        "--quarter", str(quarter),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = ENGINE_DIR + os.pathsep + env.get("PYTHONPATH", "")
    log.info("Running engine: %s (cwd=%s)", " ".join(cmd), ENGINE_DIR)
    try:
        proc = subprocess.run(
            cmd, cwd=ENGINE_DIR, env=env,
            capture_output=True, text=True, timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        raise EngineError(f"Engine directory not found: {ENGINE_DIR}") from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError(
            f"Engine timed out after {timeout_s}s for industry {industry_id} "
            f"Y{year}Q{quarter}."
        ) from exc

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-4000:]
        raise EngineError(
            f"Engine failed (exit {proc.returncode}) for industry {industry_id} "
            f"Y{year}Q{quarter}: {tail}"
        )
    return proc.stdout or ""


def parse_engine_summary(stdout: str) -> dict | None:
    """Best-effort parse of a JSON summary the engine may print on success."""
    try:
        data = json.loads(stdout.strip())
        if isinstance(data, dict):
            return data
    except (ValueError, AttributeError):
        pass
    return None
