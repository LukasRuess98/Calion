"""Model Predictive Control (MPC) with forecast updates.

This module implements MPC by running rolling horizon optimization
with periodically updated forecasts, simulating realistic operational
planning where new forecast information becomes available.

Key feature: MPC decisions are made on forecast data, but costs are
evaluated on actual historical data for fair comparison with PF.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Set, MutableMapping
from collections import OrderedDict

from energis.forecasting.base import ForecastGenerator
from energis.utils.timeseries import TimeSeriesTable
from energis.run.rolling_horizon import _slice_table

logger = logging.getLogger(__name__)


def _evaluate_costs_on_actual_data(
    series: OrderedDict[str, List[float]],
    actual_data: TimeSeriesTable,
    committed_indices: List[int],
    cfg: Dict[str, Any],
    dt_h: float,
) -> Dict[str, float]:
    """Evaluate MPC decisions on actual (not forecast) data.

    This is critical for fair comparison with PF: MPC makes decisions based
    on imperfect forecasts, but the true cost of those decisions must be
    calculated using actual prices and demand.

    Parameters
    ----------
    series:
        MPC decision time series (P_buy, P_sell, generator outputs, etc.)
    actual_data:
        The actual historical data with true prices
    committed_indices:
        Indices into actual_data for the committed steps
    cfg:
        Configuration dictionary (for cost parameters)
    dt_h:
        Time step in hours

    Returns
    -------
    Dictionary of evaluated costs on actual data
    """
    n = len(committed_indices)
    if n == 0:
        return {}

    # Extract actual prices for committed period
    actual_elec_prices = []
    actual_gas_prices = []
    actual_demand = []

    for idx in committed_indices:
        if idx < len(actual_data):
            actual_elec_prices.append(actual_data["price_elec_eur_mwh"][idx] if "price_elec_eur_mwh" in actual_data else 0.0)
            actual_gas_prices.append(actual_data["price_gas_eur_mwh"][idx] if "price_gas_eur_mwh" in actual_data else 0.0)
            actual_demand.append(actual_data["demand_mw"][idx] if "demand_mw" in actual_data else 0.0)

    # Get MPC decisions (truncate to committed length)
    p_buy = series.get("P_buy_MW", [0.0] * n)[:n]
    p_sell = series.get("P_sell_MW", [0.0] * n)[:n]

    # Calculate grid costs with actual prices
    grid_cfg = cfg.get("grid", {})
    energy_fee = float(grid_cfg.get("energy_fee_eur_per_mwh", 0.0))
    grid_fee = float(grid_cfg.get("gridcost_eur_per_mwh", 0.0))
    sell_price_base = float(grid_cfg.get("sell_price_eur_per_mwh", 0.0))

    energy_cost = 0.0
    energy_revenue = 0.0
    base_electricity_cost = 0.0
    energy_fee_cost = 0.0
    grid_fee_cost = 0.0

    for t in range(n):
        elec_price = actual_elec_prices[t] if t < len(actual_elec_prices) else 0.0
        buy_mw = p_buy[t] if t < len(p_buy) else 0.0
        sell_mw = p_sell[t] if t < len(p_sell) else 0.0

        # Buying electricity
        base_electricity_cost += buy_mw * elec_price * dt_h
        energy_fee_cost += buy_mw * energy_fee * dt_h
        grid_fee_cost += buy_mw * grid_fee * dt_h

        # Selling electricity
        sell_price = sell_price_base if sell_price_base > 0 else elec_price
        energy_revenue += sell_mw * sell_price * dt_h

    energy_cost = base_electricity_cost + energy_fee_cost + grid_fee_cost

    # Calculate fuel costs with actual gas prices
    fuel_cost = 0.0
    # Find all generator fuel series
    for key, values in series.items():
        if key.endswith("_fuel_MW"):
            for t in range(min(n, len(values))):
                gas_price = actual_gas_prices[t] if t < len(actual_gas_prices) else 0.0
                fuel_cost += values[t] * gas_price * dt_h

    # Demand charge (peak power)
    demand_charge_rate = float(grid_cfg.get("demand_charge_eur_per_mw_year", 0.0))
    from energis.constants import HOURS_PER_YEAR
    period_fraction = float(n * dt_h / HOURS_PER_YEAR) if n > 0 else 0.0
    demand_year_fraction = float(grid_cfg.get("year_fraction", period_fraction))
    peak_power = max(p_buy) if p_buy else 0.0
    demand_cost = demand_charge_rate * demand_year_fraction * peak_power

    # CO2 costs - based on fuel consumption (emission factors from config)
    costs_cfg = cfg.get("costs", {})
    co2_price = float(costs_cfg.get("co2_price_eur_per_t", 0.0))
    fuels_cfg = cfg.get("fuels", {})

    co2_emissions_kg = 0.0
    for key, values in series.items():
        if key.endswith("_fuel_MW"):
            # Get emission factor for this fuel type (default: gas)
            gas_emissions = float(fuels_cfg.get("gas", {}).get("co2_kg_per_mwh", 200.0))
            for t in range(min(n, len(values))):
                co2_emissions_kg += values[t] * gas_emissions * dt_h

    co2_cost = co2_emissions_kg / 1000.0 * co2_price  # Convert kg to tonnes

    # Dump costs (heat dumping penalty)
    dump_series = series.get("Q_dump_MWth", [0.0] * n)[:n]
    dump_price = float(costs_cfg.get("dump_price_eur_per_mwh", 100.0))
    dump_cost = sum(dump_series) * dump_price * dt_h

    # Build evaluated costs dict
    evaluated_costs = {
        "objective.Grid_energy_cost_EUR": energy_cost,
        "objective.Electricity_base_cost_EUR": base_electricity_cost,
        "objective.Electricity_energy_fee_EUR": energy_fee_cost,
        "objective.Electricity_grid_fee_EUR": grid_fee_cost,
        "objective.Grid_sell_revenue_EUR": energy_revenue,
        "objective.Grid_net_cost_EUR": energy_cost - energy_revenue,
        "objective.Fuel_cost_EUR": fuel_cost,
        "objective.Demand_charge_cost_EUR": demand_cost,
        "objective.CO2_cost_EUR": co2_cost,
        "objective.Dump_cost_EUR": dump_cost,
    }

    return evaluated_costs


def run_mpc(
    base_cfg: Dict[str, Any],
    historical_data: TimeSeriesTable,
    dt_h: float,
    solver_name: str,
    forecast_gen: ForecastGenerator,
    forecast_horizon_hours: float,
    update_frequency_hours: float,
    design: Optional[Any],
    fix_design: bool,
):
    """Run Model Predictive Control with forecast updates.

    Key difference from standard RH: At each step, we regenerate the forecast
    using the forecast_gen instead of using a static slice of historical_data.

    Parameters
    ----------
    base_cfg:
        Configuration dictionary
    historical_data:
        Full historical data (used to generate forecasts)
    dt_h:
        Time step in hours
    solver_name:
        Solver to use (e.g., 'gurobi', 'glpk')
    forecast_gen:
        Forecast generator instance
    forecast_horizon_hours:
        Forecast horizon in hours (e.g., 168h = 1 week)
    update_frequency_hours:
        How often to update forecast (e.g., 24h = daily)
    design:
        Optional pre-computed design to fix
    fix_design:
        Whether to fix the design

    Returns
    -------
    Aggregated MPC result
    """
    # Import here to avoid circular dependency
    from energis.run.rolling_horizon import (
        RollingHorizonResult,
        WindowResult,
        _hours_to_steps,
        _initial_soc,
        _storage_enabled,
        _apply_terminal_policy,
        _set_initial_soc,
        _apply_design_fix,
        _solve_scenario,
        _load_cost_plan,
        _extract_design_data,
        _accumulate_costs,
        _extend_series,
        _next_soc,
        _recompute_objective_costs,
    )

    n = len(historical_data)
    if n == 0:
        empty_series: OrderedDict[str, List[float]] = OrderedDict()
        return RollingHorizonResult(historical_data, empty_series, {}, [], design)

    # Calculate step sizes
    horizon_steps = _hours_to_steps(forecast_horizon_hours, dt_h, "MPC_HORIZON")
    update_steps = _hours_to_steps(update_frequency_hours, dt_h, "MPC_UPDATE")

    if update_steps > horizon_steps:
        raise ValueError("MPC update frequency must not exceed forecast horizon")

    # Initialize aggregation
    aggregated_indices: List[int] = []
    aggregated_series: OrderedDict[str, List[float]] = OrderedDict()
    aggregated_costs: Dict[str, float] = {}
    windows: List[WindowResult] = []

    design_state = design
    cost_plan = _load_cost_plan(base_cfg, fix_design)
    once_costs: Set[str] = set()

    soc_next = _initial_soc(base_cfg)
    base_storage_enabled = _storage_enabled(base_cfg)

    # Get terminal policy
    terminal_policy = base_cfg.get("scenario", {}).get("rolling_horizon", {}).get("terminal_policy", "free")

    # MPC main loop: update forecast at each step
    current_index = 0
    window_idx = 0

    logger.info(
        f"Starting MPC: forecast={forecast_gen.get_method_name()}, "
        f"horizon={forecast_horizon_hours}h, update_freq={update_frequency_hours}h, n={n} steps"
    )

    while current_index < n:
        logger.debug(f"MPC window {window_idx}: index={current_index}/{n}")

        # 1. Generate forecast from current position
        forecast_table = forecast_gen.generate_forecast(
            historical_data=historical_data,
            current_index=current_index,
            horizon_hours=forecast_horizon_hours,
            dt_h=dt_h,
        )

        # 2. Prepare window configuration
        window_cfg = copy.deepcopy(base_cfg)

        # Apply terminal policy
        if terminal_policy:
            _apply_terminal_policy(window_cfg, terminal_policy)

        # Set initial SOC from previous window
        if soc_next is not None and base_storage_enabled:
            _set_initial_soc(window_cfg, soc_next)

        # Fix design if requested
        should_fix_design = bool(
            design_state is not None and (fix_design or (design is None and window_idx > 0))
        )
        if should_fix_design:
            window_cfg = _apply_design_fix(window_cfg, design_state)

        # 3. Solve optimization with forecast
        window_result = _solve_scenario(
            forecast_table,
            window_cfg,
            dt_h,
            solver_name,
        )

        # 4. Extract design from first window (if not fixed)
        if window_idx == 0 and design_state is None:
            design_state = _extract_design_data(window_result.summary)

        # 5. Determine committed portion (first update_steps)
        commit_steps = min(update_steps, len(forecast_table), n - current_index)
        committed_indices = list(range(current_index, current_index + commit_steps))

        # Store window result
        window_res = WindowResult(
            table=forecast_table,
            series=window_result.series,
            summary=window_result.summary,
            costs=window_result.costs,
            solver=window_result.solver,
            start_index=current_index,
            commit_steps=commit_steps,
        )
        windows.append(window_res)

        # 6. Aggregate committed portion
        _extend_series(aggregated_series, window_result.series, commit_steps)
        aggregated_indices.extend(committed_indices)

        # 7. Aggregate costs (using RH cost aggregation logic)
        commit_fraction = commit_steps / len(forecast_table) if len(forecast_table) > 0 else 1.0
        _accumulate_costs(
            aggregated_costs,
            window_result.costs,
            cost_plan,
            commit_fraction,
            window_idx,
            once_costs,
        )

        # 8. Extract final SOC for next window
        soc_next = _next_soc(window_result.series, commit_steps, soc_next)

        # 9. Advance to next update
        current_index += commit_steps
        window_idx += 1

        if commit_steps == 0:
            logger.warning(f"MPC stuck at index {current_index}, breaking")
            break

    logger.info(f"MPC completed: {window_idx} windows, {len(aggregated_indices)} committed steps")

    # =========================================================================
    # CRITICAL: Evaluate costs on ACTUAL data, not forecast data
    # =========================================================================
    # MPC decisions are made on imperfect forecasts, but true costs must be
    # calculated using actual prices for fair comparison with PF.
    # =========================================================================
    evaluated_costs = _evaluate_costs_on_actual_data(
        series=aggregated_series,
        actual_data=historical_data,
        committed_indices=aggregated_indices,
        cfg=base_cfg,
        dt_h=dt_h,
    )

    # Replace forecast-based costs with actual-data costs
    # Keep investment costs (CAPEX) from aggregation - they don't depend on prices
    for key, value in evaluated_costs.items():
        aggregated_costs[key] = value
        logger.debug(f"Replaced {key}: {value:.2f}")

    logger.info(
        f"MPC costs re-evaluated on actual data: "
        f"Grid={evaluated_costs.get('objective.Grid_energy_cost_EUR', 0):,.0f} EUR, "
        f"Fuel={evaluated_costs.get('objective.Fuel_cost_EUR', 0):,.0f} EUR"
    )

    # Recompute objective total from actual-data costs
    _recompute_objective_costs(aggregated_costs)

    # Build final result
    result_table = _slice_table(historical_data, aggregated_indices)

    return RollingHorizonResult(
        table=result_table,
        series=aggregated_series,
        costs=aggregated_costs,
        windows=windows,
        design=design_state,
    )
