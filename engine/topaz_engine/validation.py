# Decision validation — SPEC.md section 7. Stdlib only. Never raises on bad input.

from .constants import AREAS, PRODUCTS, TABLES, DEFAULT_DECISIONS


def _get(data, *path):
    cur = data
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            cur = None
            break
    if cur is None:
        cur = DEFAULT_DECISIONS
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                return None
    return cur


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _is_nonneg_int(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and float(v).is_integer() and v >= 0)


def validate_decisions(data, funds):
    """Return a list of plain-language error strings (empty = valid)."""
    data = data or {}
    errors = []

    # Rule 1: all 6 prices > 0
    prices = _get(data, "prices") or {}
    for market, label in (("export", "Export market"), ("home", "Home market")):
        plist = prices.get(market) or []
        for i in range(3):
            v = _f(plist[i] if i < len(plist) else None, 0.0)
            if not v > 0:
                errors.append(
                    "Price for Product %d (%s) must be greater than 0."
                    % (i + 1, label))

    # Rule 2: assembly time >= product minimum
    at = _get(data, "assembly_time_minutes") or []
    for p in PRODUCTS:
        m = TABLES["T3"][p]["assembly_min"]
        v = _f(at[p - 1] if p - 1 < len(at) else None, -1.0)
        if v < m:
            errors.append(
                "Assembly time for Product %d cannot be below the minimum "
                "of %d minutes." % (p, m))

    # Rule 3: shift level
    if _get(data, "shift_level") not in (1, 2, 3):
        errors.append("Shift level must be 1, 2 or 3.")

    # Rule 4: salary / management minima (values entered in £'000)
    if _f(_get(data, "sales_remuneration", "quarterly_salary_000"), 0.0) < 2.0:
        errors.append(
            "Sales quarterly salary must be at least \u00a32,000 "
            "(2.0 in \u00a3'000).")
    if _f(_get(data, "management_budget_000"), 0.0) < 40.0:
        errors.append(
            "Management budget must be at least \u00a340,000 "
            "(40.0 in \u00a3'000).")

    # Rule 5: supplier number; supplier 3 has automatic deliveries
    sup = _get(data, "raw_material", "supplier_no")
    if sup not in (0, 1, 2, 3):
        errors.append("Supplier number must be 0, 1, 2 or 3.")
    if sup == 3 and _get(data, "raw_material", "num_deliveries") != 0:
        errors.append(
            "Supplier 3 delivers automatically 12 times per quarter: "
            "num_deliveries must be 0.")

    # Rule 6: counts/quantities are non-negative integers; percentages 0-100
    int_fields = ([(("salespeople", a), "Salespeople (%s)" % a) for a in AREAS]
                  + [(("salespeople_changes", k),
                      "Salespeople changes (%s)" % k) for k in
                     ("recruit", "dismiss", "train")]
                  + [(("assembly_changes", k), "Assembly changes (%s)" % k)
                     for k in ("recruit", "dismiss", "train")]
                  + [(("machines_to_sell",), "Machines to sell"),
                     (("new_machines_to_order",), "New machines to order"),
                     (("vans_to_buy",), "Vans to buy"),
                     (("vans_to_sell",), "Vans to sell"),
                     (("contract_maintenance_hours",),
                      "Contract maintenance hours"),
                     (("raw_material", "units_to_order"),
                      "Raw material units to order"),
                     (("raw_material", "num_deliveries"),
                      "Raw material number of deliveries"),
                     (("assembly_wage", "pounds"), "Assembly wage (pounds)"),
                     (("assembly_wage", "pence"), "Assembly wage (pence)")])
    for path, label in int_fields:
        if not _is_nonneg_int(_get(data, *path)):
            errors.append("%s must be a non-negative integer." % label)
    md = _get(data, "make_deliver") or {}
    for a in AREAS:
        for i, v in enumerate(md.get(a) or []):
            if not _is_nonneg_int(v):
                errors.append(
                    "Make/deliver units for Product %d (%s) must be a "
                    "non-negative integer." % (i + 1, a))
    pct = _f(_get(data, "sales_remuneration", "commission_pct"), -1.0)
    if not 0 <= pct <= 100:
        errors.append(
            "Sales commission percentage must be between 0 and 100.")

    # Rule 7: affordability
    promo = _get(data, "promotion") or {}
    promo000 = sum(_f(x) for k in ("trade_press", "advertising",
                                  "support", "merchandising")
                   for x in (promo.get(k) or [0, 0, 0]))
    n_sp = sum(_f((_get(data, "salespeople") or {}).get(a), 0.0)
               for a in AREAS)
    sal000 = _f(_get(data, "sales_remuneration", "quarterly_salary_000"))
    wage = (_f(_get(data, "assembly_wage", "pounds"))
            + _f(_get(data, "assembly_wage", "pence")) / 100)
    raw_units = _f(_get(data, "raw_material", "units_to_order"))
    t14 = TABLES["T14"].get(sup, {"discount": 0.0, "delivery_charge": 0})
    committed = ((_f(_get(data, "research_expenditure_000"))
                 + _f(_get(data, "management_budget_000")) + promo000) * 1000
                 + n_sp * max(sal000 * 1000, 2000) + n_sp * 3000
                 + 48 * 420 * wage
                 + raw_units * 0.50 * (1 - t14["discount"])
                 + t14["delivery_charge"]
                 + _f(_get(data, "new_machines_to_order")) * 100000
                 + _f(_get(data, "vans_to_buy")) * 15000)
    funds = funds or {"cash_invested": 400000, "overdraft_limit": 0}
    avail = _f(funds.get("cash_invested")) + _f(funds.get("overdraft_limit"))
    if committed > avail:
        errors.append(
            "Committed spend \u00a3{:,.0f} exceeds available funds "
            "\u00a3{:,.0f} (cash + overdraft limit). Reduce promotion, "
            "orders or recruitment.".format(committed, avail))

    # Rule 8: dividend and credit >= 0
    if _f(_get(data, "dividend_rate_pence"), -1.0) < 0:
        errors.append("Dividend rate must be at least 0 pence.")
    if _f(_get(data, "days_credit_allowed"), -1.0) < 0:
        errors.append("Days credit allowed must be at least 0.")

    return errors
