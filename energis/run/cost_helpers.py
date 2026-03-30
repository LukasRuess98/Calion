"""Cost aggregation utilities for rolling-horizon workflows.

Contains helpers for accumulating per-window costs, recomputing objective
totals, and applying cost-related configuration overrides to individual
RH/MPC windows.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping, MutableMapping, Set

from .types import _CostAggregationPlan


_INVESTMENT_KEYS = {
    "objective.Capex_cost_EUR",
    "objective.Activation_cost_EUR",
    "objective.Tie_breaker_cost_EUR",
    "objective.Storage_installation_cost_EUR",
}
_SKIP_KEYS = {"objective.OBJ_value_EUR", "objective.Objective_residual_EUR"}


def _accumulate_costs(
    target: Dict[str, float],
    window_costs: Mapping[str, Any],
    plan: _CostAggregationPlan,
    commit_fraction: float,
    window_idx: int,
    once_costs: Set[str],
) -> None:
    """Aggregate per-window costs while avoiding RH double-counting.

    Objective-related figures are scaled by the committed fraction of the
    window so overlap regions do not artificially inflate totals. Investment
    terms (CapEx, activation, tie-breaker, installation) are included once by
    default to mimic a single PF design phase; the behaviour can be
    controlled via :class:`_CostAggregationPlan`.
    """

    if commit_fraction <= 0:
        return

    include_investment = plan.investment_active(window_idx)

    for key, value in window_costs.items():
        if not (isinstance(value, (int, float)) and math.isfinite(value)):
            continue
        if key in _SKIP_KEYS:
            continue
        if key in _INVESTMENT_KEYS:
            if not include_investment:
                continue
            if plan.amortise_once and key in once_costs:
                continue
            once_costs.add(key)
            target[key] = float(target.get(key, 0.0) + float(value))
            continue
        scaled_value = float(value)
        if key.startswith("objective."):
            scaled_value *= commit_fraction
        target[key] = float(target.get(key, 0.0) + scaled_value)


def _recompute_objective_costs(costs: MutableMapping[str, float]) -> None:
    if not costs:
        return

    energy_cost = float(costs.get("objective.Grid_energy_cost_EUR", 0.0))
    energy_revenue = float(costs.get("objective.Grid_sell_revenue_EUR", 0.0))
    fuel_cost = float(costs.get("objective.Fuel_cost_EUR", 0.0))
    dump_cost = float(costs.get("objective.Dump_cost_EUR", 0.0))
    co2_cost = float(costs.get("objective.CO2_cost_EUR", 0.0))
    demand_cost = float(costs.get("objective.Demand_charge_cost_EUR", 0.0))
    capex_cost = float(costs.get("objective.Capex_cost_EUR", 0.0))
    activation_cost = float(costs.get("objective.Activation_cost_EUR", 0.0))
    tie_break_cost = float(costs.get("objective.Tie_breaker_cost_EUR", 0.0))
    install_cost = float(costs.get("objective.Storage_installation_cost_EUR", 0.0))

    net_cost = energy_cost - energy_revenue
    costs["objective.Grid_net_cost_EUR"] = net_cost

    objective_total = (
        net_cost
        + fuel_cost
        + dump_cost
        + co2_cost
        + demand_cost
        + capex_cost
        + activation_cost
        + tie_break_cost
        + install_cost
    )
    costs["objective.OBJ_value_EUR"] = objective_total
    costs["objective.Objective_residual_EUR"] = 0.0


def _apply_cost_overrides(cfg: MutableMapping[str, Any], plan: _CostAggregationPlan, window_idx: int) -> None:
    costs_cfg = cfg.setdefault("costs", {})
    include_investment = plan.investment_active(window_idx)
    if isinstance(costs_cfg, dict):
        costs_cfg["include_capex_costs"] = include_investment
        costs_cfg["include_activation_costs"] = include_investment and plan.include_activation
        costs_cfg["include_tie_breaker_costs"] = include_investment and plan.include_tie_breaker
        costs_cfg["include_storage_installation_costs"] = include_investment and plan.include_installation
