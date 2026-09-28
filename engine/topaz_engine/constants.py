# Engine parameters — exact values from SPEC.md section 5 (Tables 1-23).

AREAS = ["south", "west", "north", "export"]
PRODUCTS = [1, 2, 3]

TABLES = {
    # T1: households per area (with product-mix ratios), retail outlets per area
    "T1": {
        "households": {"south": 7_000_000, "west": 4_000_000,
                       "north": 13_000_000, "export": 80_000_000},
        "product_ratios": {"south": (1, 2, 4), "west": (1, 1, 2),
                           "north": (1, 3, 9), "export": (10, 15, 55)},
        "outlets": {"south": 3000, "west": 2000, "north": 4000, "export": 20000},
    },
    # T2: salesperson expenses and business-intelligence charges (£/q)
    "T2": {"salesperson_expenses_per_q": 3000,
           "competitor_info": 5000, "market_share_info": 5000},
    # T3: manufacturing per unit — machining minutes, assembly minutes, material content
    "T3": {1: {"machining_min": 60, "assembly_min": 100, "material_content": 1},
           2: {"machining_min": 75, "assembly_min": 150, "material_content": 2},
           3: {"machining_min": 120, "assembly_min": 300, "material_content": 3}},
    # T4: maintenance (£/hr; contracted rate is per machine)
    "T4": {"contracted_per_hr_per_machine": 60, "uncontracted_per_hr": 120},
    # T5: machine hours per quarter and machinists per machine, by shift level
    "T5": {1: {"machine_hours_per_q": 576, "machinists_per_machine": 4},
           2: {"machine_hours_per_q": 1068, "machinists_per_machine": 8},
           3: {"machine_hours_per_q": 1602, "machinists_per_machine": 12}},
    # T6: scrap cost per rejected unit (£)
    "T6": {1: 20, 2: 40, 3: 60},
    # T7: guarantee servicing cost per serviced unit (£)
    "T7": {1: 60, 2: 120, 3: 200},
    # T8: supervision, production overheads, machine running, planning
    "T8": {"supervision_per_shift": 10000,
           "production_overheads_per_machine": 2000,
           "machine_running_per_hr": 7, "planning_per_unit": 1},
    # T9: vehicle capacity (units; mixed loads allowed)
    "T9": {1: 40, 2: 40, 3: 20},
    # T10: journey days per area
    "T10": {"south": 1, "west": 2, "north": 4, "export": 6},
    # T11: transport costs (£)
    "T11": {"driver_wages_per_vehicle": 7000,
            "own_running_per_day": 50, "hire_per_day": 200},
    # T12: warehousing (£/q unless noted)
    "T12": {"factory_storage_units": 2000, "warehouse_fixed_per_q": 3750,
            "warehouse_admin_per_q": 3250, "per_order": 750,
            "external_storage_per_unit": 1.50,
            "market_area_storage_per_unit": 2.0},
    # T14: suppliers — discount, delivery charge, minimum order.
    # Supplier 3: 12 automatic weekly deliveries -> num_deliveries must be 0.
    "T14": {0: {"discount": 0.0, "delivery_charge": 0, "min_order": 1},
            1: {"discount": 0.10, "delivery_charge": 200, "min_order": 1},
            2: {"discount": 0.15, "delivery_charge": 300, "min_order": 1000},
            3: {"discount": 0.30, "delivery_charge": 100, "min_order": 0,
                "max_order": 50000}},
    # T15: personnel department charges — recruit, dismiss, train (£)
    "T15": {"salesperson": {"recruit": 1500, "dismiss": 5000, "train": 6000},
            "assembly": {"recruit": 1200, "dismiss": 3000, "train": 4500},
            "machinist": {"recruit": 750, "dismiss": 1500, "train": None}},
    # T16: worker hours per quarter; shift premium as fraction of basic wage
    "T16": {"basic_hours_per_q": 420,
            "saturday_overtime": {1: 84, 2: 42, 3: 42},
            "sunday_overtime": 72,
            "shift_premium": {1: 0.0, 2: 1 / 3, 3: 2 / 3}},
    # T17: minima
    "T17": {"machinist_min_paid_hours": 400,
            "assembly_min_wage_per_hr": 8.50,
            "unskilled_skilled_ratio": 0.65,
            "min_sales_salary_per_q": 2000,
            "min_management_budget_per_q": 40000},
    # T18: machine/vehicle cost and depreciation
    "T18": {"machine_cost": 200000, "machine_order_payment": 100000,
            "machine_install_payment": 100000, "vehicle_cost": 15000,
            "machine_depreciation_per_q": 0.025,
            "vehicle_depreciation_per_q": 0.0625},
    # T19: overdraft limit formula weights
    "T19": {"cash_weight": 1.0, "asset_weight": 0.5,
            "property_weight": 0.25, "liability_weight": 1.0, "floor": 0.0},
    # T20: tax, overheads, credit control, interest margins vs central bank rate
    "T20": {"tax_rate_annual": 0.30, "fixed_overheads_per_q": 10000,
            "variable_overhead_rate": 0.0025, "credit_control_per_unit": 1.50,
            "interest_investment_margin": -0.02,
            "interest_overdraft_margin": 0.04,
            "interest_unsecured_margin": 0.10},
    # T21: stock valuations — product £/unit; materials = 50% of last q price
    "T21": {"product_valuation": {1: 80, 2: 120, 3: 200},
            "material_valuation_rate": 0.50},
    # T22: creditor timing (engine uses a documented simplification)
    "T22": {"paid_quarter_after_next": ["advertising", "guarantee_servicing",
                                        "hired_transport", "maintenance",
                                        "external_stock", "business_intel"],
            "paid_next_quarter": ["research", "personnel", "warehousing",
                                  "misc", "materials_purchased",
                                  "machines_50pct"]},
    # T23: credit discount by days_credit_allowed; >= 30 days -> nil
    "T23": {"tiers": [(7, 0.10), (15, 0.075), (29, 0.05)], "default": 0.0},
}

# Default decision form values — SPEC.md section 2 (field names locked).
DEFAULT_DECISIONS = {
    "product_improvements": [False, False, False],
    "prices": {
        "export": [120.0, 180.0, 260.0],
        "home": [110.0, 165.0, 240.0],
    },
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
    "raw_material": {"units_to_order": 4000, "supplier_no": 1,
                     "num_deliveries": 2},
    "new_machines_to_order": 0,
}

# New-team state before Q1 — SPEC.md section 9.
INITIAL_STATE = {
    "machines": 8,
    "vehicles": 6,
    "salespeople": 12,
    "assembly_workers": 48,
    "machinists": 32,
    "cash_invested": 400000,
    "share_capital": 1000000,
    "shares_issued": 1000000,
    "reserves": 200000,
    "property": 250000,
    "material_stock": 2000,
    "material_price_per_1000": 500,
    "product_stock_per_area_product": 60,
    "share_price": 1.50,
}
