# Quarter simulation — SPEC.md section 8. Pure functions, stdlib only,
# no randomness, no I/O. All teams are processed in one deterministic batch.

import math
from datetime import datetime, timezone

from .constants import AREAS, PRODUCTS, TABLES, DEFAULT_DECISIONS, INITIAL_STATE

PENETRATION = {1: 0.0011, 2: 0.0007, 3: 0.0004}  # documented assumption
EXPORT_DAMPING = 0.15  # documented assumption
SHARES_ISSUED = 1_000_000
MACHINIST_WAGE_PER_HR = 10.50  # assumption: not stated in the manual tables


def overdraft_limit(cash_invested, product_stocks, machines, material_stocks,
                    debtors, property_, tax_due, creditors):
    """T19: 100% cash + 50% (stocks+machines+materials+debtors) + 25% property
    - 100% (tax due + creditors); negative -> 0."""
    return max(0.0,
               cash_invested
               + 0.5 * (product_stocks + machines + material_stocks + debtors)
               + 0.25 * property_
               - (tax_due + creditors))


def _credit_discount(days):
    for max_days, disc in TABLES["T23"]["tiers"]:
        if days <= max_days:
            return disc
    return TABLES["T23"]["default"]


def _num(v, default=0.0):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _r(x):
    return round(float(x), 2)


def _merge(base, override):
    out = {}
    for k, v in base.items():
        out[k] = (dict(v) if isinstance(v, dict)
                  else (list(v) if isinstance(v, list) else v))
    for k, v in (override or {}).items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = dict(out[k])
            merged.update(v)
            out[k] = merged
        else:
            out[k] = v
    return out


def _pad3(v, default):
    v = list(v) if isinstance(v, (list, tuple)) else []
    return [_num(v[i], default[i]) if i < len(v) else default[i]
            for i in range(3)]


def _norm_decisions(d):
    d = _merge(DEFAULT_DECISIONS, d)
    for mkt in ("export", "home"):
        d["prices"][mkt] = _pad3(d["prices"].get(mkt),
                                 DEFAULT_DECISIONS["prices"][mkt])
    for k in ("trade_press", "advertising", "support", "merchandising"):
        d["promotion"][k] = _pad3(d["promotion"].get(k),
                                  DEFAULT_DECISIONS["promotion"][k])
    d["assembly_time_minutes"] = _pad3(
        d.get("assembly_time_minutes"),
        DEFAULT_DECISIONS["assembly_time_minutes"])
    d["product_improvements"] = _pad3(
        d.get("product_improvements"),
        DEFAULT_DECISIONS["product_improvements"])
    for a in AREAS:
        d["make_deliver"][a] = _pad3(d["make_deliver"].get(a),
                                    DEFAULT_DECISIONS["make_deliver"][a])
        d["salespeople"][a] = _num(d["salespeople"].get(a), 0.0)
    d["shift_level"] = int(_num(d.get("shift_level"), 1))
    if d["shift_level"] not in (1, 2, 3):
        d["shift_level"] = 1
    sup = int(_num(d["raw_material"]["supplier_no"], 1))
    d["raw_material"]["supplier_no"] = sup if sup in (0, 1, 2, 3) else 1
    return d


