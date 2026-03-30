"""Backward compatibility — all symbols re-exported from new locations.

The original monolithic ``rolling_horizon.py`` has been decomposed into focused
modules under ``energis.run.*``.  This shim re-exports every public and private
symbol so that all existing ``from energis.run.rolling_horizon import X``
statements continue to work without modification.

New code should import from the specific module instead::

    from energis.run.workflow import run_workflow
    from energis.run.types import ScenarioResult
    from energis.run.export import export_workflow_results
"""

# --- Types (dataclasses, type aliases) ------------------------------------
from energis.run.types import (  # noqa: F401
    ScenarioResult,
    WindowResult,
    DesignData,
    RollingHorizonResult,
    WorkflowPlan,
    WorkflowInputs,
    WorkflowContext,
    WorkflowResult,
    _RollingParams,
    _CostAggregationPlan,
    StepHandler,
)

# --- Result extraction ----------------------------------------------------
from energis.run.result_collector import (  # noqa: F401
    _json_safe,
    _gather_component_metadata,
    _flatten_summary,
    _as_float,
    _extract_design_from_summary,
    _collect_timeseries_and_summary,
)

# --- Cost helpers ---------------------------------------------------------
from energis.run.cost_helpers import (  # noqa: F401
    _INVESTMENT_KEYS,
    _SKIP_KEYS,
    _accumulate_costs,
    _recompute_objective_costs,
    _apply_cost_overrides,
)

# --- Design helpers -------------------------------------------------------
from energis.run.design_helpers import (  # noqa: F401
    _extract_design_data,
    _design_from_mapping,
    _load_design_override,
    _apply_design_fix,
)

# --- Solver ---------------------------------------------------------------
from energis.run.solver import _solve_scenario  # noqa: F401

# --- RH engine ------------------------------------------------------------
from energis.run.rh_engine import (  # noqa: F401
    _initial_soc,
    _storage_enabled,
    _set_initial_soc,
    _apply_terminal_policy,
    _next_soc,
    _extend_series,
    _load_rolling_params,
    _load_cost_plan,
    _run_rolling_horizon,
)

# --- Export ----------------------------------------------------------------
from energis.run.export import (  # noqa: F401
    _write_network_data_to_dir,
    export_workflow_results,
)

# --- Workflow (orchestration, step registry, CLI) -------------------------
from energis.run.workflow import (  # noqa: F401
    _STEP_HANDLERS,
    register_workflow_step,
    unregister_workflow_step,
    get_registered_workflow_steps,
    _parse_workflow_plan,
    _build_workflow_inputs,
    run_workflow,
    _assign,
    _merge_cli_and_env,
    _build_override_dict,
    _expand_sensitivity_runs,
    add_workflow_cli_args,
)

# ``main`` now lives in ``energis.run.__main__`` (the unified CLI).
from energis.run.__main__ import main  # noqa: F401

# --- Utilities (re-exported for callers that did ``from rolling_horizon import _slice_table``) ---
from energis.run.utilities import (  # noqa: F401
    _slice_table,
    _parse_ts,
    _apply_horizon,
    _hours_to_steps,
    _slugify,
    _extract_pyomo_series,
    _env_str,
    _env_float,
    _env_bool,
    _parse_float_list,
    _gather_env_overrides,
    _assert_capacity_vs_demand,
)
from energis.run.utilities.env_overrides import (  # noqa: F401
    _OverrideValues,
    _normalise_run_mode,
    _parse_run_mode,
)

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
