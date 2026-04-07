"""Rolling-horizon loop engine.

Contains the main ``_run_rolling_horizon`` iteration together with the helpers
that manage SOC hand-over, terminal policies, rolling parameters, and cost
plan loading.
"""

from __future__ import annotations

import copy
from collections import OrderedDict
from collections.abc import Mapping, MutableMapping
from typing import Any

from calion.constants import DEFAULT_HORIZON_HOURS
from calion.design import (
    DesignSpec,
    OptimizationConfig,
    apply_design_to_config,
    convert_to_design_spec,
    extract_optimization_results,
    validate_design,
)
from calion.logging_config import get_logger
from calion.models.results import InvestmentDecisions
from calion.utils.timeseries import TimeSeriesTable

from .cost_helpers import _accumulate_costs, _apply_cost_overrides, _recompute_objective_costs
from .design_helpers import _apply_design_fix, _extract_design_data
from .solver import _solve_scenario
from .types import (
    DesignData,
    RollingHorizonResult,
    WindowResult,
    _CostAggregationPlan,
    _RollingParams,
)
from .utilities.timeseries_utils import _slice_table

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# SOC / terminal helpers
# ---------------------------------------------------------------------------

def _initial_soc(cfg: Mapping[str, Any]) -> float | None:
    # Legacy path: system.storage
    system = cfg.get("system", {}) if isinstance(cfg.get("system"), dict) else {}
    storage = system.get("storage", {}) if isinstance(system.get("storage"), dict) else {}
    if storage and storage.get("enabled", False):
        inputs = cfg.get("inputs", {}) if isinstance(cfg.get("inputs"), dict) else {}
        if "SOC_init" in inputs:
            return float(inputs["SOC_init"])
        if "SOC_init" in storage:
            return float(storage["SOC_init"])
        if "soc0_mwh" in storage:
            return float(storage["soc0_mwh"])
        return 0.0
    # Unified path: assets with type=storage
    assets = cfg.get("assets", {}) if isinstance(cfg.get("assets"), dict) else {}
    for asset_cfg in assets.values():
        if isinstance(asset_cfg, dict) and asset_cfg.get("type") == "storage":
            return float(asset_cfg.get("soc0_mwh", 0.0))
    return None


def _storage_enabled(cfg: Mapping[str, Any]) -> bool:
    # Legacy path: system.storage.enabled
    system = cfg.get("system", {}) if isinstance(cfg.get("system"), dict) else {}
    storage = system.get("storage", {}) if isinstance(system.get("storage"), dict) else {}
    if storage.get("enabled", False):
        return True
    # Unified path: any asset with type=storage
    assets = cfg.get("assets", {}) if isinstance(cfg.get("assets"), dict) else {}
    return any(
        isinstance(a, dict) and a.get("type") == "storage"
        for a in assets.values()
    )


def _set_initial_soc(cfg: MutableMapping[str, Any], soc: float) -> MutableMapping[str, Any]:
    """Set initial SOC for next RH window in all relevant config locations.

    Mutates *cfg* in place **and** returns it for chaining.  Callers should
    always pass a deep-copied config to avoid unintended side-effects on
    the base configuration.
    """
    logger.info("[RH] _set_initial_soc: Setting initial SOC for next window")
    logger.info(f"  - soc0_mwh: {soc} MWh")

    inputs = cfg.setdefault("inputs", {})
    if isinstance(inputs, dict):
        inputs["SOC_init"] = float(soc)

    system = cfg.setdefault("system", {})
    if isinstance(system, dict):
        storage = system.setdefault("storage", {})
        if isinstance(storage, dict):
            storage["soc0_mwh"] = float(soc)
            # Note: terminal.target_mwh is NOT set here — that is managed
            # by _apply_terminal_policy to avoid overriding the policy.

    root_storage = cfg.get("storage")
    if isinstance(root_storage, dict):
        root_storage["soc0_mwh"] = float(soc)

    # Unified path: propagate to assets with type=storage
    assets = cfg.get("assets", {})
    if isinstance(assets, dict):
        for asset_cfg in assets.values():
            if isinstance(asset_cfg, dict) and asset_cfg.get("type") == "storage":
                asset_cfg["soc0_mwh"] = float(soc)

    return cfg