def _openings(prev, cn):
    """Opening balances: previous published report, else INITIAL_STATE."""
    if prev is None:
        p = {(a, pr): INITIAL_STATE["product_stock_per_area_product"]
             for a in AREAS for pr in PRODUCTS}
        t21 = TABLES["T21"]["product_valuation"]
        return {
            "machines_count": INITIAL_STATE["machines"],
            "machines_value": (INITIAL_STATE["machines"]
                               * TABLES["T18"]["machine_cost"]),
            "vehicles_count": INITIAL_STATE["vehicles"],
            "vehicles_value": (INITIAL_STATE["vehicles"]
                               * TABLES["T18"]["vehicle_cost"]),
            "assembly_workers": INITIAL_STATE["assembly_workers"],
            "machinists": INITIAL_STATE["machinists"],
            "property": float(INITIAL_STATE["property"]),
            "material_stock": INITIAL_STATE["material_stock"],
            "material_price": float(
                INITIAL_STATE["material_price_per_1000"]),
            "product_stock": p,
            "product_stock_value": float(
                sum(v * t21[pr] for (a, pr), v in p.items())),
            "debtors": 0.0, "tax_due": 0.0, "creditors": 0.0,
            "cash": float(INITIAL_STATE["cash_invested"]),
            "overdraft": 0.0, "unsecured": 0.0,
            "reserves": float(INITIAL_STATE["reserves"]),
            "share_price": float(INITIAL_STATE["share_price"]),
            "net_worth": float(INITIAL_STATE["share_capital"]
                               + INITIAL_STATE["reserves"]),
            "prev_after_next": 0.0,
        }
    r = prev.get("resources", {})
    bs = prev.get("balance_sheet", {})
    oh = prev.get("overheads", {})
    prod = {(row["area"], row["product"]): row["closing_stock"]
            for row in prev.get("products", [])}
    sp = float(INITIAL_STATE["share_price"])
    for c in prev.get("group", {}).get("companies", []):
        if c.get("company_number") == cn:
            sp = _num(c.get("share_price"), sp)
    after_next = sum(_num(oh.get(k)) for k in
                     ("advertising", "trade_press", "support",
                      "merchandising", "info_charges",
                      "guarantee_servicing", "maintenance",
                      "credit_control"))
    return {
        "machines_count": int(_num(r.get("machines", {}).get("owned"))),
        "machines_value": _num(bs.get("machines")),
        "vehicles_count": int(_num(r.get("vehicles", {}).get("owned"))),
        "vehicles_value": _num(bs.get("vehicles")),
        "assembly_workers": int(_num(r.get("assembly", {}).get("workers"))),
        "machinists": int(_num(r.get("machines", {}).get("machinists"),
                               INITIAL_STATE["machinists"])),
        "property": _num(bs.get("property"), INITIAL_STATE["property"]),
        "material_stock": int(_num(r.get("materials", {}).get("closing_stock"))),
        "material_price": _num(r.get("materials", {}).get("price_per_1000"),
                               INITIAL_STATE["material_price_per_1000"]),
        "product_stock": prod,
        "product_stock_value": _num(bs.get("product_stocks")),
        "debtors": _num(bs.get("debtors")),
        "tax_due": _num(bs.get("tax_due")),
        "creditors": _num(bs.get("creditors")),
        "cash": _num(bs.get("cash_invested")),
        "overdraft": _num(bs.get("bank_overdraft")),
        "unsecured": _num(bs.get("unsecured_loans")),
        "reserves": _num(bs.get("reserves"), INITIAL_STATE["reserves"]),
        "share_price": sp,
        "net_worth": _num(bs.get("net_worth"),
                          INITIAL_STATE["share_capital"]
                          + INITIAL_STATE["reserves"]),
        "prev_after_next": after_next,
    }


