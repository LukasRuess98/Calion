"""Tests for calion.run.cost_helpers."""

import pytest

from calion.run.cost_helpers import (
    _accumulate_costs,
    _apply_cost_overrides,
    _recompute_objective_costs,
)
from calion.run.types import _CostAggregationPlan


def _make_plan(include_investment=True, amortise_once=True):
    return _CostAggregationPlan(
        include_investment=include_investment,
        amortise_once=amortise_once,
        include_tie_breaker=True,
        include_installation=True,
        include_activation=True,
    )


# ---------------------------------------------------------------------------
# _accumulate_costs
# ---------------------------------------------------------------------------

class TestAccumulateCosts:
    def test_basic_accumulation(self):
        target = {}
        costs = {"objective.Grid_energy_cost_EUR": 100.0, "objective.Fuel_cost_EUR": 50.0}
        _accumulate_costs(target, costs, _make_plan(), commit_fraction=1.0, window_idx=0, once_costs=set())
        assert target["objective.Grid_energy_cost_EUR"] == pytest.approx(100.0)
        assert target["objective.Fuel_cost_EUR"] == pytest.approx(50.0)

    def test_commit_fraction_scales_objective(self):
        target = {}
        costs = {"objective.Grid_energy_cost_EUR": 100.0}
        _accumulate_costs(target, costs, _make_plan(), commit_fraction=0.5, window_idx=0, once_costs=set())
        assert target["objective.Grid_energy_cost_EUR"] == pytest.approx(50.0)

    def test_non_objective_key_not_scaled(self):
        target = {}
        costs = {"kpi.some_metric": 200.0}
        _accumulate_costs(target, costs, _make_plan(), commit_fraction=0.5, window_idx=0, once_costs=set())
        assert target["kpi.some_metric"] == pytest.approx(200.0)

    def test_skip_keys_ignored(self):
        target = {}
        costs = {"objective.OBJ_value_EUR": 999.0, "objective.Fuel_cost_EUR": 10.0}
        _accumulate_costs(target, costs, _make_plan(), commit_fraction=1.0, window_idx=0, once_costs=set())
        assert "objective.OBJ_value_EUR" not in target
        assert "objective.Fuel_cost_EUR" in target

    def test_investment_excluded_later_windows(self):
        target = {}
        costs = {"objective.Capex_cost_EUR": 1000.0, "objective.Fuel_cost_EUR": 50.0}
        plan = _make_plan(include_investment=True, amortise_once=True)
        _accumulate_costs(target, costs, plan, commit_fraction=1.0, window_idx=1, once_costs=set())
        assert "objective.Capex_cost_EUR" not in target
        assert "objective.Fuel_cost_EUR" in target

    def test_investment_included_first_window(self):
        target = {}
        costs = {"objective.Capex_cost_EUR": 1000.0}
        plan = _make_plan(include_investment=True, amortise_once=True)
        _accumulate_costs(target, costs, plan, commit_fraction=1.0, window_idx=0, once_costs=set())
        assert target["objective.Capex_cost_EUR"] == pytest.approx(1000.0)

    def test_zero_commit_fraction_skips(self):
        target = {}
        costs = {"objective.Fuel_cost_EUR": 100.0}
        _accumulate_costs(target, costs, _make_plan(), commit_fraction=0.0, window_idx=0, once_costs=set())
        assert target == {}

    def test_non_numeric_values_skipped(self):
        target = {}
        costs = {"objective.Fuel_cost_EUR": "not_a_number", "kpi.x": 5.0}
        _accumulate_costs(target, costs, _make_plan(), commit_fraction=1.0, window_idx=0, once_costs=set())
        assert "objective.Fuel_cost_EUR" not in target
        assert target["kpi.x"] == pytest.approx(5.0)

    def test_once_costs_set_prevents_duplicates(self):
        target = {}
        once = set()
        costs = {"objective.Capex_cost_EUR": 500.0}
        plan = _make_plan(include_investment=True, amortise_once=True)
        _accumulate_costs(target, costs, plan, commit_fraction=1.0, window_idx=0, once_costs=once)
        _accumulate_costs(target, costs, plan, commit_fraction=1.0, window_idx=0, once_costs=once)
        # Second call is also window 0, but once_costs already has the key
        assert target["objective.Capex_cost_EUR"] == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# _recompute_objective_costs
# ---------------------------------------------------------------------------

class TestRecomputeObjectiveCosts:
    def test_computes_net_and_total(self):
        costs = {
            "objective.Grid_energy_cost_EUR": 100.0,
            "objective.Grid_sell_revenue_EUR": 20.0,
            "objective.Fuel_cost_EUR": 30.0,
            "objective.Dump_cost_EUR": 0.0,
            "objective.CO2_cost_EUR": 5.0,
            "objective.Demand_charge_cost_EUR": 0.0,
            "objective.Capex_cost_EUR": 200.0,
            "objective.Activation_cost_EUR": 10.0,
            "objective.Tie_breaker_cost_EUR": 1.0,
            "objective.Storage_installation_cost_EUR": 0.0,
        }
        _recompute_objective_costs(costs)
        assert costs["objective.Grid_net_cost_EUR"] == pytest.approx(80.0)
        expected_total = 80.0 + 30.0 + 5.0 + 200.0 + 10.0 + 1.0
        assert costs["objective.OBJ_value_EUR"] == pytest.approx(expected_total)
        assert costs["objective.Objective_residual_EUR"] == pytest.approx(0.0)

    def test_empty_costs_noop(self):
        costs = {}
        _recompute_objective_costs(costs)
        assert costs == {}


# ---------------------------------------------------------------------------
# _apply_cost_overrides
# ---------------------------------------------------------------------------

class TestApplyCostOverrides:
    def test_first_window_enables_capex(self):
        cfg = {}
        plan = _make_plan(include_investment=True, amortise_once=True)
        _apply_cost_overrides(cfg, plan, window_idx=0)
        assert cfg["costs"]["include_capex_costs"] is True

    def test_later_window_disables_capex(self):
        cfg = {}
        plan = _make_plan(include_investment=True, amortise_once=True)
        _apply_cost_overrides(cfg, plan, window_idx=1)
        assert cfg["costs"]["include_capex_costs"] is False
