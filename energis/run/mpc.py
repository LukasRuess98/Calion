"""Model Predictive Control (MPC) with forecast updates.

This module implements MPC by running rolling horizon optimization
with periodically updated forecasts, simulating realistic operational
planning where new forecast information becomes available.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Set
from collections import OrderedDict

from energis.forecasting.base import ForecastGenerator
from energis.utils.timeseries import TimeSeriesTable
from energis.run.rolling_horizon import _slice_table

logger = logging.getLogger(__name__)


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

    # Recompute objective total from aggregated costs
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