def _phase_a(team, d, mv, avg_price, demand):
    """Production + attractiveness (availability-free pass)."""
    cn = team["team"]["company_number"]
    op = _openings(team.get("prev"), cn)
    shift = d["shift_level"]
    t3, t5, t16 = TABLES["T3"], TABLES["T5"], TABLES["T16"]

    sched = {a: {p: max(int(_num(d["make_deliver"][a][p - 1])), 0)
                 for p in PRODUCTS} for a in AREAS}
    total_sched = sum(sched[a][p] for a in AREAS for p in PRODUCTS)

    sold_m = min(max(int(_num(d["machines_to_sell"])), 0),
                 op["machines_count"])
    new_m = max(int(_num(d["new_machines_to_order"])), 0)
    machines = op["machines_count"] - sold_m + new_m
    mach_avail = machines * t5[shift]["machine_hours_per_q"]

    workers = max(op["assembly_workers"]
                  + int(_num(d["assembly_changes"]["recruit"]))
                  - int(_num(d["assembly_changes"]["dismiss"])), 0)
    assy_avail = workers * (t16["basic_hours_per_q"]
                            + t16["saturday_overtime"][shift]
                            + t16["sunday_overtime"])

    ordered = max(int(_num(d["raw_material"]["units_to_order"])), 0)
    delivered = ordered  # deterministic: full delivery in-quarter
    mat_avail = op["material_stock"] + delivered
    mat_price = op["material_price"] * (1 + mv["mat_change"] / 100)

    at = d["assembly_time_minutes"]
    mach_need = sum(sched[a][p] * t3[p]["machining_min"] / 60
                    for a in AREAS for p in PRODUCTS)
    assy_need = sum(sched[a][p] * max(at[p - 1], t3[p]["assembly_min"]) / 60
                    for a in AREAS for p in PRODUCTS)
    mat_need = sum(sched[a][p] * t3[p]["material_content"]
                   for a in AREAS for p in PRODUCTS)
    ratios = [1.0]
    if mach_need > 0:
        ratios.append(mach_avail / mach_need)
    if assy_need > 0:
        ratios.append(assy_avail / assy_need)
    if mat_need > 0:
        ratios.append(mat_avail / mat_need)
    scale = min(ratios)
    produced_total = math.floor(total_sched * scale)
    produced = {a: {p: math.floor(sched[a][p] * scale)
                    for p in PRODUCTS} for a in AREAS}
    rem = produced_total - sum(produced[a][p]
                               for a in AREAS for p in PRODUCTS)
    order = [(a, p) for a in AREAS for p in PRODUCTS]
    guard, i = 0, 0
    while rem > 0 and guard < total_sched + 16:
        a, p = order[i % len(order)]
        i += 1
        guard += 1
        if produced[a][p] < sched[a][p]:
            produced[a][p] += 1
            rem -= 1

    research_pounds = _num(d["research_expenditure_000"]) * 1000
    imp = d["product_improvements"]
    star = {p: max(1.0, min(5.0, 1 + research_pounds / 20000
                            + (1 if imp[p - 1] else 0)))
            for p in PRODUCTS}
    rejected, sellable = {}, {}
    for a in AREAS:
        rejected[a], sellable[a] = {}, {}
        for p in PRODUCTS:
            rate = max(0.005, 0.03 - 0.01 * star[p])
            rejected[a][p] = int(round(produced[a][p] * rate))
            sellable[a][p] = produced[a][p] - rejected[a][p]

    opening = {a: {p: int(_num(op["product_stock"].get((a, p)), 60))
                   for p in PRODUCTS} for a in AREAS}

    promo = d["promotion"]
    keys = ("trade_press", "advertising", "support", "merchandising")
    promo_f = {p: 1 + 0.15 * math.log(
        1 + sum(_num(promo[k][p - 1]) for k in keys)) for p in PRODUCTS}
    outlets = TABLES["T1"]["outlets"]
    sales_f = {a: 1 + 2.0 * (d["salespeople"][a] / (outlets[a] / 500))
               for a in AREAS}
    qual_f = {p: 1 + 0.06 * (star[p] - 1) for p in PRODUCTS}
    own_price = {a: {p: _num(
        d["prices"]["export" if a == "export" else "home"][p - 1])
        for p in PRODUCTS} for a in AREAS}
    a1 = {}
    for a in AREAS:
        mkt = "export" if a == "export" else "home"
        a1[a] = {}
        for p in PRODUCTS:
            pf = ((avg_price[p][mkt] / own_price[a][p]) ** 2.0
                  if own_price[a][p] > 0 else 0.2)
            a1[a][p] = (promo_f[p] * sales_f[a] * qual_f[p]
                        * max(0.2, min(5.0, pf)))

    mach_hrs_used = sum(produced[a][p] * t3[p]["machining_min"] / 60
                        for a in AREAS for p in PRODUCTS)
    assy_hrs_used = sum(produced[a][p]
                        * max(at[p - 1], t3[p]["assembly_min"]) / 60
                        for a in AREAS for p in PRODUCTS)
    mat_used = sum(produced[a][p] * t3[p]["material_content"]
                   for a in AREAS for p in PRODUCTS)

    bought_v = max(int(_num(d["vans_to_buy"])), 0)
    sold_v = min(max(int(_num(d["vans_to_sell"])), 0),
                 op["vehicles_count"])
    vehicles = op["vehicles_count"] - sold_v + bought_v

    return {
        "op": op, "sched": sched, "total_sched": total_sched,
        "produced": produced, "rejected": rejected, "sellable": sellable,
        "opening": opening, "own_price": own_price, "star": star,
        "machines": machines, "sold_m": sold_m, "new_m": new_m,
        "vehicles": vehicles, "bought_v": bought_v, "sold_v": sold_v,
        "workers": workers, "mach_avail": mach_avail,
        "assy_avail": assy_avail, "mach_hrs_used": mach_hrs_used,
        "assy_hrs_used": assy_hrs_used, "mat_used": mat_used,
        "mat_avail": mat_avail, "mat_price": mat_price,
        "ordered": ordered, "delivered": delivered, "a1": a1,
        "share": {a: {p: 0.0 for p in PRODUCTS} for a in AREAS},
        "demand_units": {a: {p: 0 for p in PRODUCTS} for a in AREAS},
    }


