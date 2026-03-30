from datetime import datetime, timedelta
import os

import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:
    HAVE_PYOMO = False

from energis.io.loader import load_input_excel
from energis.models.system_builder import build_model
from energis.utils.xlsx import write_simple_xlsx


def _date_range(start: str, periods: int, freq_hours: int = 1):
    base = datetime.fromisoformat(start)
    return [base + timedelta(hours=freq_hours * i) for i in range(periods)]

@pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not available")
def test_bus_constraints_exist(tmp_path):
    # minimal data
    xls = tmp_path/"Import_Data.xlsx"
    idx = _date_range("2023-01-01T00:00:00", periods=3)
    headers = [
        "Datum",
        "Day_Ahead_Price \u20ac/MWh",
        "W\u00e4rmebedarf MW",
        "CO2_consumption_based kgCO2/MWh",
    ]
    rows = [
        [idx[i], 50 + 5 * i, 10, 350]
        for i in range(len(idx))
    ]
    write_simple_xlsx(str(xls), headers, rows)

    # Inline config - no external files needed
    cfg = {
        "site": {"input_xlsx": str(xls)},
        "system": {
            "heat_pumps": [
                {
                    "id": "HP1",
                    "enabled": True,
                    "type": "standard",
                    "min_load": 0.3,
                    "cop_default": 3.5,
                    "min_th_mw": 0.0,
                    "max_th_mw": 5.0,
                    "investment": {
                        "enabled": False,
                        "capacity_min_mw": 5.0,
                        "capacity_max_mw": 5.0,
                        "initial_capacity_mw": 5.0,
                    },
                }
            ],
            "storage": {"enabled": False},
            "generators": {
                "gas_boiler": {
                    "enabled": True,
                    "fuel_bus": "gas",
                    "th_eff": 0.9,
                    "el_eff": None,
                    "cap_th_mw": 10.0,
                }
            },
        },
        "grid": {
            "energy_fee_eur_mwh": 0.0,
            "gridcost_eur_mwh": 0.0,
            "demand_charge_eur_per_mw_y": 0.0,
        },
        "fuels": {
            "gas": {"price_eur_mwh": 40.0, "ef_kg_per_mwh_fuel": 200.0},
        },
        "costs": {
            "co2_price_eur_per_t": 100.0,
            "dump_cost_eur_per_mwh_th": 1.0,
            "include_co2_cost_in_objective": False,
            "include_gridcost_in_energy": False,
            "include_demand_charge_in_rh": False,
        },
        "generators": {
            "gas_boiler": {"th_eff": 0.9, "el_eff": None, "fuel_bus": "gas"},
        },
    }
    data = load_input_excel(cfg["site"]["input_xlsx"], cfg["site"], dt_hours=1.0)
    m = build_model(data, cfg, dt_h=1.0)
    assert hasattr(m, "el_balance")
    assert hasattr(m, "ht_balance")
