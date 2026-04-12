"""Solver invocation wrapper.

Encapsulates the ``build_model → SolverFactory → solve → extract`` pipeline
so that callers only need to provide a table, config, and solver name.
"""

from __future__ import annotations

from typing import Any

from calion.io._output_paths import resolve_runs_dir
from calion.logging_config import get_logger
from calion.models.results import InvestmentDecisions
from calion.models.system_builder import build_model
from calion.utils.timeseries import TimeSeriesTable

from .result_collector import _collect_timeseries_and_summary
from .types import ScenarioResult

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:  # pragma: no cover
    HAVE_PYOMO = False
    pyo = None


def _solve_scenario(
    table: TimeSeriesTable,
    cfg: dict[str, Any],
    dt_h: float,
    solver_name: str,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
) -> ScenarioResult:
    model = build_model(
        table,
        cfg,
        dt_h=dt_h,
        soc_init_override=soc_init_override,
        terminal_target_override=terminal_target_override,
    )
    solver_meta: dict[str, Any] = {
        "solver_requested": solver_name,
        "pyomo_available": HAVE_PYOMO,
        "model_built": model is not None,
    }
    if model is not None and HAVE_PYOMO:
        # Warn if nonlinear model is paired with an LP/MILP-only solver
        milp_linearize = cfg.get('thermal_network', {}).get('milp_linearize', False)
        lp_only_solvers = ('highs', 'appsi_highs', 'cbc', 'glpk')
        if not milp_linearize and any(s in solver_name.lower() for s in lp_only_solvers):
            logger.warning(
                "milp_linearize is False but solver '%s' only supports LP/MILP. "
                "Bilinear terms (m_dot * T) will cause solver failure. "
                "Set thermal_network.milp_linearize: true in your config.",
                solver_name,
            )

        solver_used = solver_name
        try:
            opt = pyo.SolverFactory(solver_name)
        except (AttributeError, OSError, RuntimeError):  # pragma: no cover - solver fallback
            solver_used = "cbc"
            opt = pyo.SolverFactory("cbc")

        # Apply solver options if configured
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

        # Export solver solution and thermal network results
        export_cfg = cfg.get('output', {})
        if export_cfg.get('export_thermal_network', True) or export_cfg.get('export_solver_solution', True):
            try:
                from calion.io.thermal_network_exporter import export_all_results

                export_dir = export_cfg.get(
                    'export_dir',
                    resolve_runs_dir() + '/thermal_network_results',
                )
                network_mgr = getattr(model, '_network_manager', None)

                export_result = export_all_results(
                    model=model,
                    network_manager=network_mgr,
                    time_set=model.t,
                    output_dir=export_dir,
                    dt_h=dt_h,
                    export_solver_files=export_cfg.get('export_solver_solution', True),
                )

                export_files = export_result.get('files', {})
                network_data = export_result.get('data', {}).get('network', {})

                logger.info(f"[EXPORT] Exported {len(export_files)} files to {export_dir}")

                solver_meta['export_files'] = export_files
                solver_meta['export_dir'] = export_dir
                solver_meta['network_data'] = network_data

            except Exception as e:
                logger.warning(f"[EXPORT] Failed to export thermal network results: {e}")
                import traceback
                traceback.print_exc()

        # Check if solver found a feasible solution
        term_cond = solver_meta["termination_condition"].lower()
        if "infeasible" in term_cond or "unbounded" in term_cond:
            logger.error(
                "Solver returned %s. Model is %s. "
                "Check constraints: heat balance, storage limits, terminal policy.",
                solver_meta["status"], term_cond
            )
            series, summary, costs = _collect_timeseries_and_summary(
                table, cfg, dt_h, None
            )
            return ScenarioResult(table, series, summary, costs, solver_meta)
    else:
        solver_meta["solver_used"] = solver_name
        solver_meta["status"] = "not_run"
        solver_meta["termination_condition"] = None

    series, summary, costs = _collect_timeseries_and_summary(
        table,
        cfg,
        dt_h,
        model if HAVE_PYOMO else None,
    )
    investments = InvestmentDecisions.from_summary(summary)
    return ScenarioResult(table, series, summary, costs, solver_meta, investments)
