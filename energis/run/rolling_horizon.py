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
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - the solver stack is optional for tests
    HAVE_PYOMO = False
    pyo = None

from energis.config.merge import load_and_merge
from energis.io.loader import load_input_excel
from energis.models.system_builder import build_model
from energis.utils.timeseries import TimeSeriesTable
from . import orchestrator


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
class _RollingParams:
    """Internal helper capturing rolling horizon parameters."""

    horizon_hours: float
    step_hours: float
    terminal_policy: str

    def as_steps(self, dt_h: float) -> tuple[int, int]:
        """Return window and step lengths measured in simulation steps."""

        if dt_h <= 0:
            raise ValueError("dt_h must be positive")
        horizon_steps = _hours_to_steps(self.horizon_hours, dt_h, "HEAT_HORIZON_HOURS")
        step_steps = _hours_to_steps(self.step_hours, dt_h, "STEP_HOURS")
        if step_steps > horizon_steps:
            raise ValueError("STEP_HOURS must not exceed HEAT_HORIZON_HOURS")
        return horizon_steps, step_steps


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
    design: Optional[DesignData] = None


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
    design: Optional[DesignData]
    plan: WorkflowPlan


def run_workflow(config_paths: List[str], overrides: Optional[Dict[str, Any]] = None) -> WorkflowResult:
    """Execute the configured workflow (PF, RH or PF→RH).

    Parameters
    ----------
    config_paths:
        List of configuration file paths that should be merged.
    overrides:
        Optional dictionary applied on top of the merged configuration.
    """

    cfg = load_and_merge(config_paths)
    if overrides:
        cfg = orchestrator._deep_update(cfg, overrides)  # type: ignore[attr-defined]

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

    context = WorkflowContext(cfg, table, dt_h, solver_name, plan)
    design_override = _load_design_override(scenario_cfg if isinstance(scenario_cfg, Mapping) else {})
    if design_override is not None:
        context.design = design_override

    for step in plan.steps:
        handler = _STEP_HANDLERS.get(step)
        if handler is None:
            raise ValueError(f"Unsupported workflow step: {step}")
        handler(context)

    return WorkflowResult(cfg, context.pf_result, context.rh_result, context.design, plan)


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
    horizon_steps, step_steps = params.as_steps(context.dt_h)
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
        context.design,
        fix_design,
    )
    if context.rh_result.design is not None:
        context.design = context.design or context.rh_result.design