def _apply_terminal_policy(cfg: MutableMapping[str, Any], policy: str) -> MutableMapping[str, Any]:
    """Set terminal policy for storage in RH/MPC windows.

    Mutates *cfg* in place **and** returns it for chaining.  Callers should
    always pass a deep-copied config.
    """
    if not policy:
        return cfg
    system = cfg.setdefault("system", {})
    if not isinstance(system, dict):
        return cfg
    storage = system.setdefault("storage", {})
    if not isinstance(storage, dict):
        return cfg
    terminal = storage.setdefault("terminal", {})
    if isinstance(terminal, dict):
        terminal["policy"] = policy

        if policy in ("free", "value"):
            terminal["state"] = "free"
            terminal.pop("target_mwh", None)
            terminal.pop("target", None)
            storage.pop("terminal_soc_mwh", None)
            storage["terminal_state"] = "free"
            logger.info(f"[TERMINAL] Set to '{policy}' (state=free, no target)")
        elif policy in ("equal", "geq", "soft"):
            terminal["state"] = "cyclic"
            logger.info(f"[TERMINAL] Set to '{policy}' (state=cyclic)")

    return cfg


def _next_soc(series: Mapping[str, list[float]], commit_len: int, fallback: float | None) -> float | None:
    soc_series = series.get("TES_SOC_MWh")
    if soc_series is None or commit_len <= 0:
        logger.info(f"[RH] _next_soc: No SOC series or invalid commit_len, using fallback={fallback}")
        return fallback
    idx = min(commit_len - 1, len(soc_series) - 1)
    soc_value = float(soc_series[idx]) if idx >= 0 else fallback
    logger.info(f"[RH] _next_soc: Extracting SOC at index {idx} (commit_len={commit_len})")
    logger.info(f"  - SOC value: {soc_value} MWh")
    if len(soc_series) > 0:
        logger.info(f"  - SOC range in window: [{min(soc_series):.1f}, {max(soc_series):.1f}] MWh")
    return soc_value


# ---------------------------------------------------------------------------
# Series aggregation
# ---------------------------------------------------------------------------

def _extend_series(
    global_series: MutableMapping[str, list[float]],
    window_series: Mapping[str, list[float]],
    commit_len: int,
) -> None:
    if commit_len <= 0:
        return
    for col in list(global_series.keys()):
        if col not in window_series:
            global_series[col].extend([0.0] * commit_len)
    for col, values in window_series.items():
        dest = global_series.setdefault(col, [])
        slice_values = list(values[:commit_len])
        if len(slice_values) < commit_len:
            slice_values.extend([0.0] * (commit_len - len(slice_values)))
        dest.extend(slice_values)


# ---------------------------------------------------------------------------
# Parameter / cost-plan loading
# ---------------------------------------------------------------------------

