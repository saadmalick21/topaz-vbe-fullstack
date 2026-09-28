import copy
import hashlib
import json

from topaz_engine.constants import DEFAULT_DECISIONS
from topaz_engine.simulation import compute_quarter


def _inputs():
    industry = {"id": 1, "simulation_code": "TEST-1",
                "name": "Test Industry"}
    macro = {"inflation_pct": 2.0, "material_price_change_pct": 5.0,
             "recession": False, "central_bank_rate": 8.0,
             "gdp_growth_pct": 2.5, "unemployment_pct": 5.0, "note": ""}
    d1 = copy.deepcopy(DEFAULT_DECISIONS)
    d2 = copy.deepcopy(DEFAULT_DECISIONS)
    d2["prices"]["home"] = [100.0, 150.0, 220.0]
    d2["prices"]["export"] = [110.0, 165.0, 240.0]
    d2["shift_level"] = 2
    d2["new_machines_to_order"] = 1
    d2["info_wanted"] = {"other_companies": True, "market_shares": True}
    teams = [
        {"team_id": 7, "team": {"company_number": 2, "name": "Beta",
                                "group_number": 1},
         "decisions": d2, "prev": None, "auto_pass": False},
        {"team_id": 3, "team": {"company_number": 1, "name": "Alpha",
                                "group_number": 1},
         "decisions": d1, "prev": None, "auto_pass": False},
    ]
    return industry, macro, teams


def _norm_hash(reports):
    r = copy.deepcopy(reports)
    for rep in r.values():
        rep["meta"]["published_at"] = "FIXED"
    return hashlib.sha256(
        json.dumps(r, sort_keys=True).encode()).hexdigest()


def test_identical_inputs_identical_outputs():
    industry, macro, teams = _inputs()
    h1 = _norm_hash(compute_quarter(industry, 1, 1, teams, macro))
    industry2, macro2, teams2 = _inputs()
    h2 = _norm_hash(compute_quarter(industry2, 1, 1, teams2, macro2))
    assert h1 == h2


def test_team_order_does_not_matter():
    industry, macro, teams = _inputs()
    r1 = compute_quarter(industry, 1, 1, teams, macro)
    teams_rev = list(reversed(copy.deepcopy(teams)))
    r2 = compute_quarter(industry, 1, 1, teams_rev, macro)
    assert _norm_hash(r1) == _norm_hash(r2)
    # per-team reports identical under their own team_id
    for tid in r1:
        a, b = copy.deepcopy(r1[tid]), copy.deepcopy(r2[tid])
        a["meta"]["published_at"] = b["meta"]["published_at"] = "FIXED"
        assert a == b


def test_roll_forward_is_deterministic():
    industry, macro, teams = _inputs()
    q1 = compute_quarter(industry, 1, 1, teams, macro)
    teams_q2 = []
    for t in teams:
        t2 = copy.deepcopy(t)
        t2["prev"] = q1[t["team_id"]]
        teams_q2.append(t2)
    h1 = _norm_hash(compute_quarter(industry, 1, 2, teams_q2, macro))
    q1b = compute_quarter(industry, 1, 1, teams, macro)
    teams_q2b = []
    for t in teams:
        t2 = copy.deepcopy(t)
        t2["prev"] = q1b[t["team_id"]]
        teams_q2b.append(t2)
    h2 = _norm_hash(compute_quarter(industry, 1, 2, teams_q2b, macro))
    assert h1 == h2


def test_byte_identical_with_fixed_timestamp():
    # With now_iso fixed, identical inputs -> byte-identical JSON, no normalisation.
    industry, macro, teams = _inputs()
    r1 = compute_quarter(industry, 1, 1, teams, macro, now_iso="2026-01-01T00:00:00+00:00")
    industry2, macro2, teams2 = _inputs()
    r2 = compute_quarter(industry2, 1, 1, teams2, macro2, now_iso="2026-01-01T00:00:00+00:00")
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
