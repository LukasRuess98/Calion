from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta
import copy
import json
from pathlib import Path
from typing import List

import pytest

from calion.run import rolling_horizon as rh
from calion.run import workflow as _wf
from calion.run import rh_engine as _rhe
from calion.utils.timeseries import TimeSeriesTable


def _make_table(n_steps: int) -> TimeSeriesTable:
    index = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(n_steps)]
    data = {
        "waermebedarf_MWth": [float(10 + i) for i in range(n_steps)],
    }
    return TimeSeriesTable(index, list(data.keys()), data)


@pytest.fixture
def simple_config() -> dict:
    return {
        "run": {"dt_h": 1.0, "solver": "dummy"},
        "site": {"input_xlsx": "unused.xlsx"},
        "system": {
            "heat_pumps": [
                {"id": "HP1", "max_th_mw": 100.0, "min_th_mw": 10.0, "investment": {}},
            ],
            "storage": {
                "enabled": True,
                "max_energy_mwh": 100.0,
                "max_power_mw": 30.0,
                "soc0_mwh": 0.0,
                "investment": {"enabled": True},
            },
        },
    }


def test_pf_only_workflow(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {"run_mode": "PF_ONLY"}

    table = _make_table(4)

    def fake_loader(path: str, site_cfg: dict, dt_hours: float) -> TimeSeriesTable:
        assert dt_hours == 1.0
        return table

    def fake_solve(table_arg, cfg, dt_h, solver_name):
        assert solver_name == "dummy"
        assert dt_h == 1.0
        assert table_arg.index == table.index
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        summary = OrderedDict(
            {
                "objective": OrderedDict(),
                "heat_pump_HP1": OrderedDict(
                    [
                        ("Thermal_capacity_MW", 5.0),
                        ("Build_binary", 1.0),
                    ]
                ),
                "storage_TES": OrderedDict(
                    [
                        ("Capacity_MWh", 20.0),
                        ("Power_limit_MW", 5.0),
                        ("Build_binary", 1.0),
                    ]
                ),
            }
        )
        costs = {"objective.OBJ_value_EUR": 0.0}
        solver = {"status": "ok"}
        return rh.ScenarioResult(table_arg, series, summary, costs, solver)

    monkeypatch.setattr(_wf, "load_input_excel", fake_loader)
    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    result = rh.run_workflow([], overrides=config)

    assert result.pf_result is not None
    assert result.rh_result is None
    assert result.design is not None
    assert result.plan.steps == ["PF"]
    assert result.design.heat_pumps["HP1"]["capacity_mw"] == pytest.approx(5.0)
    assert result.design.storage["capacity_mwh"] == pytest.approx(20.0)


def test_rh_only_workflow_aggregates(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {
        "workflow": ["RH"],
        "rolling_horizon": {"heat_horizon_hours": 4.0, "step_hours": 2.0, "terminal_policy": "free"},
    }

    table = _make_table(5)

    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    window_series = [
        OrderedDict({"TES_SOC_MWh": [0.0, 1.0, 2.0, 3.0], "P_buy_MW": [1.0, 1.0, 1.0, 1.0]}),
        OrderedDict({"TES_SOC_MWh": [1.0, 2.0, 3.0, 4.0], "P_buy_MW": [2.0, 2.0, 2.0, 2.0]}),
        OrderedDict({"TES_SOC_MWh": [2.0], "P_buy_MW": [3.0]}),
    ]

    expected_soc = [0.0, 1.0, 2.0]

    call_state = {"idx": 0}

    def fake_solve(table_arg, cfg, dt_h, solver_name, **kwargs):
        idx = call_state["idx"]
        call_state["idx"] += 1
        assert kwargs.get("soc_init_override", 0.0) == pytest.approx(expected_soc[idx])
        series = window_series[idx]
        summary = OrderedDict({"objective": OrderedDict()})
        costs = {"objective.OBJ_value_EUR": float(idx)}
        solver = {"status": "ok"}
        return rh.ScenarioResult(table_arg, series, summary, costs, solver)

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    result = rh.run_workflow([], overrides=config)

    assert result.pf_result is None
    assert result.rh_result is not None
    assert result.plan.steps == ["RH"]
    assert len(result.rh_result.windows) == 3
    assert result.rh_result.series["TES_SOC_MWh"] == [0.0, 1.0, 1.0, 2.0, 2.0]
    assert result.rh_result.series["P_buy_MW"] == [1.0, 1.0, 2.0, 2.0, 3.0]


def test_pf_then_rh_fix_design(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {
        "run_mode": "PF_THEN_RH",
        "rolling_horizon": {"HEAT_HORIZON_HOURS": 4.0, "STEP_HOURS": 2.0, "terminal_policy": "free"},
    }

    table = _make_table(5)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    pf_summary = OrderedDict(
        {
            "objective": OrderedDict(),
            "heat_pump_HP1": OrderedDict(
                [
                    ("Thermal_capacity_MW", 5.0),
                    ("Build_binary", 1.0),
                ]
            ),
            "storage_TES": OrderedDict(
                [
                    ("Capacity_MWh", 20.0),
                    ("Power_limit_MW", 5.0),
                    ("Build_binary", 1.0),
                ]
            ),
        }
    )

    window_series = [
        OrderedDict({"TES_SOC_MWh": [0.0, 1.0, 2.0, 3.0], "P_buy_MW": [1.0, 1.0, 1.0, 1.0]}),
        OrderedDict({"TES_SOC_MWh": [1.0, 2.0, 3.0, 4.0], "P_buy_MW": [2.0, 2.0, 2.0, 2.0]}),
        OrderedDict({"TES_SOC_MWh": [2.0], "P_buy_MW": [3.0]}),
    ]

    expected_soc = [0.0, 1.0, 2.0]
    call_state = {"idx": 0}

    def fake_solve(table_arg, cfg, dt_h, solver_name, **kwargs):
        idx = call_state["idx"]
        call_state["idx"] += 1
        if idx == 0:
            series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
            costs = {"objective.OBJ_value_EUR": 0.0}
            return rh.ScenarioResult(table_arg, series, pf_summary, costs, {"status": "ok"})

        window_idx = idx - 1
        assert kwargs.get("soc_init_override", 0.0) == pytest.approx(expected_soc[window_idx])
        hp_cfg = cfg["system"]["heat_pumps"][0]
        assert hp_cfg["investment"]["enabled"] is False
        assert hp_cfg["max_th_mw"] == pytest.approx(5.0)
        assert hp_cfg["min_th_mw"] == pytest.approx(5.0)
        assert hp_cfg["investment"]["capacity_min_mw"] == pytest.approx(5.0)
        assert hp_cfg["investment"]["capacity_max_mw"] == pytest.approx(5.0)
        storage_cfg = cfg["system"]["storage"]
        assert storage_cfg["investment"]["enabled"] is False
        assert storage_cfg["investment"]["energy_capacity_min_mwh"] == pytest.approx(20.0)
        assert storage_cfg["investment"]["energy_capacity_max_mwh"] == pytest.approx(20.0)
        assert storage_cfg["terminal"]["policy"] == "free"
        series = window_series[window_idx]
        costs = {"objective.OBJ_value_EUR": float(window_idx)}
        summary = OrderedDict({"objective": OrderedDict()})
        return rh.ScenarioResult(table_arg, series, summary, costs, {"status": "ok"})

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    result = rh.run_workflow([], overrides=config)

    assert result.pf_result is not None
    assert result.design is not None
    assert result.rh_result is not None
    assert result.plan.steps == ["PF", "RH"]
    assert result.rh_result.series["TES_SOC_MWh"] == [0.0, 1.0, 1.0, 2.0, 2.0]
    assert result.design.heat_pumps["HP1"]["capacity_mw"] == pytest.approx(5.0)
    assert result.design.storage["power_mw"] == pytest.approx(5.0)


def test_custom_workflow_sequence(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {
        "workflow": ["PF", "RH"],
        "fix_design": False,
        "rolling_horizon": {"HEAT_HORIZON_HOURS": 4.0, "STEP_HOURS": 2.0},
    }

    table = _make_table(4)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    pf_summary = OrderedDict(
        {
            "objective": OrderedDict(),
            "heat_pump_HP1": OrderedDict(
                [
                    ("Thermal_capacity_MW", 5.0),
                    ("Build_binary", 1.0),
                ]
            ),
        }
    )

    call_state = {"idx": 0}

    def fake_solve(table_arg, cfg, dt_h, solver_name, **kwargs):
        idx = call_state["idx"]
        call_state["idx"] += 1
        if idx == 0:
            series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
            return rh.ScenarioResult(table_arg, series, pf_summary, {}, {})
        hp_cfg = cfg["system"]["heat_pumps"][0]
        # Design fixation is disabled
        assert hp_cfg.get("investment", {}).get("enabled", True) is True
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        return rh.ScenarioResult(table_arg, series, {}, {}, {})

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    result = rh.run_workflow([], overrides=config)

    assert result.pf_result is not None
    assert result.rh_result is not None
    assert result.plan.steps == ["PF", "RH"]


def test_workflow_accepts_string(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {"workflow": "PF"}

    table = _make_table(2)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    def fake_solve(table_arg, cfg, dt_h, solver_name):
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        summary = OrderedDict({"objective": OrderedDict()})
        return rh.ScenarioResult(table_arg, series, summary, {}, {})

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    result = rh.run_workflow([], overrides=config)
    assert result.pf_result is not None
    assert result.plan.steps == ["PF"]


def test_unknown_workflow_step(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {"workflow": ["PF", "UNKNOWN"]}

    table = _make_table(2)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    def fake_solve(table_arg, cfg, dt_h, solver_name):
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        summary = OrderedDict({"objective": OrderedDict()})
        return rh.ScenarioResult(table_arg, series, summary, {}, {})

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    with pytest.raises(ValueError):
        rh.run_workflow([], overrides=config)


def test_custom_workflow_registration(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {"workflow": ["CUSTOM"]}

    table = _make_table(2)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    def fake_merge(paths):
        return copy.deepcopy(config)

    monkeypatch.setattr(_wf, "load_and_merge", fake_merge)

    executed: List[str] = []

    def custom_step(context: rh.WorkflowContext) -> None:
        executed.append("X")
        context.pf_result = rh.ScenarioResult(context.table, OrderedDict(), {}, {}, {})

    rh.register_workflow_step("CUSTOM", custom_step)
    try:
        result = rh.run_workflow(["dummy.yaml"])
    finally:
        rh.unregister_workflow_step("CUSTOM")

    assert executed == ["X"]
    assert result.plan.steps == ["CUSTOM"]
    assert result.pf_result is not None


def test_cli_entrypoint(monkeypatch: pytest.MonkeyPatch, simple_config: dict, caplog: pytest.LogCaptureFixture) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {"workflow": ["PF"]}

    table = _make_table(2)

    def fake_merge(paths):
        return copy.deepcopy(config)

    def fake_solve(table_arg, cfg, dt_h, solver_name, **kwargs):
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        summary = OrderedDict({"objective": OrderedDict()})
        return rh.ScenarioResult(table_arg, series, summary, {"objective.OBJ_value_EUR": 0.0}, {})

    monkeypatch.setattr(_wf, "load_and_merge", fake_merge)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)
    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    with caplog.at_level("INFO"):
        exit_code = rh.main(["configs.yaml", "--print-design"])

    assert exit_code == 0
    assert "[workflow] Executed steps" in caplog.text


def test_cli_overrides_env(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    captured: dict = {}

    def fake_run_workflow(configs, overrides=None):
        captured["overrides"] = overrides
        return rh.WorkflowResult(
            config={},
            pf_result=None,
            rh_result=None,
            mpc_result=None,
            design=None,
            plan=rh.WorkflowPlan(steps=("RH",), fix_design=False),
        )

    monkeypatch.setattr(_wf, "run_workflow", fake_run_workflow)

    monkeypatch.setenv("RUN_MODE", "RH_ONLY")
    monkeypatch.setenv("HEAT_HORIZON_HOURS", "6")
    monkeypatch.setenv("STEP_HOURS", "3")
    monkeypatch.setenv("TERMINAL_POLICY", "hold")
    monkeypatch.setenv("FIX_DESIGN", "1")
    monkeypatch.setenv("INCLUDE_GRIDCOST_IN_ENERGY", "0")
    monkeypatch.setenv("INCLUDE_DEMAND_CHARGE_IN_RH", "1")
    monkeypatch.setenv("INCLUDE_CO2_COST_IN_OBJECTIVE", "0")
    monkeypatch.setenv("PF_DESIGN_JSON", "/tmp/env_design.json")

    with caplog.at_level("INFO"):
        exit_code = rh.main(
            [
                "config.yaml",
                "--run-mode",
                "PF_THEN_RH",
                "--heat-horizon-hours",
                "24",
                "--step-hours",
                "12",
                "--terminal-policy",
                "free",
                "--include-gridcost-in-energy",
                "--no-include-demand-charge-in-rh",
                "--include-co2-cost-in-objective",
                "--no-fix-design",
                "--pf-design-json",
                "/tmp/cli_design.json",
            ]
        )

    assert exit_code == 0
    assert "[workflow] Executed steps" in caplog.text
    overrides = captured.get("overrides")
    assert overrides is not None
    assert overrides["scenario"]["run_mode"] == "PF_THEN_RH"
    assert overrides["scenario"]["fix_design"] is False
    assert overrides["scenario"]["rolling_horizon"]["heat_horizon_hours"] == pytest.approx(24.0)
    assert overrides["rolling_horizon"]["heat_horizon_hours"] == pytest.approx(24.0)
    assert overrides["scenario"]["rolling_horizon"]["step_hours"] == pytest.approx(12.0)
    assert overrides["rolling_horizon"]["step_hours"] == pytest.approx(12.0)
    assert overrides["scenario"]["rolling_horizon"]["terminal_policy"] == "free"
    assert overrides["scenario"]["pf_design_json"] == "/tmp/cli_design.json"
    assert overrides["costs"]["include_gridcost_in_energy"] is True
    assert overrides["costs"]["include_demand_charge_in_rh"] is False
    assert overrides["costs"]["include_co2_cost_in_objective"] is True


def test_rh_costs_amortised_once(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["costs"] = {"amortise_investment_once_in_rh": True}
    config["scenario"] = {
        "workflow": ["RH"],
        "rolling_horizon": {"heat_horizon_hours": 2.0, "step_hours": 1.0},
    }

    table = _make_table(3)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    recorded_cost_flags = []

    def fake_solve(table_arg, cfg, dt_h, solver_name, **kwargs):
        window_idx = len(recorded_cost_flags)
        costs_cfg = cfg.get("costs", {})
        recorded_cost_flags.append(
            (
                costs_cfg.get("include_capex_costs"),
                costs_cfg.get("include_tie_breaker_costs"),
                costs_cfg.get("include_storage_installation_costs"),
            )
        )
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        base_cost = 100.0 + 10.0 * window_idx
        costs = {
            "objective.Grid_energy_cost_EUR": base_cost,
            "objective.Grid_sell_revenue_EUR": 0.0,
            "objective.Capex_cost_EUR": 200.0,
            "objective.Activation_cost_EUR": 50.0,
            "objective.Tie_breaker_cost_EUR": 1.0,
            "objective.Storage_installation_cost_EUR": 5.0,
            "objective.Period_fraction_of_year": 0.01,
        }
        summary = OrderedDict({"objective": OrderedDict()})
        return rh.ScenarioResult(table_arg, series, summary, costs, {"status": "ok"})

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    result = rh.run_workflow([], overrides=config)
    assert result.rh_result is not None
    aggregated = result.rh_result.costs

    assert recorded_cost_flags[0] == (True, True, True)
    assert recorded_cost_flags[1][0] is False
    assert aggregated["objective.Capex_cost_EUR"] == pytest.approx(200.0)
    assert aggregated["objective.Activation_cost_EUR"] == pytest.approx(50.0)
    assert aggregated["objective.Tie_breaker_cost_EUR"] == pytest.approx(1.0)
    assert aggregated["objective.Storage_installation_cost_EUR"] == pytest.approx(5.0)
    assert aggregated["objective.Grid_energy_cost_EUR"] == pytest.approx(225.0)
    assert aggregated["objective.Period_fraction_of_year"] == pytest.approx(0.02)
    assert aggregated["objective.OBJ_value_EUR"] == pytest.approx(481.0)


def test_rh_investment_opt_out(monkeypatch: pytest.MonkeyPatch, simple_config: dict) -> None:
    config = copy.deepcopy(simple_config)
    config["costs"] = {"include_investment_in_rh": False}
    config["scenario"] = {
        "workflow": ["RH"],
        "rolling_horizon": {"heat_horizon_hours": 2.0, "step_hours": 1.0},
    }

    table = _make_table(2)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    recorded_flags = []

    def fake_solve(table_arg, cfg, dt_h, solver_name, **kwargs):
        costs_cfg = cfg.get("costs", {})
        recorded_flags.append(costs_cfg.get("include_capex_costs"))
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        costs = {
            "objective.Grid_energy_cost_EUR": 10.0,
            "objective.Grid_sell_revenue_EUR": 0.0,
            "objective.Capex_cost_EUR": 100.0,
        }
        summary = OrderedDict({"objective": OrderedDict()})
        return rh.ScenarioResult(table_arg, series, summary, costs, {"status": "ok"})

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    result = rh.run_workflow([], overrides=config)
    assert result.rh_result is not None
    aggregated = result.rh_result.costs

    assert recorded_flags == [False, False]
    assert aggregated.get("objective.Capex_cost_EUR", 0.0) == pytest.approx(0.0)
    assert aggregated["objective.Grid_energy_cost_EUR"] == pytest.approx(15.0)
    assert aggregated["objective.OBJ_value_EUR"] == pytest.approx(15.0)

def test_run_workflow_uses_design_file(
    monkeypatch: pytest.MonkeyPatch, simple_config: dict, tmp_path: Path
) -> None:
    config = copy.deepcopy(simple_config)
    design_path = tmp_path / "pf_design.json"
    design_data = {
        "heat_pumps": {"HP1": {"capacity_mw": 7.5, "build_binary": 1.0}},
        "storage": {"capacity_mwh": 15.0, "power_mw": 6.0, "build_binary": 1.0},
    }
    design_path.write_text(json.dumps(design_data))

    config["scenario"] = {
        "run_mode": "RH_ONLY",
        "fix_design": True,
        "pf_design_json": str(design_path),
        "rolling_horizon": {"heat_horizon_hours": 4.0, "step_hours": 2.0, "terminal_policy": "hold"},
    }

    table = _make_table(4)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    def fake_solve(table_arg, cfg, dt_h, solver_name, **kwargs):
        hp_cfg = cfg["system"]["heat_pumps"][0]
        assert hp_cfg["max_th_mw"] == pytest.approx(7.5)
        assert hp_cfg["min_th_mw"] == pytest.approx(7.5)
        assert hp_cfg["investment"]["enabled"] is False
        storage_cfg = cfg["system"]["storage"]
        assert storage_cfg["max_energy_mwh"] == pytest.approx(15.0)
        assert storage_cfg["max_power_mw"] == pytest.approx(6.0)
        assert storage_cfg["investment"]["enabled"] is False
        series = OrderedDict({"TES_SOC_MWh": [0.0, 1.0, 2.0, 3.0]})
        summary = OrderedDict({"objective": OrderedDict()})
        costs = {"objective.OBJ_value_EUR": 0.0}
        solver = {"status": "ok"}
        return rh.ScenarioResult(table_arg, series, summary, costs, solver)

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    result = rh.run_workflow([], overrides=config)

    assert result.rh_result is not None
    assert result.design is not None
    assert result.design.heat_pumps["HP1"]["capacity_mw"] == pytest.approx(7.5)


def test_run_workflow_missing_design_file(
    monkeypatch: pytest.MonkeyPatch, simple_config: dict, caplog: pytest.LogCaptureFixture
) -> None:
    config = copy.deepcopy(simple_config)
    config["scenario"] = {
        "run_mode": "RH_ONLY",
        "fix_design": True,
        "pf_design_json": "nonexistent_design.json",
        "rolling_horizon": {"heat_horizon_hours": 2.0, "step_hours": 2.0},
    }

    table = _make_table(2)
    monkeypatch.setattr(_wf, "load_input_excel", lambda *args, **kwargs: table)

    def fake_solve(table_arg, cfg, dt_h, solver_name, **kwargs):
        series = OrderedDict({"TES_SOC_MWh": [0.0] * len(table_arg)})
        summary = OrderedDict({"objective": OrderedDict()})
        return rh.ScenarioResult(table_arg, series, summary, {}, {})

    monkeypatch.setattr(_wf, "_solve_scenario", fake_solve)
    monkeypatch.setattr(_rhe, "_solve_scenario", fake_solve)

    with caplog.at_level("WARNING"):
        result = rh.run_workflow([], overrides=config)

    assert result.rh_result is not None
    assert "design file" in caplog.text.lower()

