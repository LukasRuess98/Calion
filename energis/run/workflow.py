"""Workflow orchestration — the main entry point for running simulations.

Provides :func:`run_workflow` (the primary public API), the step-handler
registry (:func:`register_workflow_step`, :func:`unregister_workflow_step`),
and the CLI ``main()`` function that used to live in ``rolling_horizon.py``.
"""

from __future__ import annotations

import argparse
import copy
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from energis.config.merge import deep_merge, load_and_merge
from energis.design import (
    DesignConfig,
    DesignSpec,
    extract_design_from_summary,
    load_design_config,
    load_design_for_scenario,
    save_design_to_file,
)
from energis.io.loader import load_input_excel
from energis.logging_config import get_logger
from energis.utils.timeseries import TimeSeriesTable

from .cost_helpers import _INVESTMENT_KEYS, _recompute_objective_costs
from .design_helpers import _extract_design_data, _load_design_override
from .rh_engine import _load_rolling_params, _run_rolling_horizon
from .solver import _solve_scenario
from .types import (
    DesignData,
    StepHandler,
    WorkflowContext,
    WorkflowInputs,
    WorkflowPlan,
    WorkflowResult,
)
from .utilities import (
    _apply_horizon,
    _assert_capacity_vs_demand,
    _gather_env_overrides,
    _parse_float_list,
)
from .utilities.env_overrides import (
    _OverrideValues,
    _normalise_run_mode,
    _parse_run_mode,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Step-handler registry
# ---------------------------------------------------------------------------

_STEP_HANDLERS: Dict[str, StepHandler] = {}


def register_workflow_step(name: str, handler: StepHandler) -> None:
    """Register or replace a workflow step handler."""
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


# ---------------------------------------------------------------------------
# Workflow plan parsing
# ---------------------------------------------------------------------------

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

    design_config = load_design_config(scenario_cfg)

    fix_default = run_mode in {"PF_THEN_RH", "PF_AND_RH", "PF_THEN_MPC"} or len(steps_upper) > 1
    fix_design = bool(scenario_cfg.get("fix_design", scenario_cfg.get("fix_design_in_rh", fix_default)))

    if fix_design and design_config.mode == "none":
        design_config = DesignConfig(mode="optimize", apply_from_window=1)
        logger.info("[DESIGN] Legacy fix_design=true converted to design.mode=optimize")

    return WorkflowPlan(steps=steps_upper, fix_design=fix_design, design_config=design_config)


# ---------------------------------------------------------------------------
# Workflow input preparation
# ---------------------------------------------------------------------------

def _build_workflow_inputs(
    config_paths: List[str], overrides: Optional[Dict[str, Any]] = None
) -> WorkflowInputs:
    cfg = load_and_merge(config_paths)
    if overrides:
        cfg = deep_merge(cfg, overrides)

    run_cfg = cfg.get("run", {})
    scenario_cfg = cfg.get("scenario", {})
    site_cfg = cfg.get("site", {})

    dt_h = float(run_cfg.get("dt_h", 1.0))
    table = load_input_excel(site_cfg.get("input_xlsx", "Import_Data.xlsx"), site_cfg, dt_hours=dt_h)
    table.ensure_frequency(dt_h)
    table = _apply_horizon(table, scenario_cfg, dt_h)
    _assert_capacity_vs_demand(table, cfg)

    plan = _parse_workflow_plan(scenario_cfg)
    solver_name = str(run_cfg.get("solver", "glpk"))
    return WorkflowInputs(cfg, table, dt_h, solver_name, plan)


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

def _pf_step(context: WorkflowContext) -> None:
    result = _solve_scenario(context.table, context.cfg, context.dt_h, context.solver_name)

    term_cond = (result.solver.get("termination_condition") or "").lower()
    if "infeasible" in term_cond or "unbounded" in term_cond:
        logger.error(
            "Perfect Foresight model is %s. Cannot proceed. "
            "Check: heat demand vs capacity, storage limits, generator constraints.",
            term_cond
        )
        raise RuntimeError(
            f"Perfect Foresight optimization failed: {term_cond}. "
            f"Hint: Verify generator capacities, storage configuration, and input data."
        )
    if result.costs:
        _recompute_objective_costs(result.costs)

    context.pf_result = result
    context.design = _extract_design_data(result.summary)


def _rh_step(context: WorkflowContext) -> None:
    params = _load_rolling_params(context.cfg)
    horizon_steps, step_steps, overlap_steps = params.as_steps(context.dt_h)

    design_config = context.plan.design_config

    if context.design_spec is not None:
        logger.info("[DESIGN] Using pre-loaded design (mode: %s)", design_config.mode if design_config else "unknown")

    fix_design = context.plan.fix_design and context.design is not None
    if context.plan.fix_design and context.design is None and context.design_spec is None:
        logger.warning(
            "Design fixation requested but no design data available – proceeding without fixation."
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
        design_spec=context.design_spec,
        design_config=design_config,
    )

    if context.rh_result.design is not None:
        context.design = context.design or context.rh_result.design

    if design_config and design_config.save_to and context.rh_result.design is not None:
        extracted_spec = extract_design_from_summary(context.rh_result.costs)
        save_design_to_file(extracted_spec, design_config.save_to)
        logger.info("[DESIGN] Saved optimized design to %s", design_config.save_to)

    # Transfer investment costs from PF to RH when fix_design is active
    if context.pf_result and context.rh_result and context.plan.fix_design:
        pf_costs = context.pf_result.costs
        rh_costs = context.rh_result.costs

        investment_transferred = False
        for inv_key in _INVESTMENT_KEYS:
            if inv_key in pf_costs:
                pf_value = pf_costs[inv_key]
                if isinstance(pf_value, (int, float)) and pf_value > 0:
                    rh_costs[inv_key] = float(pf_value)
                    investment_transferred = True

        if investment_transferred:
            _recompute_objective_costs(rh_costs)
            logger.info(
                f"Transferred investment costs from PF to RH result "
                f"(CAPEX: {rh_costs.get('objective.Capex_cost_EUR', 0):,.0f} EUR)"
            )


def _mpc_step(context: WorkflowContext) -> None:
    """Model Predictive Control with forecast updates."""

    from energis.forecasting.persistence import PersistenceForecast
    from energis.forecasting.perfect_noise import PerfectNoiseForecast
    from energis.run.mpc import run_mpc

    mpc_cfg = context.cfg.get("scenario", {}).get("mpc", {})
    forecast_method = str(mpc_cfg.get("forecast_method", "persistence")).lower()
    forecast_horizon_hours = float(mpc_cfg.get("forecast_horizon_hours", 168.0))
    update_frequency_hours = float(mpc_cfg.get("update_frequency_hours", 24.0))

    if forecast_method == "persistence":
        forecast_gen = PersistenceForecast(context.cfg)
    elif forecast_method in ("perfect_noise", "perfect_with_noise"):
        forecast_gen = PerfectNoiseForecast(context.cfg)
    else:
        raise ValueError(f"Unknown MPC forecast method: {forecast_method}")

    logger.info(f"MPC using forecast method: {forecast_gen.get_method_name()}")

    fix_design = context.plan.fix_design and context.design is not None
    if context.plan.fix_design and context.design is None:
        logger.warning(
            "Design fixation requested but no PF design data available – proceeding without fixation."
        )

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

    if context.mpc_result.design is not None:
        context.design = context.design or context.mpc_result.design

    # Transfer investment costs from PF to MPC
    if context.pf_result and context.mpc_result and context.plan.fix_design:
        pf_costs = context.pf_result.costs
        mpc_costs = context.mpc_result.costs

        investment_transferred = False
        for inv_key in _INVESTMENT_KEYS:
            if inv_key in pf_costs:
                pf_value = pf_costs[inv_key]
                if isinstance(pf_value, (int, float)) and pf_value > 0:
                    mpc_costs[inv_key] = float(pf_value)
                    investment_transferred = True

        if investment_transferred:
            _recompute_objective_costs(mpc_costs)
            logger.info(
                f"Transferred investment costs from PF to MPC result "
                f"(CAPEX: {mpc_costs.get('objective.Capex_cost_EUR', 0):,.0f} EUR)"
            )


def _register_default_steps() -> None:
    register_workflow_step("PF", _pf_step)
    register_workflow_step("RH", _rh_step)
    register_workflow_step("MPC", _mpc_step)


_register_default_steps()


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

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

    design_config = inputs.plan.design_config
    if design_config:
        base_path = None
        if config_paths:
            base_path = Path(config_paths[0]).parent

        try:
            context.design_spec = load_design_for_scenario(design_config, base_path)
            if context.design_spec:
                logger.info("[DESIGN] Loaded design: %s", design_config.mode)
        except Exception as e:
            logger.error("[DESIGN] Failed to load design: %s", e)
            raise

    scenario_cfg = inputs.cfg.get("scenario", {})
    if context.design_spec is None:
        design_override = _load_design_override(scenario_cfg if isinstance(scenario_cfg, Mapping) else {})
        if design_override is not None:
            context.design = design_override
            logger.info("[DESIGN] Loaded legacy design override from pf_design_json")

    for step in inputs.plan.steps:
        handler = _STEP_HANDLERS.get(step)
        if handler is None:
            raise ValueError(f"Unsupported workflow step: {step}")
        handler(context)

    return WorkflowResult(inputs.cfg, context.pf_result, context.rh_result, context.mpc_result, context.design, inputs.plan)


# ---------------------------------------------------------------------------
# Config override helpers (used by legacy CLI ``main()``)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Legacy CLI (was at the end of rolling_horizon.py)
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    """Simple command line interface for :mod:`energis.run.workflow`."""

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
            logger.info(f"[workflow] Sweep run {idx}/{len(runs)}: horizon={horizon}, step={step}, overlap={overlap}")
        result = run_workflow(args.configs, overrides=override_cfg or None)
        steps = " -> ".join(result.plan.steps)
        logger.info(f"[workflow] Executed steps: {steps}")

        if result.pf_result is not None:
            pf_obj = result.pf_result.costs.get("objective.OBJ_value_EUR") if result.pf_result.costs else None
            logger.info(f"  • PF time steps: {len(result.pf_result.table)}")
            if pf_obj is not None:
                logger.info(f"  • PF objective: {pf_obj}")

        if result.rh_result is not None:
            logger.info(f"  • RH windows: {len(result.rh_result.windows)}")
            logger.info(f"  • RH committed steps: {len(result.rh_result.table)}")

        if args.print_design and result.design is not None:
            hp_parts = ", ".join(sorted(result.design.heat_pumps.keys())) or "none"
            logger.info(f"  • Design heat pumps: {hp_parts}")
            if result.design.storage is not None:
                logger.info(f"  • Storage design: {result.design.storage}")

    return 0


__all__ = [
    "run_workflow",
    "register_workflow_step",
    "unregister_workflow_step",
    "get_registered_workflow_steps",
    "main",
    "WorkflowResult",
    "WorkflowContext",
    "WorkflowPlan",
    "WorkflowInputs",
]
