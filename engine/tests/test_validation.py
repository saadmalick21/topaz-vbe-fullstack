import copy

from topaz_engine.constants import DEFAULT_DECISIONS
from topaz_engine.validation import validate_decisions


def test_price_zero_rejected():
    d = copy.deepcopy(DEFAULT_DECISIONS)
    d["prices"]["export"][0] = 0
    errs = validate_decisions(d, None)
    assert ("Price for Product 1 (Export market) must be greater than 0."
            in errs)


def test_home_price_zero_rejected():
    d = copy.deepcopy(DEFAULT_DECISIONS)
    d["prices"]["home"][2] = 0
    errs = validate_decisions(d, None)
    assert ("Price for Product 3 (Home market) must be greater than 0."
            in errs)


def test_overspend_rejected():
    d = copy.deepcopy(DEFAULT_DECISIONS)
    d["promotion"]["advertising"] = [1000.0, 1000.0, 1000.0]
    errs = validate_decisions(d, {"cash_invested": 400000,
                                  "overdraft_limit": 0})
    assert any(e.startswith("Committed spend \u00a3") for e in errs)


def test_assembly_time_below_minimum():
    d = copy.deepcopy(DEFAULT_DECISIONS)
    d["assembly_time_minutes"][0] = 50
    errs = validate_decisions(d, None)
    assert ("Assembly time for Product 1 cannot be below the minimum "
            "of 100 minutes." in errs)


def test_supplier3_deliveries_must_be_zero():
    d = copy.deepcopy(DEFAULT_DECISIONS)
    d["raw_material"]["supplier_no"] = 3
    d["raw_material"]["num_deliveries"] = 2
    errs = validate_decisions(d, None)
    assert any("num_deliveries must be 0" in e for e in errs)


def test_valid_decisions_pass():
    d = copy.deepcopy(DEFAULT_DECISIONS)
    errs = validate_decisions(d, {"cash_invested": 400000,
                                  "overdraft_limit": 50000})
    assert errs == []


def test_missing_keys_fall_back_to_defaults():
    assert validate_decisions(
        {}, {"cash_invested": 400000, "overdraft_limit": 50000}) == []
