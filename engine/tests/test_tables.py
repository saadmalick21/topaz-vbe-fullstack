from topaz_engine.constants import TABLES
from topaz_engine.simulation import overdraft_limit


def test_t19_worked_example():
    # 100000 + 0.5*340000 + 0.25*250000 - 50000 = 282500
    assert overdraft_limit(100000, 50000, 200000, 10000, 80000,
                           250000, 20000, 30000) == 282500


def test_t19_negative_floors_to_zero():
    assert overdraft_limit(0, 0, 0, 0, 0, 0, 100000, 100000) == 0


def test_key_table_values():
    assert TABLES["T5"][1]["machine_hours_per_q"] == 576
    assert TABLES["T5"][2]["machine_hours_per_q"] == 1068
    assert TABLES["T5"][3]["machine_hours_per_q"] == 1602
    assert TABLES["T18"]["machine_cost"] == 200000
    assert TABLES["T18"]["vehicle_cost"] == 15000
    assert TABLES["T21"]["product_valuation"] == {1: 80, 2: 120, 3: 200}
    assert TABLES["T1"]["outlets"]["export"] == 20000
