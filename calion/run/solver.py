"""Solver invocation wrapper.

Encapsulates the ``build_model → SolverFactory → solve → extract`` pipeline
so that callers only need to provide a table, config, and solver name.
"""

from __future__ import annotations

import os
from datetime import datetime
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


# ═══════════════════════════════════════════════════════════════════════════

# LOGGING UTILITIES

# ═══════════════════════════════════════════════════════════════════════════

def _setup_solver_log(cfg: dict[str, Any]) -> tuple[str | None, bool]:
    """
    Erstellt Log-Datei für Solver-Diagnose.
    
    Returns:
        Tuple von (log_file_path, verbose_flag)
    """
    run_cfg = cfg.get("run", {})
    verbose = run_cfg.get("verbose_logging", False)
    
    # Logging aktiviert?
    if not run_cfg.get("log_to_file", True):
        return None, verbose
    
    # Log-Verzeichnis bestimmen
    output_cfg = cfg.get("output", {})
    log_dir = output_cfg.get("log_dir", resolve_runs_dir() + "/logs")
    
    # Verzeichnis erstellen
    os.makedirs(log_dir, exist_ok=True)
    
    # Dateiname mit Timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scenario_name = cfg.get("scenario", {}).get("name", "unknown")
    # Bereinige Szenarioname für Dateinamen
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in scenario_name)[:50]
    
    log_file = f"{log_dir}/solver_{safe_name}_{timestamp}.log"
    
    return log_file, verbose


def _write_log(log_file: str | None, message: str, verbose: bool = False):
    """
    Schreibt Nachricht in Log-Datei.
    
    Args:
        log_file: Pfad zur Log-Datei (None = kein Logging)
        message: Nachricht
        verbose: Wenn True, auch auf Konsole ausgeben
    """
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    
    # NUR wenn verbose=True auf Konsole ausgeben
    if verbose:
        print(message)


# ═══════════════════════════════════════════════════════════════════════════

# INFEASIBILITY DIAGNOSIS

# ═══════════════════════════════════════════════════════════════════════════

