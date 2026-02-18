import copy
from collections import OrderedDict
from datetime import datetime, timedelta

import pytest

from energis.run import rolling_horizon as rh
from energis.utils.timeseries import TimeSeriesTable


def _make_table(n_steps: int) -> TimeSeriesTable:
    index = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(n_steps)]
    data = {"waermebedarf_MWth": [float(5 + i) for i in range(n_steps)]}
    return TimeSeriesTable(index, list(data.keys()), data)


def _simple_config() -> dict:
    return {
        "run": {"dt_h": 1.0, "solver": "dummy"},
        "site": {"input_xlsx": "unused.xlsx"},
        "system": {
            "heat_pumps": [
                {
                    "id": "HP1",
                    "max_th_mw": 50.0,
                    "min_th_mw": 1.0,
                    "investment": {"enabled": True, "capacity_min_mw": 1.0, "capacity_max_mw": 100.0},
                }
            ],
            "storage": {"enabled": False},
        },
    }


def _design_summary(capacity: float = 10.0) -> OrderedDict:
    return OrderedDict(
        {
            "objective": OrderedDict(),
            "heat_pump_HP1": OrderedDict(
                [
                    ("Thermal_capacity_MW", capacity),
                    ("Build_binary", 1.0),
                ]
            ),
        }
    )


def test_capex_recorded_once(monkeypatch: pytest.MonkeyPatch) -> None:
    table = _make_table(3)
    base_config = _simple_config()

    pf_config = copy.deepcopy(base_config)
    pf_config["scenario"] = {"workflow": ["PF"]}

    rh_config = copy.deepcopy(base_config)
    rh_config["scenario"] = {
        "workflow": ["RH"],
        "rolling_horizon": {"heat_horizon_hours": 2.0, "step_hours": 1.0},
    }

    monkeypatch.setattr(rh, "load_input_excel", lambda *args, **kwargs: table)

    def pf_solver(table_arg, cfg, dt_h, solver_name, **kwargs):
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        costs = {"objective.Capex_cost_EUR": 100.0, "objective.OBJ_value_EUR": 100.0}
        return rh.ScenarioResult(table_arg, series, _design_summary(), costs, {"status": "ok"})

    monkeypatch.setattr(rh, "_solve_scenario", pf_solver)
    pf_result = rh.run_workflow([], overrides=pf_config)
    assert pf_result.pf_result is not None

    call_state = {"idx": 0}

    def rh_solver(table_arg, cfg, dt_h, solver_name, **kwargs):
        idx = call_state["idx"]
        call_state["idx"] += 1
        hp_cfg = cfg["system"]["heat_pumps"][0]
        investment_enabled = hp_cfg.get("investment", {}).get("enabled", True)
        if idx == 0:
            assert investment_enabled is True
            capex = 100.0
        else:
            assert investment_enabled is False
            capex = 0.0

        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        costs = {"objective.Capex_cost_EUR": capex, "objective.OBJ_value_EUR": capex}
        return rh.ScenarioResult(table_arg, series, _design_summary(), costs, {"status": "ok"})

    monkeypatch.setattr(rh, "_solve_scenario", rh_solver)
    rh_result = rh.run_workflow([], overrides=rh_config)

    assert rh_result.rh_result is not None
    assert call_state["idx"] == 3
    assert rh_result.rh_result.costs["objective.Capex_cost_EUR"] == pytest.approx(
        pf_result.pf_result.costs["objective.Capex_cost_EUR"]
    )