def compute_quarter(industry, year, quarter, teams, macro, now_iso=None):
    """Simulate one quarter for all teams. Returns {team_id: report}.

    now_iso: optional fixed publication timestamp (ISO string). When given,
    identical inputs produce byte-identical report JSON (determinism proof).
    When None (production path via runner/CLI), the current UTC time is used.
    """
    macro = macro or {}
    mv = {"gdp": _num(macro.get("gdp_growth_pct"), 2.5),
          "infl": _num(macro.get("inflation_pct"), 0.0),
          "recession": bool(macro.get("recession", False)),
          "bank": _num(macro.get("central_bank_rate"), 8.0),
          "unemp": _num(macro.get("unemployment_pct"), 5.0),
          "mat_change": _num(macro.get("material_price_change_pct"), 0.0)}
    ordered = sorted(teams,
                     key=lambda t: t["team"]["company_number"])
    decs = [(t, _norm_decisions(t.get("decisions"))) for t in ordered]
    if not decs:
        return {}

    avg_price = {p: {
        "home": sum(d["prices"]["home"][p - 1] for _, d in decs) / len(decs),
        "export": sum(d["prices"]["export"][p - 1]
                      for _, d in decs) / len(decs)} for p in PRODUCTS}

    demand = {}
    for a in AREAS:
        hh = TABLES["T1"]["households"][a]
        demand[a] = {}
        for p in PRODUCTS:
            q = (hh * PENETRATION[p] * (1 + mv["gdp"] / 100)
                 * (0.85 if mv["recession"] else 1) * (1 - mv["infl"] / 400))
            if a == "export":
                q *= EXPORT_DAMPING
            demand[a][p] = max(q, 1.0)

    pas = [_phase_a(t, d, mv, avg_price, demand) for t, d in decs]

    # Demand shares from the attractiveness index (price elasticity via
    # price_factor, cross-elasticity via normalisation). Availability only
    # limits how much of that demand converts into sales (in _phase_b),
    # it never rewrites the demand share itself.
    for a in AREAS:
        for p in PRODUCTS:
            a1 = [pa["a1"][a][p] for pa in pas]
            s1 = sum(a1) or 1.0
            for i, pa in enumerate(pas):
                sh = a1[i] / s1
                pa["share"][a][p] = sh
                pa["demand_units"][a][p] = int(round(sh * demand[a][p]))

    reports, summaries = {}, []
    for (t, d), pa in zip(decs, pas):
        rep, summary = _phase_b(t, d, pa, mv, industry, year, quarter, now_iso)
        reports[t["team_id"]] = rep
        summaries.append(summary)

    companies = [{
        "company_number": s["company_number"],
        "company_name": s["company_name"],
        "share_price": s["share_price"],
        "dividend_pct": s["dividend_pct"],
        "net_profit": s["net_profit"],
        "net_worth": s["net_worth"]} for s in summaries]
    market_shares = {}
    for a in AREAS:
        market_shares[a] = {}
        for p in PRODUCTS:
            # Manual: "% Market Share of Sales ... calculated on the number
            # of sales, not orders."
            sl = [pa["sales"][a][p] for pa in pas]
            tot = sum(sl)
            market_shares[a][p] = [round(x / tot, 4) if tot else 0.0
                                   for x in sl]
    group = {"companies": companies, "market_shares": market_shares}
    for rep in reports.values():
        rep["group"] = group
    return reports