def _load_rolling_params(cfg: Mapping[str, Any]) -> _RollingParams:
    scenario_cfg = cfg.get("scenario", {}) if isinstance(cfg.get("scenario"), dict) else {}
    rolling_cfg = scenario_cfg.get("rolling_horizon") or {}

    def _get(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in mapping:
                return mapping[key]
        return default

    horizon_hours = float(_get(rolling_cfg, "HEAT_HORIZON_HOURS", "heat_horizon_hours", "window_hours", default=DEFAULT_HORIZON_HOURS))
    step_hours = float(_get(rolling_cfg, "STEP_HOURS", "step_hours", default=horizon_hours))
    overlap_hours = float(_get(rolling_cfg, "OVERLAP_HOURS", "overlap_hours", default=0.0))
    terminal_policy = str(_get(rolling_cfg, "terminal_policy", "TERMINAL_POLICY", default="")).strip().lower()

    return _RollingParams(
        horizon_hours=horizon_hours,
        step_hours=step_hours,
        overlap_hours=overlap_hours,
        terminal_policy=terminal_policy,
    )


def _load_cost_plan(cfg: Mapping[str, Any], fix_design: bool) -> _CostAggregationPlan:
    scenario_cfg = cfg.get("scenario", {}) if isinstance(cfg.get("scenario"), dict) else {}
    costs_cfg = scenario_cfg.get("costs") if isinstance(scenario_cfg.get("costs"), dict) else {}
    global_costs_cfg = cfg.get("costs", {}) if isinstance(cfg.get("costs"), dict) else {}

    include_investment = costs_cfg.get("include_investment_in_rh")
    if include_investment is None:
        include_investment = global_costs_cfg.get("include_investment_in_rh")
    if include_investment is None:
        include_investment = not fix_design

    amortise_once = bool(global_costs_cfg.get("amortise_investment_once_in_rh", True))
    include_tie_breaker = bool(global_costs_cfg.get("include_tie_breaker_in_rh", include_investment))
    include_installation = bool(global_costs_cfg.get("include_installation_in_rh", include_investment))
    include_activation = bool(global_costs_cfg.get("include_activation_in_rh", include_investment))

    return _CostAggregationPlan(
        include_investment=bool(include_investment),
        amortise_once=amortise_once,
        include_tie_breaker=include_tie_breaker,
        include_installation=include_installation,
        include_activation=include_activation,
    )


# ---------------------------------------------------------------------------
# Main rolling-horizon loop
# ---------------------------------------------------------------------------

def _run_rolling_horizon(
    base_cfg: dict[str, Any],
    table: TimeSeriesTable,
    dt_h: float,
    solver_name: str,
    params: _RollingParams,
    horizon_steps: int,
    step_steps: int,
    overlap_steps: int,
    design: DesignData | None,
    fix_design: bool,
    *,
    design_spec: DesignSpec | None = None,
    design_config: OptimizationConfig | None = None,
) -> RollingHorizonResult:
    n = len(table)
    if n == 0:
        empty_series: OrderedDict[str, list[float]] = OrderedDict()
        return RollingHorizonResult(table, empty_series, {}, [], design)

    aggregated_indices: list[int] = []
    aggregated_series: OrderedDict[str, list[float]] = OrderedDict()
    aggregated_costs: dict[str, float] = {}
    windows: list[WindowResult] = []

    # Translate OptimizationConfig to the two scalars the loop needs:
    # - has_fix_schedule: True when capacities will be fixed after a window
    # - apply_from_window: first window index where the extracted design is applied
    has_fix_schedule = design_config is not None and (
        design_config.fix_after_window is not None or design_config.fixed_values is not None
    )
    apply_from_window = (
        (design_config.fix_after_window + 1)
        if design_config and design_config.fix_after_window is not None
        else 1
    )

    active_design_spec = design_spec

    design_state = design
    investment_decisions: InvestmentDecisions | None = None
    cost_plan = _load_cost_plan(base_cfg, fix_design or has_fix_schedule)
    once_costs: set[str] = set()

    soc_next = _initial_soc(base_cfg)
    base_storage_enabled = _storage_enabled(base_cfg)

    start = 0
    window_idx = 0
    while start < n:
        last_start = start
        end = min(start + horizon_steps, n)
        if end <= start:
            raise RuntimeError(
                f"Rolling horizon window length is non-positive – check dt_h and HEAT_HORIZON_HOURS. "
                f"Got: start={start}, horizon_steps={horizon_steps}, end={end}, n={n}, dt_h={dt_h}"
            )
        indices = list(range(start, end))
        window_table = _slice_table(table, indices)
        window_cfg = copy.deepcopy(base_cfg)

        if params.terminal_policy:
            _apply_terminal_policy(window_cfg, params.terminal_policy)

        soc_override = soc_next if (soc_next is not None and base_storage_enabled) else None

        policy = (params.terminal_policy or "free").lower()

        if policy in ("value", "free"):
            terminal_target = None
        else:
            terminal_target = soc_override

        # Determine if we should apply a fixed design to this window
        should_apply_design = False

        if active_design_spec is not None:
            if window_idx >= apply_from_window:
                should_apply_design = True
                logger.debug("[DESIGN] Window %d: Applying design_spec (fix_after_window=%s)",
                             window_idx, design_config.fix_after_window if design_config else None)
        elif design_state is not None:
            should_fix_design = bool(
                fix_design
                or (design is None and window_idx > 0)
            )
            if should_fix_design:
                should_apply_design = True
                logger.debug("[DESIGN] Window %d: Applying legacy design_state", window_idx)

        if should_apply_design:
            if active_design_spec is not None:
                window_cfg = apply_design_to_config(window_cfg, active_design_spec)
            elif design_state is not None:
                window_cfg = _apply_design_fix(window_cfg, design_state)

        _apply_cost_overrides(window_cfg, cost_plan, window_idx)

        window_result = _solve_scenario(
            window_table,
            window_cfg,
            dt_h,
            solver_name,
            soc_init_override=soc_override,
            terminal_target_override=terminal_target,
        )

        # Check for infeasible window
        term_cond = (window_result.solver.get("termination_condition") or "").lower()
        if "infeasible" in term_cond or "unbounded" in term_cond:
            logger.error(
                "RH Window %d (start=%d) is %s. Stopping optimization. "
                "Check: heat demand vs capacity, storage SOC constraints, terminal_policy setting.",
                window_idx, start, term_cond
            )
            raise RuntimeError(
                f"Rolling horizon window {window_idx} is infeasible. "
                f"Termination condition: {term_cond}. "
                f"Hint: Check if heat demand exceeds available capacity, "
                f"or if storage terminal_policy='equal' cannot be satisfied."
            )

        commit_len = min(step_steps - overlap_steps, len(window_table)) if step_steps > overlap_steps else 0
        if commit_len <= 0:
            raise RuntimeError(
                f"Rolling horizon produced a zero commit length – ensure STEP_HOURS exceeds OVERLAP_HOURS. "
                f"Got: step_steps={step_steps}, overlap_steps={overlap_steps}, "
                f"window_length={len(window_table)}, commit_len={commit_len}"
            )

        _extend_series(aggregated_series, window_result.series, commit_len)
        aggregated_indices.extend(indices[:commit_len])
        commit_fraction = float(commit_len / len(window_table)) if len(window_table) else 0.0
        _accumulate_costs(
            aggregated_costs,
            window_result.costs,
            cost_plan,
            commit_fraction,
            window_idx,
            once_costs,
        )

        soc_next = _next_soc(window_result.series, commit_len, soc_next)

        windows.append(
            WindowResult(
                table=window_result.table,
                series=window_result.series,
                summary=window_result.summary,
                costs=window_result.costs,
                solver=window_result.solver,
                start_index=start,
                commit_steps=commit_len,
            )
        )

        start += max(step_steps - overlap_steps, 1)
        if start <= last_start:
            raise RuntimeError(
                f"Rolling horizon iteration did not advance – check step_hours/overlap_hours configuration. "
                f"Got: step_steps={step_steps}, overlap_steps={overlap_steps}, "
                f"last_start={last_start}, new_start={start}"
            )
        window_idx += 1

        had_design_state = design_state is not None
        if design_state is None:
            design_state = _extract_design_data(window_result.summary)

        # Capture structured investment decisions from first optimization window
        if investment_decisions is None and window_result.investments is not None:
            if window_result.investments.has_decisions():
                investment_decisions = window_result.investments

        should_extract = (
            design_config is not None
            and design_config.fix_after_window is not None
            and active_design_spec is None
            and window_idx == apply_from_window
            and not had_design_state
        )
        if should_extract:
            active_design_spec = convert_to_design_spec(
                extract_optimization_results(window_result.summary)
            )
            errors = validate_design(active_design_spec)
            if errors:
                logger.warning("[DESIGN] Extracted design has validation issues: %s", errors)
            else:
                logger.info("[DESIGN] Extracted design from Window 0: storage=%.1f MWh / %.1f MW",
                           active_design_spec.storage.capacity_mwh if active_design_spec.storage else 0,
                           active_design_spec.storage.power_mw if active_design_spec.storage else 0)

    if aggregated_indices != list(range(n)):
        raise RuntimeError("Rolling horizon aggregation did not cover the full time series")

    _recompute_objective_costs(aggregated_costs)

    aggregated_table = _slice_table(table, aggregated_indices)
    return RollingHorizonResult(
        aggregated_table, aggregated_series, aggregated_costs, windows,
        design_state, investments=investment_decisions,
    )
