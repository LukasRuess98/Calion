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

from calion.forecasting.base import ForecastGenerator
from calion.utils.timeseries import TimeSeriesTable
from calion.run.utilities import _slice_table

from calion.logging_config import get_logger

logger = get_logger(__name__)

logger = logging.getLogger(__name__)


def _evaluate_costs_on_actual_data(
    series: OrderedDict[str, List[float]],
    actual_data: TimeSeriesTable,
    committed_indices: List[int],
    cfg: Dict[str, Any],
    dt_h: float,
) -> Dict[str, float]:
    """Evaluate MPC decisions on actual (not forecast) data.

    This function recalculates ALL operational costs using actual historical
    prices instead of forecast prices. This is critical for fair comparison
    with PF: MPC makes decisions based on imperfect forecasts, but the true
    cost of those decisions must be calculated using actual prices.

    The calculation mirrors _collect_timeseries_and_summary() from PF to ensure
    identical cost computation methodology.

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
    from calion.constants import HOURS_PER_YEAR
    from calion.run.result_collector import _gather_component_metadata

    n = len(committed_indices)
    if n == 0:
        return {}

    # Get component metadata using same function as PF
    meta = _gather_component_metadata(cfg)

    # DEBUG: Show generator metadata
    logger.info(f"\n[MPC DEBUG] Generator metadata from _gather_component_metadata:")
    for gen in meta["generators"]:
        logger.info(f"  {gen['name']}: fuel_bus={gen['fuel_bus']}, price={gen['fuel_price']:.2f}€/MWh, emission={gen['fuel_emission']:.1f}kg/MWh")

    # =========================================================================
    # 1. EXTRACT ACTUAL DATA FOR COMMITTED PERIOD
    # =========================================================================
    # Use same column name as PF: strompreis_EUR_MWh
    price_series = actual_data.data.get("strompreis_EUR_MWh", [0.0] * len(actual_data))
    grid_co2_series = actual_data.data.get("grid_co2_kg_MWh", [0.0] * len(actual_data))

    # DEBUG: Show data availability
    logger.info(f"[MPC DEBUG] Actual data columns: {list(actual_data.data.keys())[:10]}...")
    logger.info(f"[MPC DEBUG] Price series length: {len(price_series)}, first 3 values: {price_series[:3]}")
    logger.info(f"[MPC DEBUG] Committed indices: n={n}, range=[{committed_indices[0] if committed_indices else 'N/A'}..{committed_indices[-1] if committed_indices else 'N/A'}]")

    # Extract prices for committed indices
    actual_elec_prices = []
    actual_grid_co2 = []
    for idx in committed_indices:
        if idx < len(price_series):
            actual_elec_prices.append(float(price_series[idx]))
        else:
            actual_elec_prices.append(0.0)
        if idx < len(grid_co2_series):
            actual_grid_co2.append(float(grid_co2_series[idx]))
        else:
            actual_grid_co2.append(0.0)

    # =========================================================================
    # 2. GET MPC DECISIONS (time series from optimization)
    # =========================================================================
    p_buy = series.get("P_buy_MW", [0.0] * n)[:n]
    p_sell = series.get("P_sell_MW", [0.0] * n)[:n]
    q_dump = series.get("Q_dump_MWth", [0.0] * n)[:n]

    # DEBUG: Show series values
    logger.info(f"[MPC DEBUG] Series keys: {list(series.keys())[:15]}...")
    logger.info(f"[MPC DEBUG] P_buy_MW: len={len(p_buy)}, sum={sum(p_buy):.1f}, max={max(p_buy) if p_buy else 0:.1f}")
    logger.info(f"[MPC DEBUG] P_sell_MW: len={len(p_sell)}, sum={sum(p_sell):.1f}")

    # Check fuel series
    for gen in meta["generators"]:
        fuel_key = f"{gen['name']}_fuel_MW"
        if fuel_key in series:
            fuel_vals = series[fuel_key][:n]
            logger.info(f"[MPC DEBUG] {fuel_key}: sum={sum(fuel_vals):.1f} MW")
        else:
            logger.info(f"[MPC DEBUG] {fuel_key}: NOT FOUND in series!")

    # =========================================================================
    # 3. GRID ELECTRICITY COSTS (identical to PF calculation)
    # =========================================================================
    grid_cfg = cfg.get("grid", {})
    costs_cfg = cfg.get("costs", {})

    # Fee and grid cost parameters - USE SAME KEYS AS PF!
    energy_fee = float(grid_cfg.get("energy_fee_eur_mwh", 0.0))
    grid_cost = float(grid_cfg.get("gridcost_eur_mwh", 0.0))

    # Sell price calculation parameters (same as PF)
    sell_floor = float(grid_cfg.get("sell_floor_eur_mwh", 0.0))
    sell_haircut = float(grid_cfg.get("sell_haircut_fraction", 0.0))
    sell_spread = float(grid_cfg.get("sell_spread_eur_mwh", 0.0))
    sell_fee = float(grid_cfg.get("sell_fee_eur_mwh", 0.0))
    sell_premium = float(grid_cfg.get("sell_premium_eur_mwh", 0.0))

    def _sell_price(base: float) -> float:
        """Calculate sell price same as PF."""
        price = max(base - sell_spread, sell_floor)
        price = price * max(0.0, 1.0 - sell_haircut)
        price = price - sell_fee + sell_premium
        return max(price, 0.0)

    # Include flags - USE SAME KEY AS PF!
    include_gridcost = bool(costs_cfg.get("include_gridcost_in_energy", False))
    addition = (energy_fee + grid_cost) if include_gridcost else 0.0

    # Calculate costs timestep by timestep (identical to PF)
    base_electricity_cost = 0.0
    energy_cost = 0.0
    energy_revenue = 0.0

    for t in range(n):
        elec_price = actual_elec_prices[t] if t < len(actual_elec_prices) else 0.0
        buy_mw = p_buy[t] if t < len(p_buy) else 0.0
        sell_mw = p_sell[t] if t < len(p_sell) else 0.0

        # Buy price includes fees (same as PF line 801)
        buy_price = elec_price + addition
        base_electricity_cost += buy_mw * elec_price * dt_h
        energy_cost += buy_mw * buy_price * dt_h

        # Sell price calculation (same as PF line 802)
        sell_price = _sell_price(elec_price)
        energy_revenue += sell_mw * sell_price * dt_h

    # Calculate energy totals
    energy_in = float(sum(p_buy) * dt_h)
    energy_out = float(sum(p_sell) * dt_h)

    # Fee breakdown (same as PF lines 810-811)
    energy_fee_cost = float(energy_in * energy_fee)
    grid_fee_cost = float(energy_in * grid_cost)

    # =========================================================================
    # 4. GRID CO2 EMISSIONS (same as PF line 815)
    # =========================================================================
    grid_co2_t = 0.0
    for t in range(n):
        buy_mw = p_buy[t] if t < len(p_buy) else 0.0
        co2_factor = actual_grid_co2[t] if t < len(actual_grid_co2) else 0.0
        grid_co2_t += buy_mw * co2_factor * dt_h / 1000.0  # kg to tonnes

    # =========================================================================
    # 5. FUEL COSTS (using _gather_component_metadata - same as PF)
    # =========================================================================
    fuel_cost_total = 0.0
    fuel_emissions_t = 0.0
    fuel_cost_by_type: Dict[str, float] = {}

    # Use generator metadata from _gather_component_metadata (same as PF lines 983-1024)
    for gen in meta["generators"]:
        comp = gen["name"]  # UPPERCASE name (e.g., "HKW")

        # Find the fuel series for this generator - UPPERCASE!
        fuel_key = f"{comp}_fuel_MW"
        if fuel_key not in series:
            logger.debug(f"MPC: No fuel series found for {fuel_key}")
            continue

        fuel_series = series[fuel_key][:n]
        fuel_mwh = float(sum(fuel_series) * dt_h)

        # Use fuel_price and fuel_emission from metadata (same as PF lines 990-991)
        cost_eur = float(fuel_mwh * gen["fuel_price"])
        emission_t = float(fuel_mwh * gen["fuel_emission"] / 1000.0)  # kg to tonnes

        fuel_cost_total += cost_eur
        fuel_emissions_t += emission_t

        # Track by fuel type (same as PF lines 993-997)
        fuel_bus = gen["fuel_bus"]
        fuel_cost_by_type[fuel_bus] = fuel_cost_by_type.get(fuel_bus, 0.0) + cost_eur

        logger.debug(
            f"MPC gen {comp}: fuel={fuel_mwh:.1f}MWh, price={gen['fuel_price']:.2f}€/MWh, "
            f"cost={cost_eur:.0f}€, emissions={emission_t:.1f}t"
        )

    # =========================================================================
    # 6. CO2 COSTS (same as PF lines 1105-1107)
    # =========================================================================
    include_co2 = bool(costs_cfg.get("include_co2_cost_in_objective", True))
    co2_price = float(costs_cfg.get("co2_price_eur_per_t", 0.0))
    total_emissions_t = float(grid_co2_t + fuel_emissions_t)
    co2_cost = float(co2_price * total_emissions_t) if include_co2 else 0.0

    # =========================================================================
    # 7. DUMP COSTS (same as PF line 1108)
    # =========================================================================
    dump_cost_rate = float(costs_cfg.get("dump_cost_eur_per_mwh_th", 0.0))
    heat_dump = float(sum(q_dump) * dt_h)
    dump_cost = float(dump_cost_rate * heat_dump)

    # =========================================================================
    # 8. DEMAND CHARGE (same as PF lines 1110-1117)
    # =========================================================================
    # Use same keys as PF!
    include_demand = bool(grid_cfg.get(
        "include_demand_charge_in_rh",
        costs_cfg.get("include_demand_charge_in_rh", True)
    ))
    demand_charge_rate = float(grid_cfg.get("demand_charge_eur_per_mw_y", 0.0))

    # Year fraction calculation (same as PF lines 441-442)
    from calion.constants import HOURS_PER_YEAR
    period_fraction = float(n * dt_h / HOURS_PER_YEAR) if n > 0 else 0.0
    demand_year_fraction = float(grid_cfg.get("year_fraction", period_fraction))

    peak_power = float(max(p_buy)) if p_buy else 0.0
    demand_cost = float(demand_charge_rate * demand_year_fraction * peak_power) if include_demand else 0.0

    # =========================================================================
    # 9. BUILD EVALUATED COSTS DICTIONARY
    # =========================================================================
    evaluated_costs = {
        # Grid electricity
        "objective.Grid_energy_cost_EUR": energy_cost,
        "objective.Electricity_base_cost_EUR": base_electricity_cost,
        "objective.Electricity_energy_fee_EUR": energy_fee_cost,
        "objective.Electricity_grid_fee_EUR": grid_fee_cost,
        "objective.Grid_sell_revenue_EUR": energy_revenue,
        "objective.Grid_net_cost_EUR": energy_cost - energy_revenue,

        # Fuel
        "objective.Fuel_cost_EUR": fuel_cost_total,
        "objective.Fuel_emissions_t": fuel_emissions_t,

        # CO2 (includes both grid and fuel)
        "objective.CO2_cost_EUR": co2_cost,
        "objective.Grid_CO2_emissions_t": grid_co2_t,
        "objective.Total_CO2_emissions_t": total_emissions_t,

        # Dump and demand
        "objective.Dump_cost_EUR": dump_cost,
        "objective.Demand_charge_cost_EUR": demand_cost,
        "objective.P_buy_peak_MW": peak_power,

        # Period info
        "objective.Period_fraction_of_year": period_fraction,
        "objective.Demand_charge_year_fraction": demand_year_fraction,
    }

    # Add fuel costs by type
    for fuel_type, cost in fuel_cost_by_type.items():
        evaluated_costs[f"objective.Fuel_cost_{fuel_type}_EUR"] = cost

    logger.info(
        f"MPC actual-data costs: Grid={energy_cost:,.0f}€, Fuel={fuel_cost_total:,.0f}€, "
        f"CO2={co2_cost:,.0f}€ (Grid:{grid_co2_t:.1f}t + Fuel:{fuel_emissions_t:.1f}t), "
        f"Dump={dump_cost:,.0f}€, Demand={demand_cost:,.0f}€"
    )

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
    from calion.run.types import RollingHorizonResult, WindowResult
    from calion.run.utilities import _hours_to_steps
    from calion.run.rh_engine import (
        _initial_soc,
        _storage_enabled,
        _apply_terminal_policy,
        _set_initial_soc,
        _extend_series,
        _next_soc,
        _load_cost_plan,
    )
    from calion.run.design_helpers import _apply_design_fix, _extract_design_data
    from calion.run.solver import _solve_scenario
    from calion.run.cost_helpers import _accumulate_costs, _recompute_objective_costs

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

    # ✅ FIX: Relax terminal policy for MPC (avoid infeasibility)
    terminal_policy = base_cfg.get("scenario", {}).get("rolling_horizon", {}).get("terminal_policy", "free")
    if terminal_policy == "equal":
        logger.warning("[MPC] Relaxing terminal_policy from 'equal' to 'geq' to avoid infeasibility")
        terminal_policy = "geq"  # Less restrictive
    elif not terminal_policy:
        terminal_policy = "free"  # Most permissive

    # MPC main loop: update forecast at each step
    current_index = 0
    window_idx = 0

    logger.info(
        f"Starting MPC: forecast={forecast_gen.get_method_name()}, "
        f"horizon={forecast_horizon_hours}h, update_freq={update_frequency_hours}h, n={n} steps, "
        f"terminal_policy='{terminal_policy}'"
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

        # Debug: show forecast data for first window
        if window_idx == 0:
            logger.info(f"\n[MPC DEBUG] First window forecast data:")
            logger.info(f"  - Length: {len(forecast_table)} steps")
            logger.info(f"  - Columns: {list(forecast_table.data.keys())[:8]}...")
            if "waermebedarf_MWth" in forecast_table.data:
                demand = forecast_table.data["waermebedarf_MWth"]
                logger.info(f"  - Heat demand: min={min(demand):.1f}, max={max(demand):.1f}, avg={sum(demand)/len(demand):.1f} MWth")

            # Show generator capacities
            gen_cfg = base_cfg.get("system", {}).get("generators", {})
            total_cap = 0.0
            logger.info(f"[MPC DEBUG] Generator capacities:")
            for name, cfg_val in gen_cfg.items():
                if isinstance(cfg_val, dict) and cfg_val.get("enabled", False):
                    cap = float(cfg_val.get("cap_th_mw", 0.0))
                    total_cap += cap
                    logger.info(f"  - {name}: {cap:.1f} MWth")
            logger.info(f"  - TOTAL generators: {total_cap:.1f} MWth")

            # Show heat pump capacities
            hp_cfg = base_cfg.get("system", {}).get("heat_pumps", [])
            hp_cap = 0.0
            if isinstance(hp_cfg, list):
                for hp in hp_cfg:
                    if isinstance(hp, dict) and hp.get("enabled", True):
                        cap = float(hp.get("max_th_mw", 0.0))
                        hp_cap += cap
                        logger.info(f"  - {hp.get('id', 'HP')}: {cap:.1f} MWth")
            logger.info(f"  - TOTAL heat pumps: {hp_cap:.1f} MWth")
            logger.info(f"  - GRAND TOTAL: {total_cap + hp_cap:.1f} MWth")

            if "waermebedarf_MWth" in forecast_table.data:
                peak = max(demand)
                total_available = total_cap + hp_cap
                logger.info(f"  - Peak demand: {peak:.1f} MWth {'(OK)' if total_available >= peak else '(INSUFFICIENT!)'}")

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
            # Debug: show design being applied
            if window_idx == 0:
                logger.info(f"\n[MPC DEBUG] Applying design fix from PF:")
                if design_state:
                    logger.info(f"  Heat Pumps:")
                    for hp_id, hp_data in design_state.heat_pumps.items():
                        logger.info(f"    {hp_id}: capacity={hp_data.get('capacity_mw', 0):.2f} MW, build={hp_data.get('build_binary', 0):.2f}")
                    if design_state.storage:
                        logger.info(
                            "  Storage: capacity=%.1f MWh, power=%.1f MW, build=%.2f",
                            design_state.storage.get("capacity_mwh", 0),
                            design_state.storage.get("power_mw", 0),
                            design_state.storage.get("build_binary", 0),
                        )
                    else:
                        logger.info(f"  Storage: None")
            window_cfg = _apply_design_fix(window_cfg, design_state)

        # 3. Solve optimization with forecast
        window_result = _solve_scenario(
            forecast_table,
            window_cfg,
            dt_h,
            solver_name,
        )

        # ✅ FIX #2: Stop MPC on infeasibility (don't continue with zero costs)
        term_cond = str(window_result.solver.get("termination_condition", "")).lower()
        if "infeasible" in term_cond or "unbounded" in term_cond:
            logger.error(
                f"MPC Window {window_idx} (index={current_index}) is {term_cond}. "
                f"Stopping optimization. Check: heat demand vs capacity, "
                f"storage constraints, terminal_policy='{terminal_policy}'."
            )
            raise RuntimeError(
                f"MPC optimization failed at window {window_idx}: {term_cond}. "
                f"Hints:\n"
                f"  - Relax terminal_policy (try 'free' or 'geq' instead of 'equal')\n"
                f"  - Check if peak demand exceeds available capacity\n"
                f"  - Verify storage bounds and initial SOC\n"
                f"  - Increase forecast horizon or reduce update frequency"
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

        # 6. Aggregate committed portion of time series
        _extend_series(aggregated_series, window_result.series, commit_steps)
        aggregated_indices.extend(committed_indices)

        # 7. Aggregate costs (using RH cost aggregation logic)
        # Note: These are forecast-based costs, will be replaced with actual-data costs later
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
    # Kosten auf Basis der REALEN Daten (historical_data) auswerten
    # =========================================================================
    # Falls aus irgendeinem Grund keine Schritte committet wurden, brechen wir
    # sauber ab und geben nur CAPEX zurück.
    if not aggregated_indices:
        evaluated_costs: Dict[str, float] = {}
    else:
        evaluated_costs: Dict[str, float] = _evaluate_costs_on_actual_data(
            series=aggregated_series,
            actual_data=historical_data,
            committed_indices=aggregated_indices,
            cfg=base_cfg,
            dt_h=dt_h,
        )

    # Debug-Ausgabe (optional)
    logger.info(f"\n[MPC DEBUG] Evaluated costs from actual data:")
    for k, v in sorted(evaluated_costs.items()):
        if abs(v) > 0.01:
            logger.info(f"  {k}: {v:,.2f}")

    # OPEX durch tatsächliche Kosten ersetzen, CAPEX aus Aggregation beibehalten
    for key, value in evaluated_costs.items():
        aggregated_costs[key] = value

    # Gesamtes Ziel neu berechnen (OPEX + CAPEX)
    _recompute_objective_costs(aggregated_costs)

    logger.info(f"\n[MPC DEBUG] Final costs AFTER recompute:")
    for k, v in sorted(aggregated_costs.items()):
        if "objective" in k.lower() and abs(v) > 0.01:
            logger.info(f"  {k}: {v:,.2f}")

    # Finale Ergebnis-Tabelle: echte Zeitschiene, nur die committeten Indizes
    result_table = _slice_table(historical_data, aggregated_indices)

    return RollingHorizonResult(
        table=result_table,
        series=aggregated_series,
        costs=aggregated_costs,
        windows=windows,
        design=design_state,
    )