def _diagnose_infeasibility(
    model, 
    solver_result, 
    log_file: str | None = None,
    verbose: bool = False
):
    """
    Diagnostiziert warum ein Pyomo-Modell infeasible ist.
    
    Args:
        model: Pyomo ConcreteModel
        solver_result: Ergebnis von opt.solve()
        log_file: Pfad zur Log-Datei (None = kein File-Logging)
        verbose: Wenn True, auch auf Konsole ausgeben
    """
    import sys
    from io import StringIO
    
    lines = []
    
    def log(msg: str):
        """Interne Log-Funktion - sammelt Zeilen und gibt optional auf Konsole aus."""
        lines.append(msg)
        # NICHT logger.info() verwenden - das geht auf Konsole!
        if verbose:
            print(msg)
    
    log("")
    log("=" * 70)
    log("INFEASIBILITY DIAGNOSIS")
    log("=" * 70)
    log(f"Timestamp: {datetime.now().isoformat()}")
    
    # Solver-Status
    solver_info = getattr(solver_result, 'solver', None)
    if solver_info:
        log(f"Solver Status: {getattr(solver_info, 'status', 'unknown')}")
        log(f"Termination:   {getattr(solver_info, 'termination_condition', 'unknown')}")
    
    # ──────────────────────────────────────────────────────────────────
    # 1. VIOLATED CONSTRAINTS
    # ──────────────────────────────────────────────────────────────────
    log("")
    log("-" * 50)
    log("1. VIOLATED CONSTRAINTS")
    log("-" * 50)
    
    try:
        from pyomo.util.infeasible import log_infeasible_constraints
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        log_infeasible_constraints(
            model, 
            log_expression=True, 
            log_variables=True,
            tol=1e-6
        )
        
        constraint_output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        if constraint_output.strip():
            for line in constraint_output.strip().split("\n"):
                log(line)
        else:
            log("No constraint violations found (tolerance: 1e-6)")
            log("(Model may not have been fully solved)")
            
    except ImportError:
        log("WARNING: pyomo.util.infeasible not available")
    except Exception as e:
        log(f"Error in constraint analysis: {e}")
    
    # ──────────────────────────────────────────────────────────────────
    # 2. BOUNDS VIOLATIONS
    # ──────────────────────────────────────────────────────────────────
    log("")
    log("-" * 50)
    log("2. BOUNDS VIOLATIONS")
    log("-" * 50)
    
    try:
        from pyomo.util.infeasible import log_infeasible_bounds
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        log_infeasible_bounds(model, tol=1e-6)
        
        bounds_output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        if bounds_output.strip():
            for line in bounds_output.strip().split("\n"):
                log(line)
        else:
            log("No bounds violations found")
            
    except Exception as e:
        log(f"Error in bounds analysis: {e}")
    
    # ──────────────────────────────────────────────────────────────────
    # 3. MODEL STATISTICS
    # ──────────────────────────────────────────────────────────────────
    log("")
    log("-" * 50)
    log("3. MODEL STATISTICS")
    log("-" * 50)
    
    try:
        n_vars = sum(1 for _ in model.component_data_objects(pyo.Var, active=True))
        n_cons = sum(1 for _ in model.component_data_objects(pyo.Constraint, active=True))
        n_obj = sum(1 for _ in model.component_data_objects(pyo.Objective, active=True))
        
        n_binary = sum(1 for v in model.component_data_objects(pyo.Var, active=True) 
                      if v.is_binary())
        n_integer = sum(1 for v in model.component_data_objects(pyo.Var, active=True) 
                       if v.is_integer() and not v.is_binary())
        
        log(f"Variables:      {n_vars:,}")
        log(f"  - Binary:     {n_binary:,}")
        log(f"  - Integer:    {n_integer:,}")
        log(f"  - Continuous: {n_vars - n_binary - n_integer:,}")
        log(f"Constraints:    {n_cons:,}")
        log(f"Objectives:     {n_obj}")
        
    except Exception as e:
        log(f"Error in statistics: {e}")
    
    # ──────────────────────────────────────────────────────────────────
    # 4. DEMAND VS. CAPACITY CHECK
    # ──────────────────────────────────────────────────────────────────
    log("")
    log("-" * 50)
    log("4. DEMAND VS. CAPACITY (Quick-Check)")
    log("-" * 50)
    
    try:
        checks_done = False
        
        for comp_name in ['demand', 'total_demand', 'heat_demand', 'Q_demand']:
            if hasattr(model, comp_name):
                comp = getattr(model, comp_name)
                if hasattr(comp, 'values'):
                    values = list(comp.values())
                    if values:
                        max_val = max(v if isinstance(v, (int, float)) else v.value for v in values)
                        log(f"Max {comp_name}: {max_val:.2f}")
                        checks_done = True
        
        for comp_name in ['capacity', 'max_capacity', 'P_max', 'Q_max']:
            if hasattr(model, comp_name):
                comp = getattr(model, comp_name)
                val = comp.value if hasattr(comp, 'value') else comp
                log(f"{comp_name}: {val}")
                checks_done = True
        
        if not checks_done:
            log("No standard demand/capacity parameters found")
            
    except Exception as e:
        log(f"Quick-check failed: {e}")
    
    # ──────────────────────────────────────────────────────────────────
    # 5. RECOMMENDATIONS
    # ──────────────────────────────────────────────────────────────────
    log("")
    log("-" * 50)
    log("5. TROUBLESHOOTING TIPS")
    log("-" * 50)
    log("")
    log("1. Reduce time horizon for testing:")
    log('   horizon: { start: "2025-01-01", end: "2025-01-01 23:00" }')
    log("")
    log("2. Check if all demand columns exist in CSV")
    log("")
    log("3. Verify: Sum of all demands < Total capacity?")
    log("")
    log("4. Temporarily relax constraints:")
    log("   - Increase boiler capacity")
    log("   - Remove min_load constraint")
    log("   - Increase grid import limit")
    log("")
    log("5. Enable solver logging:")
    log("   opt.solve(model, tee=True)")
    log("")
    log("=" * 70)
    log("END DIAGNOSIS")
    log("=" * 70)
    
    # Write ALL lines to log file at once
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    
    return lines


def _log_solver_start(log_file: str | None, cfg: dict[str, Any], solver_name: str, verbose: bool = False):
    """Loggt den Start des Solver-Laufs."""
    lines = [
        "",
        "=" * 70,
        "SOLVER RUN STARTED",
        "=" * 70,
        f"Timestamp:  {datetime.now().isoformat()}",
        f"Scenario:   {cfg.get('scenario', {}).get('name', 'unknown')}",
        f"Solver:     {solver_name}",
        f"Horizon:    {cfg.get('scenario', {}).get('horizon', {})}",
        "-" * 70,
        "",
    ]
    
    if log_file:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    
    if verbose:
        for line in lines:
            print(line)


def _log_solver_result(
    log_file: str | None, 
    solver_meta: dict[str, Any], 
    elapsed_time: float = None,
    verbose: bool = False
):
    """Loggt das Solver-Ergebnis."""
    lines = [
        "",
        "-" * 70,
        "SOLVER RESULT",
        "-" * 70,
        f"Status:      {solver_meta.get('status', 'unknown')}",
        f"Termination: {solver_meta.get('termination_condition', 'unknown')}",
    ]
    
    if elapsed_time:
        lines.append(f"Time:        {elapsed_time:.2f} seconds")
    
    lines.extend(["", "-" * 70, ""])
    
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    
    if verbose:
        for line in lines:
            print(line)


# ═══════════════════════════════════════════════════════════════════════════

# MAIN SOLVE FUNCTION

# ═══════════════════════════════════════════════════════════════════════════