def _phase_b(team, d, pa, mv, industry, year, quarter, now_iso=None):
    cn = team["team"]["company_number"]
    name = team["team"]["name"]
    op = pa["op"]
    shift = d["shift_level"]
    premium = TABLES["T16"]["shift_premium"][shift]
    t3, t4, t7, t8 = TABLES["T3"], TABLES["T4"], TABLES["T7"], TABLES["T8"]
    t12, t14, t18 = TABLES["T12"], TABLES["T14"], TABLES["T18"]
    t20, t21 = TABLES["T20"], TABLES["T21"]

    demand_units = pa["demand_units"]
    sellable, opening, own_price = pa["sellable"], pa["opening"], pa["own_price"]
    sales = {a: {p: min(demand_units[a][p],
                        sellable[a][p] + opening[a][p])
                 for p in PRODUCTS} for a in AREAS}
    pa["sales"] = sales  # used for sales-based market shares
    backlog = {a: {p: demand_units[a][p] - sales[a][p]
                   for p in PRODUCTS} for a in AREAS}
    closing = {a: {p: sellable[a][p] + opening[a][p] - sales[a][p]
                   for p in PRODUCTS} for a in AREAS}
    units_sold = sum(sales[a][p] for a in AREAS for p in PRODUCTS)
    disc = _credit_discount(_num(d["days_credit_allowed"]))
    revenue = (sum(sales[a][p] * own_price[a][p]
                   for a in AREAS for p in PRODUCTS) * (1 - disc))

    # Cost of sales
    opening_stock_value = op["product_stock_value"]
    materials_cost = pa["mat_used"] * op["material_price"] / 1000
    wage = _num(d["assembly_wage"]["pounds"]) \
        + _num(d["assembly_wage"]["pence"]) / 100
    assembly_wages = pa["assy_hrs_used"] * wage * (1 + premium)
    machinists_wages = (pa["mach_hrs_used"] * MACHINIST_WAGE_PER_HR
                        * (1 + premium))
    machine_running = pa["mach_hrs_used"] * t8["machine_running_per_hr"]
    closing_stock_value = sum(closing[a][p] * t21["product_valuation"][p]
                              for a in AREAS for p in PRODUCTS)
    cost_of_sales = (opening_stock_value + materials_cost + assembly_wages
                     + machinists_wages + machine_running
                     - closing_stock_value)
    gross = revenue - cost_of_sales

    # Overheads
    promo = d["promotion"]
    advertising = sum(_num(x) for x in promo["advertising"]) * 1000
    trade_press = sum(_num(x) for x in promo["trade_press"]) * 1000
    support = sum(_num(x) for x in promo["support"]) * 1000
    merchandising = sum(_num(x) for x in promo["merchandising"]) * 1000
    n_sp = sum(d["salespeople"][a] for a in AREAS)
    sales_payroll = n_sp * max(
        _num(d["sales_remuneration"]["quarterly_salary_000"]) * 1000, 2000)
    sales_force = sales_payroll + n_sp * 3000
    research = _num(d["research_expenditure_000"]) * 1000
    management = _num(d["management_budget_000"]) * 1000
    ch = _num(d["contract_maintenance_hours"])
    maintenance = ch * t4["contracted_per_hr_per_machine"] \
        + 0.05 * ch * t4["uncontracted_per_hr"]
    supervision = t8["supervision_per_shift"] * shift
    production_overheads = t8["production_overheads_per_machine"] \
        * pa["machines"]
    planning = t8["planning_per_unit"] * pa["total_sched"]
    info = d["info_wanted"]
    info_charges = ((5000 if info.get("other_companies") else 0)
                    + (5000 if info.get("market_shares") else 0))
    credit_control = t20["credit_control_per_unit"] * units_sold
    guarantee = sum(0.02 * sum(sales[a][p] for a in AREAS) * t7[p]
                    for p in PRODUCTS)
    closing_total = sum(closing[a][p] for a in AREAS for p in PRODUCTS)
    warehousing = (t12["warehouse_fixed_per_q"]
                   + t12["warehouse_admin_per_q"]
                   + t12["per_order"]
                   * _num(d["raw_material"]["num_deliveries"])
                   + t12["external_storage_per_unit"]
                   * max(0, closing_total - t12["factory_storage_units"])
                   + t12["market_area_storage_per_unit"] * closing_total)
    fixed_overheads = t20["fixed_overheads_per_q"]
    variable_overhead = t20["variable_overhead_rate"] * revenue
    total_overheads = (advertising + trade_press + support + merchandising
                       + sales_force + research + management + maintenance
                       + supervision + production_overheads + planning
                       + info_charges + credit_control + guarantee
                       + warehousing + fixed_overheads + variable_overhead)
    operating = gross - total_overheads
    depreciation = (t18["machine_depreciation_per_q"] * op["machines_value"]
                    + t18["vehicle_depreciation_per_q"]
                    * op["vehicles_value"])
    interest_received = (op["cash"] * max(0.0, mv["bank"] - 2) / 100 / 4)
    interest_paid = op["overdraft"] * (mv["bank"] + 4) / 100 / 4
    pbt = operating + interest_received - interest_paid - depreciation
    tax = t20["tax_rate_annual"] * max(pbt, 0)
    net = pbt - tax
    dividend = _num(d["dividend_rate_pence"]) / 100 * SHARES_ISSUED
    retained = net - dividend

    # Balance sheet
    sold_m, new_m = pa["sold_m"], pa["new_m"]
    unit_mv = (op["machines_value"] / op["machines_count"]
               if op["machines_count"] else 0.0)
    sold_mv = sold_m * unit_mv
    machines_value = (op["machines_value"]
                      * (1 - t18["machine_depreciation_per_q"])
                      + new_m * t18["machine_order_payment"] - sold_mv)
    unit_vv = (op["vehicles_value"] / op["vehicles_count"]
               if op["vehicles_count"] else 0.0)
    sold_vv = pa["sold_v"] * unit_vv
    vehicles_value = (op["vehicles_value"]
                      * (1 - t18["vehicle_depreciation_per_q"])
                      + pa["bought_v"] * t18["vehicle_cost"] - sold_vv)
    prop = op["property"]
    fixed_assets = prop + machines_value + vehicles_value
    product_stocks = closing_stock_value
    mat_closing = pa["mat_avail"] - pa["mat_used"]
    material_stocks = (t21["material_valuation_rate"] * pa["mat_price"]
                       * mat_closing / 1000)
    debtors = revenue * _num(d["days_credit_allowed"]) / 90
    tax_due = tax
    sup = t14[d["raw_material"]["supplier_no"]]
    material_purchase = (pa["delivered"] * op["material_price"] / 1000
                         * (1 - sup["discount"]) + sup["delivery_charge"])
    after_next = (advertising + trade_press + support + merchandising
                  + info_charges + guarantee + maintenance + credit_control)
    next_q = (research + sales_payroll + warehousing + material_purchase
              + 0.5 * new_m * t18["machine_order_payment"])
    creditors = next_q + after_next + op["prev_after_next"]
    noncash = fixed_assets + product_stocks + material_stocks + debtors
    reserves = op["reserves"] + retained
    share_capital = float(INITIAL_STATE["share_capital"])
    net_worth = share_capital + reserves
    cl_ex_od = tax_due + creditors + op["unsecured"]
    plug = net_worth + cl_ex_od - noncash  # net cash position (cash - overdraft)
    if plug >= 0:
        cash, overdraft = plug, 0.0
    else:
        cash, overdraft = 0.0, -plug
    current_liabilities = tax_due + creditors + overdraft + op["unsecured"]
    total_assets = noncash + cash
    net_assets = total_assets - current_liabilities
    od_limit = overdraft_limit(cash, product_stocks, machines_value,
                               material_stocks, debtors, prop,
                               tax_due, creditors)
    sp = op["share_price"] * (1 + 0.6 * net / max(op["net_worth"], 1))
    share_price = round(max(0.10, min(50.00, sp)) + 1e-9, 2)

    # Cash flow (simplified creditor timing)
    trading_receipts = revenue - (debtors - op["debtors"])
    cash_costs = (materials_cost + assembly_wages + machinists_wages
                  + machine_running + total_overheads)
    trading_payments = cash_costs - (creditors - op["creditors"])
    tax_paid = op["tax_due"]
    net_operating = trading_receipts - trading_payments - tax_paid
    capital_receipts = sold_mv + sold_vv
    capital_payments = (new_m * t18["machine_order_payment"]
                        + pa["bought_v"] * t18["vehicle_cost"])
    net_investing = capital_receipts - capital_payments
    dividends_paid = dividend
    net_financing = ((overdraft - op["overdraft"]) - dividends_paid
                     - interest_paid)
    net_cash_flow = net_operating + net_investing + net_financing

    products = []
    for a in AREAS:
        for p in PRODUCTS:
            products.append({
                "product": p, "area": a,
                "scheduled": int(pa["sched"][a][p]),
                "produced": int(pa["produced"][a][p]),
                "rejected": int(pa["rejected"][a][p]),
                "demand": int(demand_units[a][p]),
                "sales": int(sales[a][p]),
                "backlog": int(backlog[a][p]),
                "closing_stock": int(closing[a][p]),
                "price": _r(own_price[a][p]),
                "improvement": bool(d["product_improvements"][p - 1]),
            })

    util_m = (pa["mach_hrs_used"] / pa["mach_avail"] * 100
              if pa["mach_avail"] else 0.0)
    util_a = (pa["assy_hrs_used"] / pa["assy_avail"] * 100
              if pa["assy_avail"] else 0.0)
    report = {
        "meta": {
            "industry_id": industry.get("id"),
            "simulation_code": industry.get("simulation_code"),
            "group_number": team["team"].get("group_number", 1),
            "company_number": cn, "company_name": name,
            "year": year, "quarter": quarter,
            "published_at": now_iso or datetime.now(timezone.utc).isoformat(),
            "auto_pass": bool(team.get("auto_pass", False)),
            "demo_data": False,
        },
        "decisions": d,
        "resources": {
            "machines": {
                "owned": pa["machines"], "new_installed": new_m,
                "sold": sold_m,
                "hours_available": _r(pa["mach_avail"]),
                "hours_used": _r(pa["mach_hrs_used"]),
                "utilisation_pct": _r(util_m),
                "machinists": op["machinists"],
                "machinists_required": (pa["machines"]
                                        * TABLES["T5"][shift]
                                        ["machinists_per_machine"]),
            },
            "assembly": {
                "workers": pa["workers"],
                "hours_available": _r(pa["assy_avail"]),
                "hours_used": _r(pa["assy_hrs_used"]),
                "utilisation_pct": _r(util_a),
                "wage_rate": _r(wage),
            },
            "vehicles": {"owned": pa["vehicles"],
                         "bought": pa["bought_v"], "sold": pa["sold_v"]},
            "materials": {
                "opening_stock": int(op["material_stock"]),
                "ordered": pa["ordered"], "delivered": pa["delivered"],
                "used": int(pa["mat_used"]),
                "closing_stock": int(mat_closing),
                "price_per_1000": _r(pa["mat_price"]),
            },
        },
        "products": products,
        "overheads": {
            "advertising": _r(advertising),
            "trade_press": _r(trade_press),
            "support": _r(support),
            "merchandising": _r(merchandising),
            "sales_force": _r(sales_force),
            "research": _r(research),
            "management": _r(management),
            "maintenance": _r(maintenance),
            "supervision": _r(supervision),
            "production_overheads": _r(production_overheads),
            "planning": _r(planning),
            "info_charges": _r(info_charges),
            "credit_control": _r(credit_control),
            "guarantee_servicing": _r(guarantee),
            "warehousing": _r(warehousing),
            "fixed_overheads": _r(fixed_overheads),
            "variable_overhead": _r(variable_overhead),
            "total": _r(total_overheads),
        },
        "pnl": {
            "sales_revenue": _r(revenue),
            "opening_stock_value": _r(opening_stock_value),
            "materials": _r(materials_cost),
            "assembly_wages": _r(assembly_wages),
            "machinists_wages": _r(machinists_wages),
            "machine_running": _r(machine_running),
            "closing_stock_value": _r(closing_stock_value),
            "cost_of_sales": _r(cost_of_sales),
            "gross_profit": _r(gross),
            "total_overheads": _r(total_overheads),
            "operating_profit": _r(operating),
            "interest_received": _r(interest_received),
            "interest_paid": _r(interest_paid),
            "depreciation": _r(depreciation),
            "profit_before_tax": _r(pbt),
            "tax_assessed": _r(tax),
            "net_profit": _r(net),
            "dividend_paid": _r(dividend),
            "retained_profit": _r(retained),
        },
        "balance_sheet": {
            "property": _r(prop),
            "machines": _r(machines_value),
            "vehicles": _r(vehicles_value),
            "fixed_assets": _r(fixed_assets),
            "product_stocks": _r(product_stocks),
            "material_stocks": _r(material_stocks),
            "debtors": _r(debtors),
            "cash_invested": _r(cash),
            "total_assets": _r(total_assets),
            "tax_due": _r(tax_due),
            "creditors": _r(creditors),
            "bank_overdraft": _r(overdraft),
            "unsecured_loans": _r(op["unsecured"]),
            "current_liabilities": _r(current_liabilities),
            "net_assets": _r(net_assets),
            "share_capital": _r(share_capital),
            "reserves": _r(reserves),
            "net_worth": _r(net_worth),
            "overdraft_limit": _r(od_limit),
        },
        "cash_flow": {
            "trading_receipts": _r(trading_receipts),
            "trading_payments": _r(trading_payments),
            "tax_paid": _r(tax_paid),
            "net_operating": _r(net_operating),
            "interest_received": _r(interest_received),
            "capital_receipts": _r(capital_receipts),
            "capital_payments": _r(capital_payments),
            "net_investing": _r(net_investing),
            "interest_paid": _r(interest_paid),
            "dividends_paid": _r(dividends_paid),
            "net_financing": _r(net_financing),
            "net_cash_flow": _r(net_cash_flow),
        },
        "group": {},  # filled in compute_quarter once all teams are done
        "economic": {
            "gdp_growth_pct": mv["gdp"],
            "unemployment_pct": mv["unemp"],
            "central_bank_rate": mv["bank"],
            "inflation_pct": mv["infl"],
            "recession": mv["recession"],
            "material_price_next_q": _r(pa["mat_price"]),
        },
    }
    dividend_pct = (_r(_num(d["dividend_rate_pence"]) / 100
                       / share_price * 100) if share_price else 0.0)
    summary = {"company_number": cn, "company_name": name,
               "share_price": share_price, "dividend_pct": dividend_pct,
               "net_profit": _r(net), "net_worth": _r(net_worth)}
    return report, summary
