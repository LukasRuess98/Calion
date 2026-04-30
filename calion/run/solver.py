"""Solver invocation wrapper.

Encapsulates the ``build_model → SolverFactory → solve → extract`` pipeline
so that callers only need to provide a table, config, and solver name.
"""

from __future__ import annotations

from pathlib import Path
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


def _is_milp_linearized(cfg: dict[str, Any]) -> bool:
    """Read linearization mode across legacy and unified config layouts."""
    return bool(
        cfg.get('thermal_network', {}).get('milp_linearize', False)
        or cfg.get('network', {}).get('milp_linearize', False)
        or cfg.get('scenario', {}).get('milp_linearize', False)
    )


def _resolve_solver_executable(solver_name: str) -> str | None:
    """Locate a solver executable when it is not already on PATH."""
    if solver_name.lower() != "ipopt":
        return None

    try:  # pragma: no cover - optional dependency
        import idaes
    except ImportError:
        return None

    executable = Path(idaes.bin_directory) / "ipopt.exe"
    if executable.exists():
        return str(executable)
    return None


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
        milp_linearize = _is_milp_linearized(cfg)
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
        except (AttributeError, OSError, RuntimeError) as exc:  # pragma: no cover - solver fallback
            logger.warning(
                "Solver '%s' not available (%s), falling back to 'gurobi'.",
                solver_name, exc,
            )
            solver_used = "gurobi"
            opt = pyo.SolverFactory("gurobi")

        solver_executable = None
        if hasattr(opt, "available") and not opt.available(exception_flag=False):
            solver_executable = _resolve_solver_executable(solver_name)
            if solver_executable and hasattr(opt, "set_executable"):
                opt.set_executable(solver_executable, validate=False)
                logger.info(
                    "Using %s executable from %s",
                    solver_name,
                    solver_executable,
                )

        if solver_executable:
            solver_meta["solver_executable"] = solver_executable

        # Apply solver options if configured
        run_cfg = cfg.get("run", {})
        solver_options = run_cfg.get("solver_options", {})
        if solver_options:
            for key, value in solver_options.items():
                opt.options[key] = value
            logger.debug(f"Applied solver options: {solver_options}")

        # === WARMSTART: inject L3plus solution as MIPStart ===
        warmstart_path = run_cfg.get("warmstart_from")  # e.g. "output/paper_runs/L3plus"
        if warmstart_path:
            from pathlib import Path
            import pandas as pd
            ws_file = Path(warmstart_path) / "unified_timeseries.csv"
            if ws_file.exists():
                logger.info("Loading warmstart from %s", ws_file)
                ws_df = pd.read_csv(ws_file, sep=";", index_col=0)
                
                # Set .value hints for all matching Pyomo Vars
                n_set = 0
                for var in model.component_objects(pyo.Var, active=True):
                    for idx in var:
                        var_name = f"{var.name}[{idx}]" if idx is not None else var.name
                        # Match column names from timeseries (simplified mapping)
                        if hasattr(var[idx], 'set_value'):
                            # Gurobi reads var.value as Start hint
                            pass  # see mapping below
                    
                # Simpler approach: use Gurobi's native .sol file
                try:
                    grb_model = opt._solver_model  # after model translation
                    # Can't access before solve — use callback instead
                    pass
                except Exception:
                    pass
                
                # BEST approach: set Pyomo Var.value before solve
                # Gurobi Pyomo interface reads var.value as MIPStart
                for t_idx in model.t:
                    row = t_idx - 1  # 0-indexed
                    if row < len(ws_df):
                        # Storage SOC
                        if hasattr(model, 'SOC') and t_idx in model.SOC:
                            soc_val = ws_df.iloc[row].get("storage_SOC_MWh")
                            if soc_val is not None and not pd.isna(soc_val):
                                model.SOC[t_idx].value = float(soc_val)
                                n_set += 1
                        # Mass flow per pipe
                        for pipe_id in getattr(model, '_pipe_ids', []):
                            col = f"{pipe_id}_m_dot"
                            if col in ws_df.columns and hasattr(model, 'm_dot'):
                                val = ws_df.iloc[row].get(col)
                                if val is not None and not pd.isna(val):
                                    model.m_dot[pipe_id, t_idx].value = float(val)
                                    n_set += 1
                        # Node temperatures
                        for node_id in getattr(model, '_node_ids', []):
                            ts_col = f"{node_id}_T_supply"
                            tr_col = f"{node_id}_T_return"
                            if hasattr(model, 'T_supply'):
                                val = ws_df.iloc[row].get(ts_col)
                                if val is not None and not pd.isna(val):
                                    model.T_supply[node_id, t_idx].value = float(val)
                                    n_set += 1
                            if hasattr(model, 'T_return'):
                                val = ws_df.iloc[row].get(tr_col)
                                if val is not None and not pd.isna(val):
                                    model.T_return[node_id, t_idx].value = float(val)
                                    n_set += 1
                logger.info("Warmstart: set %d variable hints from L3plus solution", n_set)

        # Defer solution loading until after we inspect the solver status.
        # Gurobi can return "aborted/maxTimeLimit" with no incumbent for hard
        # MIQCPs; eager loading raises before we can return useful diagnostics.
        solver_result = opt.solve(model, tee=True, load_solutions=False)
        solver_meta["solver_used"] = solver_used
        solver_meta["status"] = str(getattr(getattr(solver_result, "solver", None), "status", "unknown"))
        solver_meta["termination_condition"] = str(
            getattr(getattr(solver_result, "solver", None), "termination_condition", "unknown")
        )
        try:
            solution_count = len(solver_result.solution)
        except Exception:
            solution_count = 0
        solver_meta["solution_count"] = solution_count

        # Check feasibility BEFORE attempting to read any variable values.
        # Gurobi leaves all variables uninitialized when infeasible — reading them
        # causes a flood of "No value for uninitialized VarData" errors that hide
        # the actual IIS diagnosis.
        term_cond = solver_meta["termination_condition"].lower()
        if "infeasible" in term_cond or "unbounded" in term_cond:
            logger.error(
                "Solver returned %s. Model is %s. "
                "Check constraints: heat balance, storage limits, terminal policy.",
                solver_meta["status"], term_cond
            )
            # Try Gurobi IIS to identify the infeasible constraint set
            try:
                grb_model = opt._solver_model
                grb_model.computeIIS()
                iis_constraints = []
                for c in grb_model.getConstrs():
                    if c.IISConstr:
                        iis_constraints.append(c.ConstrName)
                iis_bounds = []
                for v in grb_model.getVars():
                    if v.IISLB:
                        iis_bounds.append(f"LB({v.VarName})")
                    if v.IISUB:
                        iis_bounds.append(f"UB({v.VarName})")
                logger.error("IIS constraints (%d): %s", len(iis_constraints), iis_constraints[:20])
                logger.error("IIS bounds (%d): %s", len(iis_bounds), iis_bounds[:20])
                solver_meta["iis_constraints"] = iis_constraints
                solver_meta["iis_bounds"] = iis_bounds
            except Exception as iis_err:
                logger.debug("IIS computation failed: %s", iis_err)

            series, summary, costs = _collect_timeseries_and_summary(
                table, cfg, dt_h, None
            )
            return ScenarioResult(table, series, summary, costs, solver_meta)

        if solution_count <= 0:
            logger.error(
                "Solver returned %s/%s without an incumbent solution. "
                "No variable values will be extracted.",
                solver_meta["status"],
                solver_meta["termination_condition"],
            )
            series, summary, costs = _collect_timeseries_and_summary(
                table, cfg, dt_h, None
            )
            return ScenarioResult(table, series, summary, costs, solver_meta)

        model.solutions.load_from(solver_result)

        # Export solver solution and thermal network results (only when a solution exists)
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
    else:
        solver_meta["solver_used"] = solver_name
        solver_meta["status"] = "not_run"
        solver_meta["termination_condition"] = None

    series, summary, costs = _collect_timeseries_and_summary(
        table,
        cfg,
        dt_h,
        model if (HAVE_PYOMO and model is not None) else None,
    )
    investments = InvestmentDecisions.from_summary(summary)
    return ScenarioResult(table, series, summary, costs, solver_meta, investments)