def _solve_scenario(
    table: TimeSeriesTable,
    cfg: dict[str, Any],
    dt_h: float,
    solver_name: str,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
) -> ScenarioResult:
    
    import time
    
    # Setup logging - returns (log_file, verbose)
    log_file, verbose = _setup_solver_log(cfg)
    run_cfg = cfg.get("run", {})
    
    # NUR in Log-Datei schreiben, NICHT auf Konsole (außer verbose=True)
    _write_log(log_file, f"Solver log file: {log_file}", verbose=verbose)
    
    start_time = time.time()
    
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
        "log_file": log_file,
    }
    
    if model is not None and HAVE_PYOMO:
        # Log solver start
        _log_solver_start(log_file, cfg, solver_name, verbose=verbose)
        
        # Warn if nonlinear model is paired with an LP/MILP-only solver
        milp_linearize = cfg.get('thermal_network', {}).get('milp_linearize', False)
        lp_only_solvers = ('highs', 'appsi_highs', 'cbc', 'glpk')
        if not milp_linearize and any(s in solver_name.lower() for s in lp_only_solvers):
            warning_msg = (
                f"WARNING: milp_linearize is False but solver '{solver_name}' only supports LP/MILP. "
                "Bilinear terms (m_dot * T) will cause solver failure. "
                "Set thermal_network.milp_linearize: true in your config."
            )
            # NUR in Log-Datei, NICHT auf Konsole (außer verbose)
            _write_log(log_file, warning_msg, verbose=verbose)

        solver_used = solver_name
        try:
            opt = pyo.SolverFactory(solver_name)
        except (AttributeError, OSError, RuntimeError):
            solver_used = "cbc"
            opt = pyo.SolverFactory("cbc")
            _write_log(log_file, f"Fallback to solver: {solver_used}", verbose=verbose)

        # Apply solver options
        solver_options = run_cfg.get("solver_options", {})
        if solver_options:
            for key, value in solver_options.items():
                opt.options[key] = value
            _write_log(log_file, f"Solver options: {solver_options}", verbose=verbose)

        # Solve with load_solutions=False to prevent RuntimeError
        load_solutions = run_cfg.get("load_solutions", True)
        
        _write_log(log_file, f"Starting solve (load_solutions={load_solutions})...", verbose=verbose)
        
        try:
            solver_result = opt.solve(model, tee=False, load_solutions=load_solutions)
        except Exception as e:
            error_msg = f"ERROR: Solver exception: {e}"
            _write_log(log_file, error_msg, verbose=verbose)
            
            import traceback
            _write_log(log_file, traceback.format_exc(), verbose=verbose)
            
            solver_meta["status"] = "error"
            solver_meta["termination_condition"] = str(e)
            solver_meta["solver_used"] = solver_used
            
            series, summary, costs = _collect_timeseries_and_summary(
                table, cfg, dt_h, None
            )
            return ScenarioResult(table, series, summary, costs, solver_meta)
        
        elapsed_time = time.time() - start_time
        
        solver_meta["solver_used"] = solver_used
        solver_meta["status"] = str(getattr(getattr(solver_result, "solver", None), "status", "unknown"))
        solver_meta["termination_condition"] = str(
            getattr(getattr(solver_result, "solver", None), "termination_condition", "unknown")
        )
        solver_meta["solve_time_seconds"] = elapsed_time
        
        # Log result
        _log_solver_result(log_file, solver_meta, elapsed_time, verbose=verbose)

        # Export thermal network results
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

                # NUR in Log-Datei
                _write_log(log_file, f"Exported {len(export_files)} files to {export_dir}", verbose=verbose)

                solver_meta['export_files'] = export_files
                solver_meta['export_dir'] = export_dir
                solver_meta['network_data'] = network_data

            except Exception as e:
                _write_log(log_file, f"WARNING: Export failed: {e}", verbose=verbose)

        # Check termination condition
        term_cond = solver_meta["termination_condition"].lower()
        
        if "infeasible" in term_cond or "unbounded" in term_cond:
            error_msg = (
                f"ERROR: Solver returned {solver_meta['status']}. Model is {term_cond}. "
                "Check constraints: heat balance, storage limits, terminal policy."
            )
            _write_log(log_file, error_msg, verbose=verbose)
            
            # Run infeasibility diagnosis - NUR in Log-Datei (außer verbose)
            _diagnose_infeasibility(
                model, 
                solver_result, 
                log_file=log_file,
                verbose=verbose
            )
            
            series, summary, costs = _collect_timeseries_and_summary(
                table, cfg, dt_h, None
            )
            return ScenarioResult(table, series, summary, costs, solver_meta)
        
        # Load solution manually if load_solutions=False
        if not load_solutions:
            try:
                model.solutions.load_from(solver_result)
                _write_log(log_file, "Solution loaded successfully", verbose=verbose)
            except Exception as e:
                _write_log(log_file, f"WARNING: Could not load solution: {e}", verbose=verbose)
        
        # Log success
        _write_log(log_file, f"\nSolver completed successfully in {elapsed_time:.2f}s", verbose=verbose)
                
    else:
        solver_meta["solver_used"] = solver_name
        solver_meta["status"] = "not_run"
        solver_meta["termination_condition"] = None
        _write_log(log_file, "Model not built or Pyomo not available", verbose=verbose)

    series, summary, costs = _collect_timeseries_and_summary(
        table,
        cfg,
        dt_h,
        model if HAVE_PYOMO else None,
    )
    investments = InvestmentDecisions.from_summary(summary)
    return ScenarioResult(table, series, summary, costs, solver_meta, investments)