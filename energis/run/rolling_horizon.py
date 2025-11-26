"""Workflow helpers for rolling horizon simulations.

The module implements a lightweight orchestration layer around the existing
`energis.run.orchestrator` utilities.  Callers can describe a sequence of
workflow steps via ``scenario.workflow`` (e.g. ``["PF", "RH"]``) or the legacy
``run_mode`` switch.  This makes it trivial to compare PF-only, RH-only and
combined PF→RH simulations while reusing the same configuration set.  The RH
logic honours configuration entries for window size, step width and terminal
policies while preserving state-of-charge (SOC) values between windows.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import argparse
import copy
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - the solver stack is optional for tests
    HAVE_PYOMO = False
    pyo = None

from energis.config.merge import deep_merge, load_and_merge
from energis.io.loader import load_input_excel
from energis.io.exporter import export_scenario_bundle, write_timeseries_csv
from energis.io.plotter import export_plots
from energis.models.system_builder import build_model
from energis.utils.timeseries import TimeSeriesTable
from . import orchestrator
import time


@dataclass
class ScenarioResult:
    """Container for a single optimisation run."""

    table: TimeSeriesTable
    series: OrderedDict[str, List[float]]
    summary: Mapping[str, Mapping[str, Any]]
    costs: Dict[str, Any]
    solver: Dict[str, Any]


@dataclass
class WindowResult(ScenarioResult):
    """Specialised result carrying metadata for RH windows."""

    start_index: int
    commit_steps: int


@dataclass
class RollingHorizonResult:
    """Aggregated result for a complete RH simulation."""

    table: TimeSeriesTable
    series: OrderedDict[str, List[float]]
    costs: Dict[str, Any]
    windows: List[WindowResult]
    design: Optional[DesignData] = None


@dataclass
class DesignData:
    """Design figures extracted from a PF optimisation."""

    heat_pumps: Dict[str, Dict[str, float]]
    storage: Optional[Dict[str, float]]


@dataclass
class WorkflowPlan:
    """Parsed representation of the requested workflow sequence."""

    steps: Sequence[str]
    fix_design: bool


@dataclass
class WorkflowInputs:
    """Prepared artefacts required to execute a workflow."""

    cfg: Dict[str, Any]
    table: TimeSeriesTable
    dt_h: float
    solver_name: str
    plan: WorkflowPlan


@dataclass
class _RollingParams:
    """Internal helper capturing rolling horizon parameters."""

    horizon_hours: float
    step_hours: float
    overlap_hours: float
    terminal_policy: str

    def as_steps(self, dt_h: float) -> tuple[int, int, int]:
        """Return window, commit and overlap lengths measured in simulation steps."""

        if dt_h <= 0:
            raise ValueError("dt_h must be positive")
        horizon_steps = _hours_to_steps(self.horizon_hours, dt_h, "HEAT_HORIZON_HOURS")
        step_steps = _hours_to_steps(self.step_hours, dt_h, "STEP_HOURS")
        overlap_steps = _hours_to_steps(self.overlap_hours, dt_h, "OVERLAP_HOURS") if self.overlap_hours else 0
        if step_steps > horizon_steps:
            raise ValueError("STEP_HOURS must not exceed HEAT_HORIZON_HOURS")
        if overlap_steps >= step_steps:
            raise ValueError("OVERLAP_HOURS must be smaller than STEP_HOURS")
        return horizon_steps, step_steps, overlap_steps


@dataclass
class WorkflowContext:
    """Mutable state shared between workflow steps."""

    cfg: Dict[str, Any]
    table: TimeSeriesTable
    dt_h: float
    solver_name: str
    plan: WorkflowPlan
    pf_result: Optional[ScenarioResult] = None
    rh_result: Optional[RollingHorizonResult] = None
    mpc_result: Optional[RollingHorizonResult] = None
    design: Optional[DesignData] = None


@dataclass
class _CostAggregationPlan:
    """Configuration for rolling-horizon cost handling."""

    include_investment: bool
    amortise_once: bool
    include_tie_breaker: bool
    include_installation: bool
    include_activation: bool

    def investment_active(self, window_idx: int) -> bool:
        if not self.include_investment:
            return False
        if self.amortise_once and window_idx > 0:
            return False
        return True


StepHandler = Callable[[WorkflowContext], None]


logger = logging.getLogger(__name__)


_STEP_HANDLERS: Dict[str, StepHandler] = {}


_RUN_MODE_ALIASES = {
    "PF": "PF_ONLY",
    "PF_ONLY": "PF_ONLY",
    "PF_THEN_RH": "PF_THEN_RH",
    "PF_AND_RH": "PF_THEN_RH",
    "RH": "RH_ONLY",
    "RH_ONLY": "RH_ONLY",
}


def _normalise_run_mode(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().upper()
    if not key:
        return None
    return _RUN_MODE_ALIASES.get(key, key)


def _parse_run_mode(value: str) -> str:
    normalised = _normalise_run_mode(value)
    if normalised is None:
        raise argparse.ArgumentTypeError("run mode must not be empty")
    if normalised not in {"PF_ONLY", "RH_ONLY", "PF_THEN_RH"}:
        raise argparse.ArgumentTypeError(
            "run mode must be one of PF_ONLY, RH_ONLY or PF_THEN_RH"
        )
    return normalised


def _env_str(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _env_float(name: str) -> float | None:
    raw = _env_str(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - guarded by tests
        raise ValueError(f"Invalid float for {name}: {raw!r}") from exc


def _env_bool(name: str) -> bool | None:
    raw = _env_str(name)
    if raw is None:
        return None
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean for {name}: {raw!r}")


def _parse_float_list(value: str) -> List[float]:
    try:
        return [float(item) for item in value.replace(";", ",").split(",") if item.strip()]
    except ValueError as exc:  # pragma: no cover - guarded by argparse
        raise argparse.ArgumentTypeError(f"Invalid float list: {value}") from exc


@dataclass
class _OverrideValues:
    """Merged CLI/environment overrides for a single run."""

    run_mode: str | None = None
    fix_design: bool | None = None
    horizon_hours: float | None = None
    step_hours: float | None = None
    overlap_hours: float | None = None
    terminal_policy: str | None = None
    design_json: str | None = None
    include_gridcost: bool | None = None
    include_demand_charge: bool | None = None
    include_co2_cost: bool | None = None


def _gather_env_overrides() -> _OverrideValues:
    return _OverrideValues(
        run_mode=_normalise_run_mode(_env_str("RUN_MODE")),
        horizon_hours=_env_float("HEAT_HORIZON_HOURS"),
        step_hours=_env_float("STEP_HOURS"),
        overlap_hours=_env_float("OVERLAP_HOURS"),
        terminal_policy=_env_str("TERMINAL_POLICY"),
        fix_design=_env_bool("FIX_DESIGN"),
        include_gridcost=_env_bool("INCLUDE_GRIDCOST_IN_ENERGY"),
        include_demand_charge=_env_bool("INCLUDE_DEMAND_CHARGE_IN_RH"),
        include_co2_cost=_env_bool("INCLUDE_CO2_COST_IN_OBJECTIVE"),
        design_json=_env_str("PF_DESIGN_JSON"),
    )


def _merge_cli_and_env(
    args: argparse.Namespace, env_values: _OverrideValues
) -> tuple[_OverrideValues, float | None, float | None, float | None]:
    values = _OverrideValues(
        run_mode=args.run_mode or env_values.run_mode,
        fix_design=args.fix_design if args.fix_design is not None else env_values.fix_design,
        terminal_policy=args.terminal_policy or env_values.terminal_policy,
        design_json=args.pf_design_json or env_values.design_json,
        include_gridcost=(
            args.include_gridcost_in_energy
            if args.include_gridcost_in_energy is not None
            else env_values.include_gridcost
        ),
        include_demand_charge=(
            args.include_demand_charge_in_rh
            if args.include_demand_charge_in_rh is not None
            else env_values.include_demand_charge
        ),
        include_co2_cost=(
            args.include_co2_cost_in_objective
            if args.include_co2_cost_in_objective is not None
            else env_values.include_co2_cost
        ),
    )

    horizon_value = args.heat_horizon_hours
    if horizon_value is None:
        horizon_value = args.rh_window_hours if args.rh_window_hours is not None else env_values.horizon_hours

    step_value = args.step_hours if args.step_hours is not None else env_values.step_hours
    overlap_value = args.rh_overlap_hours if args.rh_overlap_hours is not None else env_values.overlap_hours
    return values, horizon_value, step_value, overlap_value


def _build_override_dict(values: _OverrideValues) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    if values.run_mode:
        _assign(overrides, ["scenario", "run_mode"], values.run_mode)
    if values.fix_design is not None:
        _assign(overrides, ["scenario", "fix_design"], bool(values.fix_design))
    if values.terminal_policy:
        _assign(overrides, ["scenario", "rolling_horizon", "terminal_policy"], str(values.terminal_policy))
    if values.design_json:
        _assign(overrides, ["scenario", "pf_design_json"], str(values.design_json))
    if values.include_gridcost is not None:
        _assign(overrides, ["costs", "include_gridcost_in_energy"], bool(values.include_gridcost))
    if values.include_demand_charge is not None:
        _assign(overrides, ["costs", "include_demand_charge_in_rh"], bool(values.include_demand_charge))
    if values.include_co2_cost is not None:
        _assign(overrides, ["costs", "include_co2_cost_in_objective"], bool(values.include_co2_cost))
    return overrides


def _expand_sensitivity_runs(
    args: argparse.Namespace,
    base_overrides: Dict[str, Any],
    horizon_value: float | None,
    step_value: float | None,
    overlap_value: float | None,
) -> List[tuple[float | None, float | None, float | None, Dict[str, Any]]]:
    def _choices(values: List[float] | None, default: float | None) -> List[float | None]:
        if values:
            return list(values)
        if default is not None:
            return [default]
        return [None]

    horizon_choices = _choices(args.sensitivity_horizon_hours, horizon_value)
    step_choices = _choices(args.sensitivity_step_hours, step_value)
    overlap_choices = _choices(args.sensitivity_overlap_hours, overlap_value)

    runs = []
    for horizon in horizon_choices:
        for step in step_choices:
            for overlap in overlap_choices:
                iter_overrides = copy.deepcopy(base_overrides)
                if horizon is not None:
                    _assign(
                        iter_overrides,
                        ["scenario", "rolling_horizon", "heat_horizon_hours"],
                        float(horizon),
                    )
                    _assign(iter_overrides, ["rolling_horizon", "heat_horizon_hours"], float(horizon))
                if step is not None:
                    _assign(iter_overrides, ["scenario", "rolling_horizon", "step_hours"], float(step))
                    _assign(iter_overrides, ["rolling_horizon", "step_hours"], float(step))
                if overlap is not None:
                    _assign(
                        iter_overrides,
                        ["scenario", "rolling_horizon", "overlap_hours"],
                        float(overlap),
                    )
                    _assign(iter_overrides, ["rolling_horizon", "overlap_hours"], float(overlap))
                runs.append((horizon, step, overlap, iter_overrides))
    return runs


def _assign(target: MutableMapping[str, Any], path: Iterable[str], value: Any) -> None:
    node: MutableMapping[str, Any] = target
    keys = list(path)
    for key in keys[:-1]:
        child = node.get(key)
        if not isinstance(child, MutableMapping):
            child = {}
            node[key] = child
        node = child
    node[keys[-1]] = value


def _design_from_mapping(data: Mapping[str, Any]) -> DesignData:
    heat_pumps: Dict[str, Dict[str, float]] = {}
    raw_hps = data.get("heat_pumps")
    if isinstance(raw_hps, Mapping):
        for hp_id, entry in raw_hps.items():
            if not isinstance(entry, Mapping):
                continue
            heat_pumps[str(hp_id)] = {
                "capacity_mw": float(entry.get("capacity_mw", entry.get("Thermal_capacity_MW", 0.0)) or 0.0),
                "build_binary": float(
                    entry.get("build_binary", entry.get("Build", entry.get("Build_binary", 0.0))) or 0.0
                ),
            }

    storage_data = data.get("storage")
    storage: Dict[str, float] | None
    if isinstance(storage_data, Mapping):
        storage = {
            "name": str(storage_data.get("name", storage_data.get("id", "TES")) or "TES"),
            "capacity_mwh": float(
                storage_data.get("capacity_mwh", storage_data.get("Capacity_MWh", 0.0)) or 0.0
            ),
            "power_mw": float(
                storage_data.get("power_mw", storage_data.get("Power_limit_MW", 0.0)) or 0.0
            ),
            "build_binary": float(
                storage_data.get("build_binary", storage_data.get("Build", storage_data.get("Build_binary", 0.0)))
                or 0.0
            ),
        }
    else:
        storage = None

    return DesignData(heat_pumps=heat_pumps, storage=storage)


def _load_design_override(scenario_cfg: Mapping[str, Any]) -> DesignData | None:
    path = scenario_cfg.get("pf_design_json") or scenario_cfg.get("design_json")
    if not path:
        return None
    design_path = Path(str(path)).expanduser()
    if not design_path.exists():
        logger.warning("PF design file %s not found – continuing without design fixation.", design_path)
        return None
    try:
        with open(design_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.warning("Failed to load PF design file %s: %s", design_path, exc)
        return None
    if not isinstance(raw, Mapping):
        logger.warning("Design file %s does not contain a mapping – ignoring content.", design_path)
        return None
    return _design_from_mapping(raw)


def register_workflow_step(name: str, handler: StepHandler) -> None:
    """Register or replace a workflow step handler.

    Parameters
    ----------
    name:
        Identifier used in ``scenario.workflow`` entries.  The identifier is
        stored in upper-case to provide case-insensitive matching.
    handler:
        Callable that mutates a :class:`WorkflowContext` in place.
    """

    key = str(name).strip().upper()
    if not key:
        raise ValueError("Workflow step name must not be empty")
    _STEP_HANDLERS[key] = handler


def unregister_workflow_step(name: str) -> None:
    """Remove a workflow step handler if it exists."""

    key = str(name).strip().upper()
    if key:
        _STEP_HANDLERS.pop(key, None)


def get_registered_workflow_steps() -> List[str]:
    """Return the currently registered workflow step identifiers."""

    return sorted(_STEP_HANDLERS.keys())


@dataclass
class WorkflowResult:
    """Return value for :func:`run_workflow`."""

    config: Dict[str, Any]
    pf_result: Optional[ScenarioResult]
    rh_result: Optional[RollingHorizonResult]
    mpc_result: Optional[RollingHorizonResult]
    design: Optional[DesignData]
    plan: WorkflowPlan


def _build_workflow_inputs(
    config_paths: List[str], overrides: Optional[Dict[str, Any]] = None
) -> WorkflowInputs:
    """Load configs, inputs and workflow plan in a single place.

    The helper keeps :func:`run_workflow` small and ensures that configuration
    merging, time-step preparation and capacity validation follow the same
    order across CLI and notebook usage.
    """

    cfg = load_and_merge(config_paths)
    if overrides:
        cfg = deep_merge(cfg, overrides)

    run_cfg = cfg.get("run", {})
    scenario_cfg = cfg.get("scenario", {})
    site_cfg = cfg.get("site", {})

    dt_h = float(run_cfg.get("dt_h", 1.0))
    table = load_input_excel(site_cfg.get("input_xlsx", "Import_Data.xlsx"), site_cfg, dt_hours=dt_h)
    table.ensure_frequency(dt_h)
    table = orchestrator._apply_horizon(table, scenario_cfg, dt_h)  # type: ignore[attr-defined]
    orchestrator._assert_capacity_vs_demand(table, cfg)  # type: ignore[attr-defined]

    plan = _parse_workflow_plan(scenario_cfg)
    solver_name = str(run_cfg.get("solver", "glpk"))
    return WorkflowInputs(cfg, table, dt_h, solver_name, plan)


def run_workflow(config_paths: List[str], overrides: Optional[Dict[str, Any]] = None) -> WorkflowResult:
    """Execute the configured workflow (PF, RH, MPC or combinations).

    Parameters
    ----------
    config_paths:
        List of configuration file paths that should be merged.
    overrides:
        Optional dictionary applied on top of the merged configuration.
    """

    inputs = _build_workflow_inputs(config_paths, overrides)

    context = WorkflowContext(inputs.cfg, inputs.table, inputs.dt_h, inputs.solver_name, inputs.plan)
    scenario_cfg = inputs.cfg.get("scenario", {})
    design_override = _load_design_override(scenario_cfg if isinstance(scenario_cfg, Mapping) else {})
    if design_override is not None:
        context.design = design_override

    for step in inputs.plan.steps:
        handler = _STEP_HANDLERS.get(step)
        if handler is None:
            raise ValueError(f"Unsupported workflow step: {step}")
        handler(context)

    return WorkflowResult(inputs.cfg, context.pf_result, context.rh_result, context.mpc_result, context.design, inputs.plan)


def _parse_workflow_plan(scenario_cfg: Mapping[str, Any]) -> WorkflowPlan:
    run_mode = str(scenario_cfg.get("run_mode", "")).strip().upper() or "PF_ONLY"
    workflow = scenario_cfg.get("workflow")

    if workflow is not None:
        if isinstance(workflow, (str, bytes)):
            steps = [str(workflow)]
        else:
            steps = list(workflow)
        steps_upper = [str(step).strip().upper() for step in steps if str(step).strip()]
    else:
        mapping = {
            "PF_ONLY": ["PF"],
            "RH_ONLY": ["RH"],
            "PF_THEN_RH": ["PF", "RH"],
            "PF_AND_RH": ["PF", "RH"],
            "MPC_ONLY": ["MPC"],
            "PF_THEN_MPC": ["PF", "MPC"],
        }
        steps_upper = mapping.get(run_mode, ["PF"])

    if not steps_upper:
        raise ValueError("Workflow must contain at least one step")

    fix_default = run_mode in {"PF_THEN_RH", "PF_AND_RH"}
    fix_design = bool(scenario_cfg.get("fix_design", scenario_cfg.get("fix_design_in_rh", fix_default)))

    return WorkflowPlan(steps=steps_upper, fix_design=fix_design)


def _pf_step(context: WorkflowContext) -> None:
    result = _solve_scenario(context.table, context.cfg, context.dt_h, context.solver_name)
    context.pf_result = result
    context.design = _extract_design_data(result.summary)


def _rh_step(context: WorkflowContext) -> None:
    params = _load_rolling_params(context.cfg)
    horizon_steps, step_steps, overlap_steps = params.as_steps(context.dt_h)
    fix_design = context.plan.fix_design and context.design is not None
    if context.plan.fix_design and context.design is None:
        logger.warning(
            "Design fixation requested but no PF design data available – proceeding without fixation."
        )
    context.rh_result = _run_rolling_horizon(
        context.cfg,
        context.table,
        context.dt_h,
        context.solver_name,
        params,
        horizon_steps,
        step_steps,
        overlap_steps,
        context.design,
        fix_design,
    )
    if context.rh_result.design is not None:
        context.design = context.design or context.rh_result.design


def _mpc_step(context: WorkflowContext) -> None:
    """Model Predictive Control with forecast updates."""

    from energis.forecasting.persistence import PersistenceForecast
    from energis.forecasting.perfect_noise import PerfectNoiseForecast
    from energis.run.mpc import run_mpc

    # Load MPC configuration
    mpc_cfg = context.cfg.get("scenario", {}).get("mpc", {})
    forecast_method = str(mpc_cfg.get("forecast_method", "persistence")).lower()
    forecast_horizon_hours = float(mpc_cfg.get("forecast_horizon_hours", 168.0))
    update_frequency_hours = float(mpc_cfg.get("update_frequency_hours", 24.0))

    # Create forecast generator
    if forecast_method == "persistence":
        forecast_gen = PersistenceForecast(context.cfg)
    elif forecast_method in ("perfect_noise", "perfect_with_noise"):
        forecast_gen = PerfectNoiseForecast(context.cfg)
    else:
        raise ValueError(f"Unknown MPC forecast method: {forecast_method}")

    logger.info(f"MPC using forecast method: {forecast_gen.get_method_name()}")

    # Check design fixation
    fix_design = context.plan.fix_design and context.design is not None
    if context.plan.fix_design and context.design is None:
        logger.warning(
            "Design fixation requested but no PF design data available – proceeding without fixation."
        )

    # Run MPC
    context.mpc_result = run_mpc(
        base_cfg=context.cfg,
        historical_data=context.table,
        dt_h=context.dt_h,
        solver_name=context.solver_name,
        forecast_gen=forecast_gen,
        forecast_horizon_hours=forecast_horizon_hours,
        update_frequency_hours=update_frequency_hours,
        design=context.design,
        fix_design=fix_design,
    )

    # Propagate design if MPC found one
    if context.mpc_result.design is not None:
        context.design = context.design or context.mpc_result.design


def _run_rolling_horizon(
    base_cfg: Dict[str, Any],
    table: TimeSeriesTable,
    dt_h: float,
    solver_name: str,
    params: _RollingParams,
    horizon_steps: int,
    step_steps: int,
    overlap_steps: int,
    design: Optional[DesignData],
    fix_design: bool,
) -> RollingHorizonResult:
    n = len(table)
    if n == 0:
        empty_series: OrderedDict[str, List[float]] = OrderedDict()
        return RollingHorizonResult(table, empty_series, {}, [], design)

    aggregated_indices: List[int] = []
    aggregated_series: OrderedDict[str, List[float]] = OrderedDict()
    aggregated_costs: Dict[str, float] = {}
    windows: List[WindowResult] = []

    design_state = design
    cost_plan = _load_cost_plan(base_cfg, fix_design)
    once_costs: Set[str] = set()

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
        window_table = orchestrator._slice_table(table, indices)  # type: ignore[attr-defined]
        window_cfg = copy.deepcopy(base_cfg)

        if params.terminal_policy:
            _apply_terminal_policy(window_cfg, params.terminal_policy)
        if soc_next is not None and base_storage_enabled:
            _set_initial_soc(window_cfg, soc_next)

        should_fix_design = bool(
            design_state is not None
            and (
                fix_design
                or (design is None and window_idx > 0)
            )
        )
        if should_fix_design:
            window_cfg = _apply_design_fix(window_cfg, design_state)  # type: ignore[arg-type]

        _apply_cost_overrides(window_cfg, cost_plan, window_idx)

        window_result = _solve_scenario(window_table, window_cfg, dt_h, solver_name)
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

        if design_state is None:
            design_state = _extract_design_data(window_result.summary)

    if aggregated_indices != list(range(n)):
        raise RuntimeError("Rolling horizon aggregation did not cover the full time series")

    _recompute_objective_costs(aggregated_costs)

    aggregated_table = orchestrator._slice_table(table, aggregated_indices)  # type: ignore[attr-defined]
    return RollingHorizonResult(aggregated_table, aggregated_series, aggregated_costs, windows, design_state)


def _extend_series(
    global_series: MutableMapping[str, List[float]],
    window_series: Mapping[str, List[float]],
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


def _apply_cost_overrides(cfg: MutableMapping[str, Any], plan: _CostAggregationPlan, window_idx: int) -> None:
    costs_cfg = cfg.setdefault("costs", {})
    include_investment = plan.investment_active(window_idx)
    if isinstance(costs_cfg, dict):
        costs_cfg["include_capex_costs"] = include_investment
        costs_cfg["include_activation_costs"] = include_investment and plan.include_activation
        costs_cfg["include_tie_breaker_costs"] = include_investment and plan.include_tie_breaker
        costs_cfg["include_storage_installation_costs"] = include_investment and plan.include_installation


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


def _next_soc(series: Mapping[str, List[float]], commit_len: int, fallback: Optional[float]) -> Optional[float]:
    soc_series = series.get("TES_SOC_MWh")
    if soc_series is None or commit_len <= 0:
        return fallback
    idx = min(commit_len - 1, len(soc_series) - 1)
    return float(soc_series[idx]) if idx >= 0 else fallback


def _solve_scenario(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float,
    solver_name: str,
) -> ScenarioResult:
    model = build_model(table, cfg, dt_h=dt_h)
    solver_meta: Dict[str, Any] = {
        "solver_requested": solver_name,
        "pyomo_available": HAVE_PYOMO,
        "model_built": model is not None,
    }
    if model is not None and HAVE_PYOMO:
        solver_used = solver_name
        try:
            opt = pyo.SolverFactory(solver_name)
        except Exception:  # pragma: no cover - solver fallback
            solver_used = "glpk"
            opt = pyo.SolverFactory("glpk")

        # Apply solver options if configured (CRITICAL FIX: prevents infinite runtime)
        run_cfg = cfg.get("run", {})
        solver_options = run_cfg.get("solver_options", {})
        if solver_options:
            for key, value in solver_options.items():
                opt.options[key] = value
            logger.debug(f"Applied solver options: {solver_options}")

        solver_result = opt.solve(model, tee=False)
        solver_meta["solver_used"] = solver_used
        solver_meta["status"] = str(getattr(getattr(solver_result, "solver", None), "status", "unknown"))
        solver_meta["termination_condition"] = str(
            getattr(getattr(solver_result, "solver", None), "termination_condition", "unknown")
        )
    else:
        solver_meta["solver_used"] = solver_name
        solver_meta["status"] = "not_run"
        solver_meta["termination_condition"] = None

    series, summary, costs = orchestrator._collect_timeseries_and_summary(  # type: ignore[attr-defined]
        table,
        cfg,
        dt_h,
        model if HAVE_PYOMO else None,
    )
    return ScenarioResult(table, series, summary, costs, solver_meta)


def _extract_design_data(summary: Mapping[str, Mapping[str, Any]]) -> DesignData:
    heat_pumps: Dict[str, Dict[str, float]] = {}
    storage: Optional[Dict[str, float]] = None

    for key, metrics in summary.items():
        if key.startswith("heat_pump_"):
            hp_id = key.split("heat_pump_", 1)[1]
            capacity = float(metrics.get("Thermal_capacity_MW", 0.0))
            build = float(metrics.get("Build_binary", metrics.get("Build", 0.0)))
            heat_pumps[hp_id] = {
                "capacity_mw": capacity,
                "build_binary": build,
            }
        elif key.startswith("storage_"):
            storage = {
                "name": key.split("storage_", 1)[1],
                "capacity_mwh": float(metrics.get("Capacity_MWh", 0.0)),
                "power_mw": float(metrics.get("Power_limit_MW", 0.0)),
                "build_binary": float(metrics.get("Build_binary", metrics.get("Build", 0.0))),
            }

    return DesignData(heat_pumps=heat_pumps, storage=storage)


def _load_rolling_params(cfg: Mapping[str, Any]) -> _RollingParams:
    scenario_cfg = cfg.get("scenario", {}) if isinstance(cfg.get("scenario"), dict) else {}
    rolling_cfg = scenario_cfg.get("rolling_horizon") or {}

    def _get(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in mapping:
                return mapping[key]
        return default

    horizon_hours = float(_get(rolling_cfg, "HEAT_HORIZON_HOURS", "heat_horizon_hours", "window_hours", default=168.0))
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


def _hours_to_steps(hours: float, dt_h: float, name: str) -> int:
    if hours <= 0:
        raise ValueError(f"{name} must be positive")
    ratio = hours / dt_h
    rounded = round(ratio)
    if not math.isclose(ratio, rounded, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError(f"{name} must be a multiple of dt_h")
    return max(1, int(rounded))


def _initial_soc(cfg: Mapping[str, Any]) -> Optional[float]:
    system = cfg.get("system", {}) if isinstance(cfg.get("system"), dict) else {}
    storage = system.get("storage", {}) if isinstance(system.get("storage"), dict) else {}
    if not storage or not storage.get("enabled", False):
        return None
    inputs = cfg.get("inputs", {}) if isinstance(cfg.get("inputs"), dict) else {}
    if "SOC_init" in inputs:
        return float(inputs["SOC_init"])
    if "SOC_init" in storage:
        return float(storage["SOC_init"])
    if "soc0_mwh" in storage:
        return float(storage["soc0_mwh"])
    return 0.0


def _storage_enabled(cfg: Mapping[str, Any]) -> bool:
    system = cfg.get("system", {}) if isinstance(cfg.get("system"), dict) else {}
    storage = system.get("storage", {}) if isinstance(system.get("storage"), dict) else {}
    return bool(storage.get("enabled", False))


def _set_initial_soc(cfg: MutableMapping[str, Any], soc: float) -> None:
    inputs = cfg.setdefault("inputs", {})
    if isinstance(inputs, dict):
        inputs["SOC_init"] = float(soc)
    storage = cfg.setdefault("system", {}).setdefault("storage", {})
    if isinstance(storage, dict):
        storage["soc0_mwh"] = float(soc)


def _apply_terminal_policy(cfg: MutableMapping[str, Any], policy: str) -> None:
    if not policy:
        return
    system = cfg.setdefault("system", {})
    if not isinstance(system, dict):
        return
    storage = system.setdefault("storage", {})
    if not isinstance(storage, dict):
        return
    terminal = storage.setdefault("terminal", {})
    if isinstance(terminal, dict):
        terminal["policy"] = policy


def _apply_design_fix(cfg: Dict[str, Any], design: DesignData) -> Dict[str, Any]:
    cfg_copy = copy.deepcopy(cfg)
    system = cfg_copy.setdefault("system", {})
    heat_pumps = system.get("heat_pumps")
    if isinstance(heat_pumps, list):
        for hp_cfg in heat_pumps:
            if not isinstance(hp_cfg, dict):
                continue
            hp_id = str(hp_cfg.get("id"))
            if hp_id not in design.heat_pumps:
                continue
            design_entry = design.heat_pumps[hp_id]
            capacity = float(design_entry.get("capacity_mw", 0.0))
            build_binary = float(design_entry.get("build_binary", 0.0))
            invest_cfg = hp_cfg.setdefault("investment", {})
            if isinstance(invest_cfg, dict):
                invest_cfg["enabled"] = False
                invest_cfg["capacity_min_mw"] = capacity
                invest_cfg["capacity_max_mw"] = capacity
            hp_cfg["max_th_mw"] = capacity
            hp_cfg["min_th_mw"] = capacity
            if build_binary < 0.5:
                hp_cfg["enabled"] = False

    storage_cfg = system.get("storage") if isinstance(system.get("storage"), dict) else None
    if storage_cfg and design.storage:
        storage_cfg["enabled"] = bool(design.storage.get("build_binary", 0.0) >= 0.5)
        storage_cfg["max_energy_mwh"] = float(design.storage.get("capacity_mwh", 0.0))
        storage_cfg["max_power_mw"] = float(design.storage.get("power_mw", 0.0))
        invest_cfg = storage_cfg.setdefault("investment", {})
        if isinstance(invest_cfg, dict):
            invest_cfg["enabled"] = False
            invest_cfg["energy_capacity_min_mwh"] = float(design.storage.get("capacity_mwh", 0.0))
            invest_cfg["energy_capacity_max_mwh"] = float(design.storage.get("capacity_mwh", 0.0))
            invest_cfg["power_capacity_min_mw"] = float(design.storage.get("power_mw", 0.0))
            invest_cfg["power_capacity_max_mw"] = float(design.storage.get("power_mw", 0.0))

    return cfg_copy


def _register_default_steps() -> None:
    register_workflow_step("PF", _pf_step)
    register_workflow_step("RH", _rh_step)
    register_workflow_step("MPC", _mpc_step)


_register_default_steps()


def export_workflow_results(
    workflow: "WorkflowResult",
    outdir: Optional[str] = None,
) -> Dict[str, Any]:
    """Export workflow results to files (Excel, CSV, plots, JSON).

    This is the unified export function that replaces orchestrator.run_all() exports.
    It handles PF, RH, and MPC results consistently.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()
    outdir : str, optional
        Output directory path. If None, creates timestamped directory in exports/

    Returns
    -------
    dict
        Dictionary with export paths and metadata
    """

    # Create output directory
    if outdir is None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        scenario_cfg = workflow.config.get("scenario", {})
        title = str(scenario_cfg.get("title", "Workflow"))
        run_mode = str(scenario_cfg.get("run_mode", "UNKNOWN"))
        tag = scenario_cfg.get("tag") or f"{run_mode}-{title}"
        slug = orchestrator._slugify(tag)  # Reuse orchestrator's slug function
        outdir = os.path.join("exports", f"{stamp}_{slug}")

    os.makedirs(outdir, exist_ok=True)

    # Determine which results we have
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None
    has_mpc = workflow.mpc_result is not None

    # Prepare timeseries sections for Excel export
    timeseries_sections = []
    cost_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()

    # Add PF results
    if has_pf and workflow.pf_result:
        pf_input_series: OrderedDict[str, List[float]] = OrderedDict(
            (col, list(workflow.pf_result.table[col])) for col in workflow.pf_result.table.columns
        )
        pf_result_series: OrderedDict[str, List[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.pf_result.series.items()
        )

        timeseries_sections.append({
            "label": "PF_input",
            "timestamps": list(workflow.pf_result.table.index),
            "series": pf_input_series,
        })
        timeseries_sections.append({
            "label": "PF_result",
            "timestamps": list(workflow.pf_result.table.index),
            "series": pf_result_series,
        })

        if workflow.pf_result.costs:
            cost_sections["PF"] = OrderedDict(
                (str(key), value) for key, value in workflow.pf_result.costs.items()
            )

        # Export PF CSV
        pf_csv = os.path.join(outdir, "pf_timeseries.csv")
        write_timeseries_csv(pf_csv, workflow.pf_result.table, workflow.pf_result.series)

    # Add RH results
    if has_rh and workflow.rh_result:
        rh_result_series: OrderedDict[str, List[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.rh_result.series.items()
        )

        timeseries_sections.append({
            "label": "RH_result",
            "timestamps": list(workflow.rh_result.table.index),
            "series": rh_result_series,
        })

        if workflow.rh_result.costs:
            cost_sections["RH"] = OrderedDict(
                (str(key), value) for key, value in workflow.rh_result.costs.items()
            )

        # Export RH CSV
        rh_csv = os.path.join(outdir, "rh_timeseries.csv")
        write_timeseries_csv(rh_csv, workflow.rh_result.table, workflow.rh_result.series)

    # Add MPC results
    if has_mpc and workflow.mpc_result:
        mpc_result_series: OrderedDict[str, List[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.mpc_result.series.items()
        )

        timeseries_sections.append({
            "label": "MPC_result",
            "timestamps": list(workflow.mpc_result.table.index),
            "series": mpc_result_series,
        })

        if workflow.mpc_result.costs:
            cost_sections["MPC"] = OrderedDict(
                (str(key), value) for key, value in workflow.mpc_result.costs.items()
            )

        # Export MPC CSV
        mpc_csv = os.path.join(outdir, "mpc_timeseries.csv")
        write_timeseries_csv(mpc_csv, workflow.mpc_result.table, workflow.mpc_result.series)

    # Prepare design export
    design_export: Dict[str, Any] = {}
    if workflow.design:
        design_export["heat_pumps"] = workflow.design.heat_pumps
        if workflow.design.storage:
            design_export["storage"] = workflow.design.storage

        # Export design JSON
        design_json_path = os.path.join(outdir, "design.json")
        with open(design_json_path, "w") as f:
            json.dump(design_export, f, indent=2, default=str)

    # Prepare metadata sections
    scenario_cfg = workflow.config.get("scenario", {})
    site_cfg = workflow.config.get("site", {})
    run_cfg = workflow.config.get("run", {})

    stamp = time.strftime("%Y%m%d_%H%M%S")
    dt_h = float(run_cfg.get("dt_h", 1.0))

    metadata_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    metadata_sections["run"] = OrderedDict([
        ("timestamp", stamp),
        ("output_directory", outdir),
        ("dt_h", dt_h),
        ("workflow_steps", list(workflow.plan.steps)),
        ("pyomo_available", HAVE_PYOMO),
    ])

    if isinstance(scenario_cfg, dict):
        metadata_sections["scenario"] = OrderedDict((key, value) for key, value in scenario_cfg.items())

    if isinstance(site_cfg, dict):
        metadata_sections["site"] = OrderedDict((key, value) for key, value in site_cfg.items())

    # Prepare manifest
    title = str(scenario_cfg.get("title", "Workflow"))
    run_mode = str(scenario_cfg.get("run_mode", "UNKNOWN"))
    tag = scenario_cfg.get("tag") or f"{run_mode}-{title}"

    flags = OrderedDict([
        ("has_pf", has_pf),
        ("has_rh", has_rh),
        ("has_mpc", has_mpc),
        ("has_design", bool(design_export)),
    ])

    manifest_data = OrderedDict([
        ("scenario_title", title),
        ("run_mode", run_mode),
        ("workflow_steps", list(workflow.plan.steps)),
        ("flags", flags),
        ("export_timestamp", stamp),
        ("slug", orchestrator._slugify(tag)),
        ("output_directory", outdir),
    ])

    # Export scenario bundle (Excel)
    bundle_paths = dict(
        export_scenario_bundle(
            outdir,
            meta_sections=metadata_sections,
            timeseries_sections=timeseries_sections,
            cost_sections=cost_sections,
            design=design_export,
            manifest=manifest_data,
        )
    )

    # Export plots
    plot_files = []
    try:
        # Export PF plots if available
        if has_pf and workflow.pf_result:
            pf_summary = workflow.pf_result.summary if hasattr(workflow.pf_result, 'summary') else {}
            pf_plots = export_plots(
                outdir,
                workflow.pf_result.table,
                workflow.pf_result.series,
                pf_summary,
            )
            plot_files.extend(pf_plots)
    except Exception as exc:
        print(f"[EXPORT] Plot export skipped: {exc}")

    # Prepare return dictionary
    result_dict = {
        "outdir": outdir,
        "scenario_xlsx": bundle_paths.get("scenario_xlsx"),
        "costs_json": bundle_paths.get("costs_json"),
        "design_json": bundle_paths.get("design_json"),
        "meta_json": bundle_paths.get("meta_json"),
        "manifest_json": bundle_paths.get("manifest_json"),
        "plots": plot_files,
        "costs": {},
    }

    # Add costs from the final result
    if has_mpc and workflow.mpc_result and workflow.mpc_result.costs:
        result_dict["costs"] = workflow.mpc_result.costs
    elif has_rh and workflow.rh_result and workflow.rh_result.costs:
        result_dict["costs"] = workflow.rh_result.costs
    elif has_pf and workflow.pf_result and workflow.pf_result.costs:
        result_dict["costs"] = workflow.pf_result.costs

    return result_dict


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Simple command line interface for :mod:`energis.run.rolling_horizon`."""

    parser = argparse.ArgumentParser(description="Run PF/RH workflows using merged EnerGIS configs")
    parser.add_argument(
        "configs",
        metavar="CONFIG",
        nargs="+",
        help="Configuration files passed to load_and_merge in the given order",
    )
    parser.add_argument(
        "--run-mode",
        type=_parse_run_mode,
        choices=["PF_ONLY", "RH_ONLY", "PF_THEN_RH"],
        help="Override scenario.run_mode (env: RUN_MODE)",
    )
    parser.add_argument(
        "--heat-horizon-hours",
        type=float,
        help="Override rolling horizon window size in hours (env: HEAT_HORIZON_HOURS)",
    )
    parser.add_argument(
        "--rh-window-hours",
        type=float,
        help="Alias for --heat-horizon-hours (env: HEAT_HORIZON_HOURS)",
    )
    parser.add_argument(
        "--step-hours",
        type=float,
        help="Override rolling horizon commit length in hours (env: STEP_HOURS)",
    )
    parser.add_argument(
        "--rh-overlap-hours",
        type=float,
        help="Overlap between consecutive RH windows in hours (env: OVERLAP_HOURS)",
    )
    parser.add_argument(
        "--sensitivity-horizon-hours",
        type=_parse_float_list,
        help="Comma/semicolon separated list of window sizes for a sensitivity sweep",
    )
    parser.add_argument(
        "--sensitivity-step-hours",
        type=_parse_float_list,
        help="Comma/semicolon separated list of commit lengths for a sensitivity sweep",
    )
    parser.add_argument(
        "--sensitivity-overlap-hours",
        type=_parse_float_list,
        help="Comma/semicolon separated list of RH overlaps for a sensitivity sweep",
    )
    parser.add_argument(
        "--terminal-policy",
        help="Override storage terminal policy for RH windows (env: TERMINAL_POLICY)",
    )
    parser.add_argument(
        "--pf-design-json",
        help="Path to a PF design JSON exported by a previous run (env: PF_DESIGN_JSON)",
    )
    parser.add_argument(
        "--fix-design",
        dest="fix_design",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable design fixation during RH (env: FIX_DESIGN)",
    )
    parser.add_argument(
        "--include-gridcost-in-energy",
        dest="include_gridcost_in_energy",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include grid cost in PF objective (env: INCLUDE_GRIDCOST_IN_ENERGY)",
    )
    parser.add_argument(
        "--include-demand-charge-in-rh",
        dest="include_demand_charge_in_rh",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include demand charge during RH runs (env: INCLUDE_DEMAND_CHARGE_IN_RH)",
    )
    parser.add_argument(
        "--include-co2-cost-in-objective",
        dest="include_co2_cost_in_objective",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include CO2 pricing in the optimisation objective (env: INCLUDE_CO2_COST_IN_OBJECTIVE)",
    )
    parser.add_argument(
        "--print-design",
        action="store_true",
        help="Print extracted design values when available",
    )
    args = parser.parse_args(argv)

    try:
        env_values = _gather_env_overrides()
    except ValueError as exc:
        parser.error(str(exc))

    values, horizon_value, step_value, overlap_value = _merge_cli_and_env(args, env_values)
    base_overrides = _build_override_dict(values)
    runs = _expand_sensitivity_runs(args, base_overrides, horizon_value, step_value, overlap_value)

    for idx, (horizon, step, overlap, override_cfg) in enumerate(runs, start=1):
        if len(runs) > 1:
            print(f"[workflow] Sweep run {idx}/{len(runs)}: horizon={horizon}, step={step}, overlap={overlap}")
        result = run_workflow(args.configs, overrides=override_cfg or None)
        steps = " -> ".join(result.plan.steps)
        print(f"[workflow] Executed steps: {steps}")

        if result.pf_result is not None:
            pf_obj = result.pf_result.costs.get("objective.OBJ_value_EUR") if result.pf_result.costs else None
            print(f"  • PF time steps: {len(result.pf_result.table)}")
            if pf_obj is not None:
                print(f"  • PF objective: {pf_obj}")

        if result.rh_result is not None:
            print(f"  • RH windows: {len(result.rh_result.windows)}")
            print(f"  • RH committed steps: {len(result.rh_result.table)}")

        if args.print_design and result.design is not None:
            hp_parts = ", ".join(sorted(result.design.heat_pumps.keys())) or "none"
            print(f"  • Design heat pumps: {hp_parts}")
            if result.design.storage is not None:
                print(f"  • Storage design: {result.design.storage}")

    return 0


__all__ = [
    "ScenarioResult",
    "WindowResult",
    "RollingHorizonResult",
    "DesignData",
    "WorkflowInputs",
    "WorkflowResult",
    "run_workflow",
    "export_workflow_results",
    "WorkflowContext",
    "WorkflowPlan",
    "register_workflow_step",
    "unregister_workflow_step",
    "get_registered_workflow_steps",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    raise SystemExit(main())

