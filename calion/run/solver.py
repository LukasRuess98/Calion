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


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


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


# =============================================================================
# WARMSTART FUNCTIONS
# =============================================================================


def _find_col(df, candidates: list[str]) -> str | None:
    """Erste passende Spalte im DataFrame finden."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _infer_binary_from_ws(var, idx, ws_df, times) -> int | None:
    """Infer binary value from prior solution.

    Returns 0 or 1 only when we have clear evidence from the CSV data.
    Returns None otherwise → variable is left unset (partial MIP start).
    Gurobi will complete missing values internally.
    """
    import pandas as pd

    var_name = var.name.lower() if hasattr(var, 'name') else ""

    # Zeitindex extrahieren
    t_idx = None
    if isinstance(idx, (int, float)):
        t_idx = int(idx) - 1
    elif isinstance(idx, tuple):
        for elem in reversed(idx):
            if isinstance(elem, (int, float)):
                t_idx = int(elem) - 1
                break

    # ── Grid mode (buy=1, sell=0) ─────────────────────────────────
    if "grid" in var_name and "mode" in var_name:
        p_buy_col = _find_col(ws_df, ["P_buy_MW", "electricity_purchase_MW", "grid_buy_MW"])
        p_sell_col = _find_col(ws_df, ["P_sell_MW", "electricity_sell_MW", "grid_sell_MW"])
        if p_buy_col and t_idx is not None and 0 <= t_idx < len(ws_df):
            p_buy = float(ws_df.iloc[t_idx].get(p_buy_col, 0))
            p_sell = float(ws_df.iloc[t_idx].get(p_sell_col, 0)) if p_sell_col else 0
            if p_buy > 0.001:
                return 1
            elif p_sell > 0.001:
                return 0
            else:
                return 1  # Default: buy mode when idle
        return None

    # ── Generator on/off ──────────────────────────────────────────
    for gen_key in ["chp", "gasboiler", "biomass", "eboiler"]:
        if gen_key in var_name and ("on" in var_name or "commit" in var_name):
            q_col = _find_col(ws_df, [
                f"{gen_key}_main_Q_th_MW",
                f"Q_{gen_key}_MW",
                f"{gen_key}_heat_MW",
                f"{gen_key}_Q_th_MW",
            ])
            if q_col and t_idx is not None and 0 <= t_idx < len(ws_df):
                q_val = float(ws_df.iloc[t_idx].get(q_col, 0))
                return 1 if q_val > 0.01 else 0
            return None

    # ── HP on/off ─────────────────────────────────────────────────
    if "hp" in var_name and ("on" in var_name or "commit" in var_name):
        hp_col = _find_col(ws_df, ["Q_hp_total_MW", "hp_main_Q_th_MW", "hp_heat_MW"])
        if hp_col and t_idx is not None and 0 <= t_idx < len(ws_df):
            val = float(ws_df.iloc[t_idx].get(hp_col, 0))
            return 1 if val > 0.01 else 0
        return None

    # ── Storage charge/discharge mode ─────────────────────────────
    if ("tes" in var_name or "storage" in var_name) and "mode" in var_name:
        soc_col = _find_col(ws_df, ["SOC_MWh", "storage_SOC_MWh", "TES_SOC_MWh"])
        if soc_col and t_idx is not None and 0 <= t_idx < len(ws_df) - 1:
            soc_now = float(ws_df.iloc[t_idx].get(soc_col, 0))
            soc_next = float(ws_df.iloc[t_idx + 1].get(soc_col, 0))
            if abs(soc_next - soc_now) > 0.1:
                return 1 if soc_next > soc_now else 0
            else:
                return None  # Idle → uncertain
        return None

    # ── Alles andere: KEIN HINT ───────────────────────────────────
    # Pipe regime buckets, startup/shutdown, SOS constraints etc.
    # Gurobi ergänzt diese selbst konsistent.
    return None


def _apply_warmstart(model, warmstart_path: str) -> bool:
    """Set .value hints on BINARY variables where we can reliably infer them.

    Uses a PARTIAL MIP start strategy: only variables with clear evidence
    from the prior solution get a hint. All others are left at None so
    Gurobi can complete them consistently (avoids SOS/logic violations).

    Returns True if hints were successfully loaded.
    """
    import pandas as pd

    logger.info("[WARMSTART] Loading solution hints from: %s", warmstart_path)

    base_path = Path(warmstart_path)

    # Datei finden
    ts_path = None
    for candidate in [
        base_path / "unified_timeseries.csv",
        base_path / "dispatch_hourly.csv",
    ]:
        if candidate.exists():
            ts_path = candidate
            break

    if ts_path is None:
        logger.warning("[WARMSTART] No solution file found in %s — skipping", warmstart_path)
        return False

    sep = ";" if "unified" in ts_path.name else ","
    ws_df = pd.read_csv(ts_path, sep=sep, index_col=0)
    logger.info("[WARMSTART] Loaded %d rows x %d cols from %s", len(ws_df), len(ws_df.columns), ts_path.name)

    times = list(model.t)
    n_hints = 0
    n_skipped = 0

    for var in model.component_objects(pyo.Var, active=True):
        for idx in var:
            v = var[idx]
            if v.is_fixed():
                continue
            if v.is_binary() or v.is_integer():
                val = _infer_binary_from_ws(var, idx, ws_df, times)
                if val is not None:
                    v.value = val
                    n_hints += 1
                else:
                    v.value = None  # Kein Hint → Gurobi ergänzt selbst
                    n_skipped += 1

    logger.info(
        "[WARMSTART] Set %d binary hints, skipped %d (partial MIP start). "
        "Gurobi will complete missing values internally.",
        n_hints, n_skipped,
    )
    return n_hints > 0


# =============================================================================
# MAIN SOLVER FUNCTION
# =============================================================================


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
        # ─── Solver compatibility check ──────────────────────────────
        milp_linearize = _is_milp_linearized(cfg)
        lp_only_solvers = ('highs', 'appsi_highs', 'cbc', 'glpk')
        if not milp_linearize and any(s in solver_name.lower() for s in lp_only_solvers):
            logger.warning(
                "milp_linearize is False but solver '%s' only supports LP/MILP. "
                "Bilinear terms (m_dot * T) will cause solver failure. "
                "Set thermal_network.milp_linearize: true in your config.",
                solver_name,
            )

        # ─── Solver factory ───────────────────────────────────────────
        solver_used = solver_name
        try:
            opt = pyo.SolverFactory(solver_name)
        except (AttributeError, OSError, RuntimeError) as exc:
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

        # ─── Solver options ───────────────────────────────────────────
        run_cfg = cfg.get("run", {})
        solver_options = run_cfg.get("solver_options", {})
        if solver_options:
            for key, value in solver_options.items():
                opt.options[key] = value
            logger.debug("Applied solver options: %s", solver_options)

        # ─── WARMSTART: Partial MIP Start aus vorherigem Lauf ─────────
        warmstart_path = run_cfg.get("warmstart_from")
        use_warmstart = False

        if warmstart_path:
            use_warmstart = _apply_warmstart(model, warmstart_path)

        # ─── SOLVE ────────────────────────────────────────────────────
        solver_result = opt.solve(
            model,
            tee=True,
            warmstart=use_warmstart,
            load_solutions=False,
        )

        solver_meta["solver_used"] = solver_used
        solver_meta["warmstart_applied"] = use_warmstart
        solver_meta["status"] = str(
            getattr(getattr(solver_result, "solver", None), "status", "unknown")
        )
        solver_meta["termination_condition"] = str(
            getattr(getattr(solver_result, "solver", None), "termination_condition", "unknown")
        )
        try:
            solution_count = len(solver_result.solution)
        except Exception:
            solution_count = 0
        solver_meta["solution_count"] = solution_count

        # ─── Feasibility check ────────────────────────────────────────
        term_cond = solver_meta["termination_condition"].lower()
        if "infeasible" in term_cond or "unbounded" in term_cond:
            logger.error(
                "Solver returned %s. Model is %s. "
                "Check constraints: heat balance, storage limits, terminal policy.",
                solver_meta["status"], term_cond,
            )
            # Try Gurobi IIS
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

        # ─── No incumbent check ───────────────────────────────────────
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

        # ─── Load solution ────────────────────────────────────────────
        model.solutions.load_from(solver_result)

        # ─── Export results ───────────────────────────────────────────
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

                logger.info("[EXPORT] Exported %d files to %s", len(export_files), export_dir)

                solver_meta['export_files'] = export_files
                solver_meta['export_dir'] = export_dir
                solver_meta['network_data'] = network_data

            except Exception as e:
                logger.warning("[EXPORT] Failed to export thermal network results: %s", e)
                import traceback
                traceback.print_exc()

    else:
        solver_meta["solver_used"] = solver_name
        solver_meta["status"] = "not_run"
        solver_meta["termination_condition"] = None

    # ─── Collect results ──────────────────────────────────────────
    series, summary, costs = _collect_timeseries_and_summary(
        table,
        cfg,
        dt_h,
        model if (HAVE_PYOMO and model is not None) else None,
    )
    investments = InvestmentDecisions.from_summary(summary)
    return ScenarioResult(table, series, summary, costs, solver_meta, investments)