def _run_rolling_horizon(
    base_cfg: Dict[str, Any],
    table: TimeSeriesTable,
    dt_h: float,
    solver_name: str,
    params: _RollingParams,
    horizon_steps: int,
    step_steps: int,
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

    soc_next = _initial_soc(base_cfg)
    base_storage_enabled = _storage_enabled(base_cfg)

    start = 0
    window_idx = 0
    while start < n:
        end = min(start + horizon_steps, n)
        indices = list(range(start, end))
        window_table = orchestrator._slice_table(table, indices)  # type: ignore[attr-defined]
        window_cfg = copy.deepcopy(base_cfg)

        if params.terminal_policy:
            _apply_terminal_policy(window_cfg, params.terminal_policy)
        if soc_next is not None and base_storage_enabled:
            _set_initial_soc(window_cfg, soc_next)

        should_fix_design = design_state is not None and (fix_design or window_idx > 0)
        if should_fix_design:
            window_cfg = _apply_design_fix(window_cfg, design_state)  # type: ignore[arg-type]

        window_result = _solve_scenario(window_table, window_cfg, dt_h, solver_name)
        commit_len = min(step_steps, len(window_table))

        _extend_series(aggregated_series, window_result.series, commit_len)
        aggregated_indices.extend(indices[:commit_len])
        _accumulate_costs(aggregated_costs, window_result.costs)

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

        start += step_steps
        window_idx += 1

        if design_state is None:
            design_state = _extract_design_data(window_result.summary)

    if aggregated_indices != list(range(n)):
        raise RuntimeError("Rolling horizon aggregation did not cover the full time series")

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


def _accumulate_costs(target: Dict[str, float], window_costs: Mapping[str, Any]) -> None:
    for key, value in window_costs.items():
        if isinstance(value, (int, float)) and math.isfinite(value):
            target[key] = float(target.get(key, 0.0) + float(value))


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
    rolling_cfg = scenario_cfg.get("rolling_horizon") or cfg.get("rolling_horizon", {}) or {}

    def _get(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in mapping:
                return mapping[key]
        return default

    horizon_hours = float(_get(rolling_cfg, "HEAT_HORIZON_HOURS", "heat_horizon_hours", default=168.0))
    step_hours = float(_get(rolling_cfg, "STEP_HOURS", "step_hours", default=horizon_hours))
    terminal_policy = str(_get(rolling_cfg, "terminal_policy", "TERMINAL_POLICY", default="")).strip().lower()

    return _RollingParams(horizon_hours=horizon_hours, step_hours=step_hours, terminal_policy=terminal_policy)


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


_register_default_steps()


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
        "--step-hours",
        type=float,
        help="Override rolling horizon commit length in hours (env: STEP_HOURS)",
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

    overrides: Dict[str, Any] = {}
    try:
        env_run_mode = _normalise_run_mode(_env_str("RUN_MODE"))
        env_heat_horizon = _env_float("HEAT_HORIZON_HOURS")
        env_step_hours = _env_float("STEP_HOURS")
        env_terminal = _env_str("TERMINAL_POLICY")
        env_fix_design = _env_bool("FIX_DESIGN")
        env_gridcost = _env_bool("INCLUDE_GRIDCOST_IN_ENERGY")
        env_demand_charge = _env_bool("INCLUDE_DEMAND_CHARGE_IN_RH")
        env_co2_cost = _env_bool("INCLUDE_CO2_COST_IN_OBJECTIVE")
        env_design_json = _env_str("PF_DESIGN_JSON")
    except ValueError as exc:
        parser.error(str(exc))

    run_mode = args.run_mode or env_run_mode
    if run_mode:
        _assign(overrides, ["scenario", "run_mode"], run_mode)

    fix_design_value = args.fix_design if args.fix_design is not None else env_fix_design
    if fix_design_value is not None:
        _assign(overrides, ["scenario", "fix_design"], bool(fix_design_value))

    horizon_value = args.heat_horizon_hours if args.heat_horizon_hours is not None else env_heat_horizon
    if horizon_value is not None:
        _assign(overrides, ["scenario", "rolling_horizon", "heat_horizon_hours"], float(horizon_value))
        _assign(overrides, ["rolling_horizon", "heat_horizon_hours"], float(horizon_value))

    step_value = args.step_hours if args.step_hours is not None else env_step_hours
    if step_value is not None:
        _assign(overrides, ["scenario", "rolling_horizon", "step_hours"], float(step_value))
        _assign(overrides, ["rolling_horizon", "step_hours"], float(step_value))

    terminal_value = args.terminal_policy or env_terminal
    if terminal_value:
        _assign(overrides, ["scenario", "rolling_horizon", "terminal_policy"], str(terminal_value))
        _assign(overrides, ["rolling_horizon", "terminal_policy"], str(terminal_value))

    design_json_value = args.pf_design_json or env_design_json
    if design_json_value:
        _assign(overrides, ["scenario", "pf_design_json"], str(design_json_value))

    include_gridcost = (
        args.include_gridcost_in_energy
        if args.include_gridcost_in_energy is not None
        else env_gridcost
    )
    if include_gridcost is not None:
        _assign(overrides, ["costs", "include_gridcost_in_energy"], bool(include_gridcost))

    include_demand = (
        args.include_demand_charge_in_rh
        if args.include_demand_charge_in_rh is not None
        else env_demand_charge
    )
    if include_demand is not None:
        _assign(overrides, ["costs", "include_demand_charge_in_rh"], bool(include_demand))

    include_co2 = (
        args.include_co2_cost_in_objective
        if args.include_co2_cost_in_objective is not None
        else env_co2_cost
    )
    if include_co2 is not None:
        _assign(overrides, ["costs", "include_co2_cost_in_objective"], bool(include_co2))

    result = run_workflow(args.configs, overrides=overrides or None)
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
    "WorkflowResult",
    "run_workflow",
    "WorkflowContext",
    "WorkflowPlan",
    "register_workflow_step",
    "unregister_workflow_step",
    "get_registered_workflow_steps",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    raise SystemExit(main())

