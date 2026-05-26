"""Backward compatibility — all symbols re-exported from new locations.

The original monolithic ``rolling_horizon.py`` has been decomposed into focused
modules under ``calion.run.*``.  This shim re-exports every public and private
symbol so that all existing ``from calion.run.rolling_horizon import X``
statements continue to work without modification.

New code should import from the specific module instead::

    from calion.run.workflow import run_workflow
    from calion.run.types import ScenarioResult
    from calion.run.export import export_workflow_results
"""

# --- Types (dataclasses, type aliases) ------------------------------------
# ``main`` now lives in ``calion.run.__main__`` (the unified CLI).
from calion.run.__main__ import main

# --- Cost helpers ---------------------------------------------------------
from calion.run.cost_helpers import (  # noqa: F401
    _INVESTMENT_KEYS,
    _SKIP_KEYS,
    _accumulate_costs,
    _apply_cost_overrides,
    _recompute_objective_costs,
)

# --- Design helpers -------------------------------------------------------
from calion.run.design_helpers import (  # noqa: F401
    _apply_design_fix,
    _design_from_mapping,
    _extract_design_data,
    _load_design_override,
)

# --- Export ----------------------------------------------------------------
from calion.run.export import (  # noqa: F401
    _write_network_data_to_dir,
    export_workflow_results,
)

# --- Result extraction ----------------------------------------------------
from calion.run.result_collector import (  # noqa: F401
    _as_float,
    _collect_timeseries_and_summary,
    _extract_design_from_summary,
    _flatten_summary,
    _gather_component_metadata,
    _json_safe,
)

# --- RH engine ------------------------------------------------------------
from calion.run.rh_engine import (  # noqa: F401
    _apply_terminal_policy,
    _extend_series,
    _initial_soc,
    _load_cost_plan,
    _load_rolling_params,
    _next_soc,
    _run_rolling_horizon,
    _set_initial_soc,
    _storage_enabled,
)

# --- Solver ---------------------------------------------------------------
from calion.run.solver import _solve_scenario  # noqa: F401
from calion.run.types import (  # noqa: F401
    DesignData,
    RollingHorizonResult,
    ScenarioResult,
    StepHandler,
    WindowResult,
    WorkflowContext,
    WorkflowInputs,
    WorkflowPlan,
    WorkflowResult,
    _CostAggregationPlan,
    _RollingParams,
)

# --- Utilities (re-exported for callers that did ``from rolling_horizon import _slice_table``) ---
from calion.run.utilities import (  # noqa: F401
    _apply_horizon,
    _assert_capacity_vs_demand,
    _env_bool,
    _env_float,
    _env_str,
    _extract_pyomo_series,
    _gather_env_overrides,
    _hours_to_steps,
    _parse_float_list,
    _parse_ts,
    _slice_table,
    _slugify,
)
from calion.run.utilities.env_overrides import (  # noqa: F401
    _normalise_run_mode,
    _OverrideValues,
    _parse_run_mode,
)

# --- Workflow (orchestration, step registry, CLI) -------------------------
from calion.run.workflow import (  # noqa: F401
    _STEP_HANDLERS,
    _assign,
    _build_override_dict,
    _build_workflow_inputs,
    _expand_sensitivity_runs,
    _merge_cli_and_env,
    _parse_workflow_plan,
    add_workflow_cli_args,
    get_registered_workflow_steps,
    register_workflow_step,
    run_workflow,
    unregister_workflow_step,
)

__all__ = [
    "DesignData",
    "RollingHorizonResult",
    "ScenarioResult",
    "WindowResult",
    "WorkflowContext",
    "WorkflowInputs",
    "WorkflowPlan",
    "WorkflowResult",
    "export_workflow_results",
    "get_registered_workflow_steps",
    "main",
    "register_workflow_step",
    "run_workflow",
    "unregister_workflow_step",
]


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    raise SystemExit(main())
