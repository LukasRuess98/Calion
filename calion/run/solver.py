"""Solver invocation wrapper.

Encapsulates the ``build_model → SolverFactory → solve → extract`` pipeline
so that callers only need to provide a table, config, and solver name.

Two-stage Fix-and-Relax (for MIQCP validation):
  Stage A: Solve MILP relaxation (milp_linearize=True) → extract all binary values
  Stage B: Fix binaries in NLP model → solve pure nonconvex QCP (no branching)
  Result: Temperature propagation solved in ~5-15 min instead of >1h with no solution.
"""

from __future__ import annotations

import copy
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

    # Zeitindex robust extrahieren (unterstützt 0-basierte und 1-basierte Indizes)
    t_idx = None
    raw_t = None
    if isinstance(idx, (int, float)):
        raw_t = int(idx)
    elif isinstance(idx, tuple):
        for elem in reversed(idx):
            if isinstance(elem, (int, float)):
                raw_t = int(elem)
                break
    if raw_t is not None:
        if 0 <= raw_t < len(ws_df):
            t_idx = raw_t
        elif 1 <= raw_t <= len(ws_df):
            t_idx = raw_t - 1

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


def _apply_warmstart(
    model,
    warmstart_path: str,
    fix_binaries: bool = False,
    strict_unknown_fix: bool = False,
) -> bool:
    """Set .value hints or fix binary variables from a prior solution.

    Parameters
    ----------
    model : ConcreteModel
        The Pyomo model to apply warmstart to.
    warmstart_path : str
        Path to directory containing prior solution CSV.
    fix_binaries : bool
        If True: Fix-and-Relax mode — all inferred binaries are FIXED
        (removed from search space). Unknown binaries default to 0.
        If False: Partial MIP start — only set .value hints.

    Returns True if hints/fixes were successfully loaded.

    WARNING (2026-09-05): this seeds binaries by NAME from the prior solution's
    time-series (`_infer_binary_from_ws`), i.e. it hits the per-hour DISPATCH /
    unit-commitment binaries and CANNOT seed INVESTMENT/sizing binaries (those are
    not in the time-series, and a size-ladder that changed between runs won't map).
    So for a "seed the investment, let Gurobi fill the dispatch" MIP start this is the
    WRONG tool — it does the opposite. Worse, across a config change the seeded
    dispatch is often infeasible and Gurobi discards the whole start SILENTLY (only a
    faint "Processing user MIP start" line). Callers that rely on the start must check
    the Gurobi log for "Loaded user MIP start with objective" and record MIP-start
    acceptance in the run manifest — never assume it took.
    """
    import pandas as pd

    mode_str = "FIX-AND-RELAX" if fix_binaries else "PARTIAL MIP START"
    logger.info("[WARMSTART] Loading solution (%s) from: %s", mode_str, warmstart_path)

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
    n_fixed_unknown = 0
    n_skipped = 0

    for var in model.component_objects(pyo.Var, active=True):
        for idx in var:
            v = var[idx]
            if v.is_fixed():
                continue
            if v.is_binary() or v.is_integer():
                val = _infer_binary_from_ws(var, idx, ws_df, times)
                if val is not None:
                    if fix_binaries:
                        v.fix(val)
                    else:
                        v.value = val
                    n_hints += 1
                else:
                    if fix_binaries:
                        if strict_unknown_fix:
                            # Optional strict mode: fix unknown binaries to 0.
                            v.fix(0)
                            n_fixed_unknown += 1
                        else:
                            # Robust default: relax unknown binaries to [0, 1]
                            # to avoid hard infeasibility and combinatorial blow-up.
                            try:
                                v.domain = pyo.UnitInterval
                            except Exception:
                                pass
                            try:
                                v.setlb(0.0)
                                v.setub(1.0)
                                v.value = 0.0
                            except Exception:
                                pass
                            n_skipped += 1
                    else:
                        v.value = None  # Kein Hint → Gurobi ergänzt selbst
                        n_skipped += 1

    if fix_binaries:
        if strict_unknown_fix:
            logger.info(
                "[WARMSTART] FIX-AND-RELAX: Fixed %d binaries from data, "
                "%d unknown binaries defaulted to 0. "
                "Model is now a pure nonconvex QCP (no branching needed).",
                n_hints, n_fixed_unknown,
            )
        else:
            logger.info(
                "[WARMSTART] FIX-AND-RELAX (robust): Fixed %d binaries from data, "
                "relaxed %d unknown binaries to UnitInterval.",
                n_hints, n_skipped,
            )
    else:
        logger.info(
            "[WARMSTART] Set %d binary hints, skipped %d (partial MIP start). "
            "Gurobi will complete missing values internally.",
            n_hints, n_skipped,
        )
    return n_hints > 0


def _apply_warmstart_dump(model, dump_path, fix_binaries: bool = False) -> bool:
    """COMPLETE MIP start from a full var dump {component: {abs_index: value}}.

    Unlike _apply_warmstart (partial, name-inferred binary hints that Gurobi could not
    complete), this reads a full dumped solution keyed by ABSOLUTE year index.

    fix_binaries=False: set var.value for EVERY matching var (a complete start). BUT if
    the dump was stitched from monthly solves with per-month investment (e.g. HP capacity),
    the concatenated CONTINUOUS values violate year-wide linearisations (hp_main_linfix_lo)
    -> Gurobi rejects. So use:
    fix_binaries=True: FIX only the binary/integer COMMITMENT vars (hourly on/off) to the
    dumped schedule and leave the continuous FREE. CRITICALLY, capacity-selection binaries
    (name contains 'cap_x') are NEVER fixed: the monthly seeds each chose their OWN capacity
    segment, so fixing those re-imposes 12 inconsistent capacities -> hp_main_linfix_lo
    infeasible. Leaving them free lets the year LP/MILP pick ONE consistent capacity.
    Override the exclude-substring set via CALION_FIXBIN_EXCLUDE (comma-sep). The schedule-
    fixed solve RE-DERIVES a year-consistent continuous trajectory + investment -> a
    genuinely feasible year solution, dumped and re-used as the complete MIP start. 2026-09-07.
    """
    import json, os as _os_fx
    _excl = tuple(s for s in _os_fx.environ.get("CALION_FIXBIN_EXCLUDE", "cap_x").split(",") if s)
    # RUNG-SPECIFIC TES-SoC PROJECTION (2026-09-10, path-A sweep robustness). A seed built at
    # E_max(source) carries absolute SoC values; injected into a TES-FIXED model at a different
    # E_max(target) it violates the initial-SoC equality E[0]=soc0*E_max by exactly the capacity
    # change. Scaling the TES state vars (E/Qc/Qd) by f = E_max(target)/E_max(source) preserves
    # the SoC RECURSION (every term scales) AND yields E[0]=soc0*E_max(target) exactly. Gated by
    # CALION_SEED_SOC_SCALE=f; applies ONLY to the storage state vars (name ends _E/_Qc/_Qd).
    try:
        _soc_scale = float(_os_fx.environ.get("CALION_SEED_SOC_SCALE", "") or "1.0")
    except ValueError:
        _soc_scale = 1.0
    def _is_tes_state(nm: str) -> bool:
        return ("tes" in nm.lower()) and (nm.endswith("_E") or nm.endswith("_Qc") or nm.endswith("_Qd"))
    p = Path(dump_path)
    if not p.exists():
        logger.warning("[SEED-DUMP] warmstart dump not found: %s", dump_path)
        return False
    data = json.loads(p.read_text(encoding="utf-8"))
    vars_d = data.get("vars", data)
    n = miss = nfix = nscaled = 0
    _n_total_vardata = sum(1 for var in model.component_objects(pyo.Var, active=True) for _ in var)
    for var in model.component_objects(pyo.Var, active=True):
        d = vars_d.get(var.name)
        if not d:
            continue
        if fix_binaries and any(x in var.name for x in _excl):
            continue  # capacity-selection binary — never fix (per-month capacities differ)
        _scale = _soc_scale if (_soc_scale != 1.0 and _is_tes_state(var.name)) else 1.0
        for idx in var:
            v = var[idx]
            if v.is_fixed():
                continue
            key = str(idx)
            if key not in d:
                continue
            try:
                val = float(d[key])
            except Exception:
                miss += 1
                continue
            if fix_binaries and (v.is_binary() or v.is_integer()):
                v.fix(int(round(val))); nfix += 1
            elif not fix_binaries:
                if _scale != 1.0:
                    val *= _scale; nscaled += 1
                v.value = val; n += 1
    if _soc_scale != 1.0:
        logger.info("[SEED-DUMP] TES-SoC projection: scaled %d storage-state values by f=%.4f "
                    "(E_max retarget; preserves recursion + E[0]=soc0*E_max)", nscaled, _soc_scale)
    if fix_binaries:
        logger.info("[SEED-DUMP] FIX-SCHEDULE: fixed %d commitment binaries from %s "
                    "(continuous free -> LP re-derives a year-consistent solution)", nfix, p.name)
        return nfix > 0
    _coverage = (n / _n_total_vardata) if _n_total_vardata else 0.0
    logger.info("[SEED-DUMP] complete MIP start: set %d var values (%d skipped) from %s "
                "-- coverage %.1f%% of %d total var entries in the current model",
                n, miss, p.name, _coverage * 100.0, _n_total_vardata)
    if _coverage < 0.99:
        logger.warning(
            "[SEED-DUMP] PARTIAL start: only %.1f%% of this model's variable entries were "
            "set from %s (%d of %d) -- the remaining %d are left for Gurobi's own subMIP "
            "repair to complete, which has previously failed to produce an incumbent "
            "within its internal budget on large models. Do not assume this start was fully "
            "accepted; check the Gurobi log for 'Loaded user MIP start with objective' vs "
            "'did not produce a new incumbent solution'.",
            _coverage * 100.0, p.name, n, _n_total_vardata, _n_total_vardata - n,
        )
    return n > 0


# =============================================================================
# TWO-STAGE FIX-AND-RELAX
# =============================================================================


def _solve_milp_stage(
    table: TimeSeriesTable,
    cfg: dict[str, Any],
    dt_h: float,
    solver_name: str,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
    time_limit: int = 600,
    mip_gap: float = 0.005,
) -> dict[tuple[str, Any], int] | None:
    """
    Stage A of Fix-and-Relax: Solve MILP relaxation to obtain binary values.

    Builds the same model with milp_linearize=True, solves it quickly,
    then extracts all binary variable values.

    Returns
    -------
    dict mapping (var_name, index) → int value, or None if solve failed.
    """
    logger.info("[FIX-RELAX] ═══ Stage A: Solving MILP relaxation ═══")

    # Build linearized config
    cfg_milp = copy.deepcopy(cfg)
    cfg_milp.setdefault('scenario', {})['milp_linearize'] = True
    cfg_milp.setdefault('network', {})['milp_linearize'] = True
    if 'thermal_network' in cfg_milp:
        cfg_milp['thermal_network']['milp_linearize'] = True

    # Override solver options for fast MILP solve.
    _stage_opts = {
        'MIPGap': mip_gap,
        'TimeLimit': time_limit,
        'MIPFocus': 1,
        'OutputFlag': 1,
        'LogToConsole': 1,
        'Threads': 0,
    }
    # 2026-09-05 FIX (reporting-integrity): this dict previously REPLACED the user
    # config's solver_options wholesale, silently dropping the documented weak-LP-bound
    # knobs (Cuts=2 / MIPFocus=2 / Heuristics / NumericFocus, Implementation Statement
    # Part F.4). Because paper-2 solves through this Stage-A path, the whole frozen
    # campaign ran at MIPFocus=1 / no-Cuts (verified in gurobi_SB-S1-HK0.log), NOT the
    # settings the methods section claims -- which is why gaps sat at 4-9 % / hit the
    # time limit. Propagate ONLY the bound-tightening knobs from the config here (leave
    # Stage-A's own MIPGap/TimeLimit as passed, so paper-1's fast Stage A is unchanged
    # when its config does not set these keys).
    _cfg_opts = cfg.get('run', {}).get('solver_options', {})
    for _k in ('Cuts', 'MIPFocus', 'Heuristics', 'NumericFocus', 'NodefileStart', 'NodefileDir'):
        if _k in _cfg_opts:
            _stage_opts[_k] = _cfg_opts[_k]
    cfg_milp.setdefault('run', {})['solver_options'] = _stage_opts

    # Remove NLP-specific settings. KEEP warmstart_from: Stage A (the hard MILP) can
    # use a prior solution as a DISCRETE-only MIP start, which is the correct fix when
    # a known-good incumbent exists but the default heuristic is stuck far above it
    # (2026-09-05). Read it out before build; it is applied as HINTS below.
    cfg_milp.get('run', {}).pop('fix_binaries_from_milp', None)
    _ws_path = cfg_milp.get('run', {}).pop('warmstart_from', None)

    logger.info("[FIX-RELAX] Building MILP model (milp_linearize=True)...")
    model_milp = build_model(
        table,
        cfg_milp,
        dt_h=dt_h,
        soc_init_override=soc_init_override,
        terminal_target_override=terminal_target_override,
    )

    if model_milp is None:
        logger.error("[FIX-RELAX] Stage A: Failed to build MILP model")
        return None

    # DISCRETE-only MIP start (hint mode): seed the binaries/integers from a prior
    # solution and let Gurobi complete the continuous dispatch, so the start stays
    # feasible across model changes (loss-fix, new cost curve, ceiling). Collapses the
    # integrality gap when the heuristic incumbent sits far above a known optimum.
    _use_ws = False
    import os as _os_wsd
    _wsdump = _os_wsd.environ.get("CALION_WARMSTART_DUMP")
    if _wsdump:
        # COMPLETE MIP start: set every matching var value from the full-year dump so
        # Gurobi accepts a complete incumbent (no fixed-commitment LP to complete, which
        # is what made the partial commitment-only hints infeasible / rejected).
        _use_ws = _apply_warmstart_dump(model_milp, _wsdump)
    elif _ws_path:
        _use_ws = _apply_warmstart(model_milp, _ws_path, fix_binaries=False)

    # Solve MILP
    try:
        opt = pyo.SolverFactory(solver_name)
        for key, value in cfg_milp['run']['solver_options'].items():
            opt.options[key] = value

        logger.info("[FIX-RELAX] Stage A: Solving MILP (TimeLimit=%ds, MIPGap=%.3f, warmstart=%s)...",
                    time_limit, mip_gap, _use_ws)

        solver_result = opt.solve(model_milp, tee=True, load_solutions=False, warmstart=_use_ws)

        # Check feasibility
        term_cond = str(
            getattr(getattr(solver_result, "solver", None), "termination_condition", "unknown")
        ).lower()

        try:
            solution_count = len(solver_result.solution)
        except Exception:
            solution_count = 0

        if "infeasible" in term_cond:
            logger.error("[FIX-RELAX] Stage A: MILP infeasible!")
            return None

        if solution_count <= 0:
            logger.error("[FIX-RELAX] Stage A: No incumbent solution found (status: %s)", term_cond)
            return None

        # Load solution
        model_milp.solutions.load_from(solver_result)
        logger.info("[FIX-RELAX] Stage A: MILP solved (%s)", term_cond)
        # Optional full-solution dump for the complete-MIP-start UC seed (2026-09-07):
        # {component_name: {str(index): value}} + T (max per-var entry count = the time
        # dimension), so the seed builder can remap positional time indices (RangeSet
        # 1..744 per month) to the absolute year index by each month's hour offset.
        import os as _os_dump
        _dump = _os_dump.environ.get("CALION_DUMP_VARS")
        if _dump:
            import json as _json
            _out, _T = {}, 0
            for _v in model_milp.component_objects(pyo.Var, active=True):
                _d = {str(i): float(model_milp.component(_v.name)[i].value)
                      for i in _v if _v[i].value is not None}
                if _d:
                    _out[_v.name] = _d
                    _T = max(_T, len(_d))
            Path(_dump).write_text(_json.dumps({"T": _T, "vars": _out}), encoding="utf-8")
            logger.info("[SEED-DUMP] wrote %d var components (T=%d) -> %s",
                        len(_out), _T, _dump)

    except Exception as e:
        logger.error("[FIX-RELAX] Stage A: Solve failed: %s", e)
        return None

    # Extract ALL binary values
    binary_vals: dict[tuple[str, Any], int] = {}
    n_binary = 0
    n_integer = 0

    for var in model_milp.component_objects(pyo.Var, active=True):
        for idx in var:
            v = var[idx]
            if v.is_binary() or v.is_integer():
                val = v.value
                if val is not None:
                    binary_vals[(var.name, idx)] = int(round(val))
                    if v.is_binary():
                        n_binary += 1
                    else:
                        n_integer += 1
                else:
                    # Variable not in solution (shouldn't happen after load)
                    binary_vals[(var.name, idx)] = 0

    logger.info(
        "[FIX-RELAX] Stage A: Extracted %d binary + %d integer = %d total discrete values",
        n_binary, n_integer, len(binary_vals),
    )

    # Log some statistics
    n_ones = sum(1 for v in binary_vals.values() if v == 1)
    n_zeros = sum(1 for v in binary_vals.values() if v == 0)
    logger.info("[FIX-RELAX] Stage A: %d=1, %d=0 (%.1f%% active)",
                n_ones, n_zeros, n_ones / max(len(binary_vals), 1) * 100)

    return binary_vals


def _apply_binary_fixation(
    model,
    binary_vals: dict[tuple[str, Any], int],
    *,
    strict_unknown_fix: bool = False,
) -> int:
    """
    Stage B: Fix all binary/integer variables in the NLP model from Stage A values.

    After this, the model has 0 discrete variables → pure nonconvex QCP.
    Gurobi solves this without branching (spatial branching only for bilinear).

    Returns number of fixed variables.
    """
    logger.info("[FIX-RELAX] ═══ Stage B: Fixing binaries in NLP model ═══")

    n_fixed = 0
    n_not_found = 0
    n_relaxed = 0
    n_already_fixed = 0

    for var in model.component_objects(pyo.Var, active=True):
        for idx in var:
            v = var[idx]
            if v.is_fixed():
                n_already_fixed += 1
                continue
            if v.is_binary() or v.is_integer():
                key = (var.name, idx)
                if key in binary_vals:
                    v.fix(binary_vals[key])
                    n_fixed += 1
                else:
                    # Binary in NLP but not in MILP (different model structure)
                    if strict_unknown_fix:
                        v.fix(0)
                        n_not_found += 1
                    else:
                        try:
                            v.domain = pyo.UnitInterval
                        except Exception:
                            pass
                        try:
                            v.setlb(0.0)
                            v.setub(1.0)
                            v.value = 0.0
                        except Exception:
                            pass
                        n_relaxed += 1

    if strict_unknown_fix:
        logger.info(
            "[FIX-RELAX] Stage B: Fixed %d from MILP, %d defaulted to 0, "
            "%d already fixed. Model is now pure nonconvex QCP.",
            n_fixed, n_not_found, n_already_fixed,
        )
    else:
        logger.info(
            "[FIX-RELAX] Stage B (robust): Fixed %d from MILP, relaxed %d unmatched "
            "discrete vars to UnitInterval, %d already fixed.",
            n_fixed, n_relaxed, n_already_fixed,
        )

    # Verify: count remaining unfixed discrete variables
    n_remaining = 0
    for var in model.component_objects(pyo.Var, active=True):
        for idx in var:
            v = var[idx]
            if not v.is_fixed() and (v.is_binary() or v.is_integer()):
                n_remaining += 1

    if n_remaining > 0:
        logger.warning("[FIX-RELAX] WARNING: %d discrete variables remain unfixed!", n_remaining)
    else:
        logger.info("[FIX-RELAX] ✓ All discrete variables fixed — 0 remaining")

    return n_fixed


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

        # ─── TWO-STAGE FIX-AND-RELAX (for MIQCP) ─────────────────────
        fix_from_milp = run_cfg.get("fix_binaries_from_milp", False)
        use_warmstart = False
        binary_vals = None

        if fix_from_milp and not milp_linearize:
            # ── Stage A: Solve MILP to get binary values ──────────────
            logger.info(
                "[FIX-RELAX] Two-stage mode activated: "
                "Stage A (MILP) → Stage B (fix binaries → QCP)"
            )

            milp_time_limit = run_cfg.get("milp_stage_time_limit", 600)
            milp_gap = run_cfg.get("milp_stage_gap", 0.005)

            binary_vals = _solve_milp_stage(
                table, cfg, dt_h, solver_name,
                soc_init_override=soc_init_override,
                terminal_target_override=terminal_target_override,
                time_limit=milp_time_limit,
                mip_gap=milp_gap,
            )

            if binary_vals is not None:
                # ── Stage B: Fix binaries in NLP model ────────────────
                strict_fix = bool(run_cfg.get("strict_binary_fixing", False))
                n_fixed = _apply_binary_fixation(
                    model,
                    binary_vals,
                    strict_unknown_fix=strict_fix,
                )
                solver_meta["fix_relax_stage_a"] = "success"
                solver_meta["fix_relax_n_fixed"] = n_fixed
                solver_meta["fix_relax_strategy"] = "two_stage"

                # Keep user-specified feasibility options (e.g., MIPFocus/Heuristics)
                # and only harden numerical robustness for nonconvex QCP.
                opt.options["NumericFocus"] = max(
                    int(opt.options.get("NumericFocus", 0)), 2
                )
                # Reduce time limit — QCP should be fast
                if opt.options.get("TimeLimit", 3600) > 1800:
                    opt.options["TimeLimit"] = 1800  # 30 min max for QCP
                    logger.info("[FIX-RELAX] Reduced TimeLimit to 1800s (QCP mode)")

            else:
                logger.warning(
                    "[FIX-RELAX] Stage A failed — falling back to standard warmstart"
                )
                solver_meta["fix_relax_stage_a"] = "failed"
                solver_meta["fix_relax_strategy"] = "fallback_warmstart"
                fix_from_milp = False  # Fall through to normal warmstart

        # ─── WARMSTART: Partial MIP Start (fallback or explicit) ──────
        warmstart_path = run_cfg.get("warmstart_from")
        import os as _os_wdm
        _wsdump_m = _os_wdm.environ.get("CALION_WARMSTART_DUMP")

        _fixbin = bool(_os_wdm.environ.get("CALION_WARMSTART_FIXBIN"))
        if _wsdump_m and not fix_from_milp:
            # CALION_WARMSTART_FIXBIN: FIX only the commitment binaries from the stitched
            # monthly seed and leave the continuous FREE -> the solve is an LP that
            # re-derives a year-consistent continuous trajectory + investment (the concat
            # of per-month HP capacities violated hp_main_linfix_lo; re-solving heals it).
            # Capture that clean, feasible year solution via CALION_DUMP_VARS for reuse as
            # the (now acceptable) complete MIP start. Otherwise: COMPLETE MIP start.
            use_warmstart = _apply_warmstart_dump(model, _wsdump_m, fix_binaries=_fixbin)
            # INHERITANCE SEED completion (2026-09-09): a dump from a RESTRICTION (e.g. S0,
            # no TES) covers every shared var but leaves the richer model's extra investment
            # vars unset (tes_main_build / size_sel / V_m3 / E / Qc / Qd). Gurobi can't guess
            # the "no-build" assignment for the TES size one-hot (Sigma size_sel = build), so
            # the otherwise-feasible S0 start is rejected. CALION_SEED_FILL_ZERO completes
            # every still-unset var to 0 where 0 is in-bounds — which is exactly the TES-idle
            # (no build) state, making the inherited S0 solution a COMPLETE feasible S1 start.
            if _wsdump_m and _os_wdm.environ.get("CALION_SEED_FILL_ZERO"):
                _nz = _n1 = 0
                for _v in model.component_objects(pyo.Var, active=True):
                    # geometric-storage size one-hot: Sum size_sel = 1 ALWAYS, and the
                    # "no build" state is size_sel[0]=1 (the zero-size rung, v_list[0]=0 ->
                    # build=0). Setting ALL to 0 violates the equality -> infeasible start.
                    # So complete an all-unset size_sel to its zero rung (index 0 -> 1).
                    if _v.name.endswith("_size_sel"):
                        _idx = sorted(_v.keys())
                        if _idx and all(_v[_i].value is None and not _v[_i].is_fixed() for _i in _idx):
                            for _i in _idx:
                                _v[_i].value = 1 if _i == _idx[0] else 0
                            _n1 += 1
                        continue
                    for _i in _v:
                        _vi = _v[_i]
                        if _vi.value is not None or _vi.is_fixed():
                            continue
                        _lb, _ub = _vi.lb, _vi.ub
                        if (_lb is None or _lb <= 0) and (_ub is None or _ub >= 0):
                            _vi.value = 0; _nz += 1
                logger.info("[SEED-DUMP] inheritance fill-zero: %d unset vars -> 0, %d size one-hot(s) "
                            "-> zero rung (TES no-build state)", _nz, _n1)
        elif warmstart_path and not fix_from_milp:
            # Only apply warmstart if we didn't already do fix-and-relax
            fix_binaries_flag = run_cfg.get("fix_binaries_from_warmstart", False)
            strict_fix = bool(run_cfg.get("strict_binary_fixing", False))
            # K1 (2026-09-26, docs SS4be): prefer a COMPLETE prior solution (full_solution_dump.json,
            # now written unconditionally after every successful solve) over the CSV-column-inferred
            # PARTIAL binary-only hints -- the partial path is the confirmed root cause of the
            # SB-S0-HK0 seeded re-run's rejected MIP start (only 1.5% of binaries hinted, Gurobi's
            # subMIP repair failed to complete the other 98.5% within its internal budget).
            _full_dump_candidate = Path(warmstart_path) / "full_solution_dump.json"
            if _full_dump_candidate.exists():
                logger.info("[WARMSTART] Found full_solution_dump.json at %s -- using COMPLETE "
                            "MIP start instead of the partial CSV-column-inferred binary hints.",
                            _full_dump_candidate)
                use_warmstart = _apply_warmstart_dump(
                    model, str(_full_dump_candidate), fix_binaries=fix_binaries_flag,
                )
            else:
                logger.warning("[WARMSTART] No full_solution_dump.json in %s (pre-K1 run, or "
                               "export failed) -- falling back to the PARTIAL CSV-column-inferred "
                               "binary-only hints. This start is likely to be rejected by Gurobi's "
                               "subMIP repair on large models; treat any resulting incumbent with "
                               "caution.", warmstart_path)
                use_warmstart = _apply_warmstart(
                    model,
                    warmstart_path,
                    fix_binaries=fix_binaries_flag,
                    strict_unknown_fix=strict_fix,
                )
            if fix_binaries_flag and use_warmstart:
                solver_meta["fix_relax_strategy"] = "warmstart_fix"
                # Same QCP robustness adjustment, while preserving feasibility-focused
                # search options provided by the caller.
                opt.options["NumericFocus"] = max(
                    int(opt.options.get("NumericFocus", 0)), 2
                )

        # ─── FEASIBILITY-ONLY DIAGNOSTIC (2026-09-07) ────────────────
        # With var.values set from the seed dump, report which year-model constraints
        # the concatenated monthly solution violates (top-15) instead of solving — finds
        # the ONE broken constraint behind the 7 MIP-start rejections. No solve.
        if _os_wdm.environ.get("CALION_FEAS_ONLY"):
            # L1 (2026-09-27, docs SS4bg): also report the TRUE objective value at this
            # transplanted point, before any violations abort the run -- this is what an
            # incumbent-pool report needs as the evaluated UB for the seeded scenario/point.
            _obj_at_point = pyo.value(model.obj, exception=False) if hasattr(model, 'obj') else None
            logger.info("[FEAS-CHECK] objective at seeded point: %s",
                        f"{_obj_at_point:.2f} EUR" if _obj_at_point is not None else "UNCOMPUTABLE (unset var in objective expr)")
            _viol = []
            for _con in model.component_objects(pyo.Constraint, active=True):
                for _ix in _con:
                    _c = _con[_ix]
                    _b = pyo.value(_c.body, exception=False)
                    if _b is None:
                        continue
                    _lo = pyo.value(_c.lower, exception=False)
                    _hi = pyo.value(_c.upper, exception=False)
                    _d = 0.0
                    if _lo is not None and _b < _lo - 1e-6:
                        _d = _lo - _b
                    elif _hi is not None and _b > _hi + 1e-6:
                        _d = _b - _hi
                    if _d > 1e-6:
                        _viol.append((_d, _con.name, str(_ix)))
            _viol.sort(reverse=True)
            logger.error("[FEAS-CHECK] %d violated constraints (of the seeded assignment)."
                         " Top 15:", len(_viol))
            for _dv, _nm, _ixs in _viol[:15]:
                logger.error("[FEAS-CHECK]   viol=%.5g  %s[%s]", _dv, _nm, _ixs)
            raise RuntimeError(f"[FEAS-CHECK] done: {len(_viol)} violations (diagnostic only)")

        # ─── EXTRACT-ONLY, NO SOLVE (W4, 2026-09-30, docs SS4bw-W) ─────
        # Re-extract a run's FULL cost/result breakdown under CURRENT code (e.g. after a
        # code fix like V1-V5) from its already-found solution (CALION_WARMSTART_FROM's
        # full_solution_dump.json), WITHOUT re-solving. Unlike CALION_FEAS_ONLY (which
        # always raises after a diagnostic-only violation scan), this returns a normal
        # ScenarioResult by falling through to the SAME _collect_timeseries_and_summary()
        # call every real solve uses (further down in this function) -- so cost_breakdown.json/
        # economics.csv/etc. come out identically shaped, just built from transplanted
        # values instead of a fresh solve. Logs (does not abort on) constraint violations,
        # since a code-only fix (no constraint changes) should leave the point feasible;
        # a real violation here would mean the fix DID change what's feasible, worth flagging.
        if _os_wdm.environ.get("CALION_EXTRACT_ONLY"):
            _n_viol = 0
            # X1 (2026-09-30, docs SS4bw-W): full violation capture (not just a count/top-15)
            # for constraint-family classification, gated behind a separate env var so the
            # normal (fast) W4 re-extraction path is unaffected.
            _viol_dump_path = _os_wdm.environ.get("CALION_VIOLATIONS_DUMP")
            _viol_detail: list = []
            _n_vars_total = 0
            _n_vars_unset = 0
            for _vv in model.component_objects(pyo.Var, active=True):
                for _vix in _vv:
                    _n_vars_total += 1
                    if _vv[_vix].value is None:
                        _n_vars_unset += 1
            for _con in model.component_objects(pyo.Constraint, active=True):
                for _ix in _con:
                    _c = _con[_ix]
                    _b = pyo.value(_c.body, exception=False)
                    if _b is None:
                        continue
                    _lo = pyo.value(_c.lower, exception=False)
                    _hi = pyo.value(_c.upper, exception=False)
                    _viol_amt = 0.0
                    if _lo is not None and _b < _lo - 1e-6:
                        _viol_amt = _lo - _b
                    elif _hi is not None and _b > _hi + 1e-6:
                        _viol_amt = _b - _hi
                    if _viol_amt > 1e-6:
                        _n_viol += 1
                        if _viol_dump_path:
                            _viol_detail.append({
                                "constraint": _con.name, "index": str(_ix),
                                "violation": _viol_amt, "body": _b, "lower": _lo, "upper": _hi,
                            })
            if _viol_dump_path:
                import json as _json_vd
                Path(_viol_dump_path).parent.mkdir(parents=True, exist_ok=True)
                Path(_viol_dump_path).write_text(_json_vd.dumps({
                    "n_violations": _n_viol,
                    "n_vars_total": _n_vars_total,
                    "n_vars_unset": _n_vars_unset,
                    "var_coverage_pct": round(100.0 * (_n_vars_total - _n_vars_unset) / max(_n_vars_total, 1), 4),
                    "violations": _viol_detail,
                }, indent=2), encoding="utf-8")
                logger.info("[EXTRACT-ONLY] wrote %d violation details + var coverage (%d/%d, %.2f%%) -> %s",
                            len(_viol_detail), _n_vars_total - _n_vars_unset, _n_vars_total,
                            100.0 * (_n_vars_total - _n_vars_unset) / max(_n_vars_total, 1), _viol_dump_path)
            if _n_viol:
                logger.warning("[EXTRACT-ONLY] %d constraint violations at the transplanted "
                                "point under current code -- the fix may have changed what's "
                                "feasible; treat this re-extraction with caution.", _n_viol)
            else:
                logger.info("[EXTRACT-ONLY] 0 constraint violations at the transplanted point "
                            "-- re-extracting under current code, no solve.")
            solver_meta["solver_used"] = solver_name
            solver_meta["status"] = "extract_only_no_solve"
            solver_meta["termination_condition"] = "not_solved_transplanted_from_warmstart"
            solver_meta["extract_only_constraint_violations"] = _n_viol
            series, summary, costs = _collect_timeseries_and_summary(table, cfg, dt_h, model)
            investments = InvestmentDecisions.from_summary(summary)
            return ScenarioResult(table, series, summary, costs, solver_meta, investments)

        # ─── SOLVE ────────────────────────────────────────────────────
        # Determine if we should pass warmstart flag to Gurobi
        # (only meaningful if we set .value hints, not if we .fix()'d)
        pass_warmstart = use_warmstart and not fix_from_milp and not _fixbin and not run_cfg.get(
            "fix_binaries_from_warmstart", False
        )

        solver_result = opt.solve(
            model,
            tee=True,
            warmstart=pass_warmstart,
            load_solutions=False,
        )

        solver_meta["solver_used"] = solver_used
        solver_meta["warmstart_applied"] = use_warmstart or (binary_vals is not None)
        # Capture model size stats (Pyomo native counting, always available)
        try:
            from pyomo.core import Var, Constraint
            _all_vars = list(model.component_data_objects(Var, active=True))
            solver_meta["num_vars"] = len(_all_vars)
            solver_meta["num_bin"] = sum(1 for v in _all_vars if v.is_binary())
            solver_meta["num_constr"] = sum(
                1 for _ in model.component_data_objects(Constraint, active=True)
            )
            # Quad constraints: try Gurobi API for exact count, fallback 0
            try:
                gb = getattr(opt, "_solver_model", None) or getattr(opt, "_solver", None)
                solver_meta["num_quad_constr"] = int(gb.NumQConstrs) if (
                    gb is not None and hasattr(gb, "NumQConstrs")
                ) else 0
            except Exception:
                solver_meta["num_quad_constr"] = 0
            # Final relative MIP gap: Pyomo's SolverResults doesn't carry this for
            # Gurobi, so read it directly off the native Gurobi model (MIPGap is
            # only meaningful once a solve has produced an incumbent + bound).
            try:
                gb = getattr(opt, "_solver_model", None) or getattr(opt, "_solver", None)
                if gb is not None and hasattr(gb, "MIPGap"):
                    solver_meta["mip_gap"] = float(gb.MIPGap)
            except Exception:
                pass
        except Exception:
            pass
        solver_meta["status"] = str(
            getattr(getattr(solver_result, "solver", None), "status", "unknown")
        )
        solver_meta["termination_condition"] = str(
            getattr(getattr(solver_result, "solver", None), "termination_condition", "unknown")
        )
        # Matched-effort T-GAP fields (2026-09-08): the file-based Gurobi interface keeps
        # no live model (gb is None -> mip_gap above stays unset), but Pyomo's SolverResults
        # DOES carry the bound/incumbent + runtime. Record incumbent, best_bound, gap, runtime
        # so every campaign row reports the same 5 figures (incumbent, bound, gap, runtime, status).
        try:
            _prob = getattr(solver_result, "problem", None)
            _lb = getattr(_prob, "lower_bound", None) if _prob is not None else None
            _ub = getattr(_prob, "upper_bound", None) if _prob is not None else None
            _lb = None if _lb is None else float(_lb)
            _ub = None if _ub is None else float(_ub)
            if _lb is not None and _lb not in (float("inf"), float("-inf")):
                solver_meta["best_bound"] = _lb
            if _ub is not None and _ub not in (float("inf"), float("-inf")):
                solver_meta["incumbent"] = _ub
            if (_lb is not None and _ub is not None and abs(_ub) > 1e-9
                    and _ub not in (float("inf"),) and _lb not in (float("-inf"),)):
                solver_meta["mip_gap"] = abs(_ub - _lb) / abs(_ub)
        except Exception:
            pass
        try:
            _slv = getattr(solver_result, "solver", None)
            _rt = getattr(_slv, "wallclock_time", None) or getattr(_slv, "time", None)
            if _rt is not None:
                solver_meta["runtime_s"] = float(_rt)
        except Exception:
            pass
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

            # Additional hints for fix-and-relax infeasibility
            if binary_vals is not None:
                logger.error(
                    "[FIX-RELAX] QCP infeasible with fixed binaries from MILP. "
                    "Possible causes:\n"
                    "  - Bilinear Q = m_dot * cp * dT constraints incompatible with "
                    "fixed pipe regime buckets\n"
                    "  - Temperature bounds violated when T propagates through pipes\n"
                    "  - Consumer return temp assumptions inconsistent with NLP physics\n"
                    "  Try: relax terminal_policy to 'free' or increase storage bounds"
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
                try:
                    out_dir = Path(cfg.get("output", {}).get("export_dir", "output/results"))
                    out_solver_dir = out_dir / "solver"
                    out_solver_dir.mkdir(parents=True, exist_ok=True)
                    iis_path = out_solver_dir / "gurobi_infeasible.ilp"
                    grb_model.write(str(iis_path))
                    logger.error("IIS model written to %s", iis_path)
                    solver_meta["iis_file"] = str(iis_path)
                except Exception as write_err:
                    logger.debug("Could not write IIS model file: %s", write_err)
                solver_meta["iis_constraints"] = iis_constraints
                solver_meta["iis_bounds"] = iis_bounds
            except Exception as iis_err:
                logger.error("IIS computation failed: %s", iis_err)
                try:
                    out_dir = Path(cfg.get("output", {}).get("export_dir", "output/results"))
                    out_solver_dir = out_dir / "solver"
                    out_solver_dir.mkdir(parents=True, exist_ok=True)
                    lp_path = out_solver_dir / "infeasible_model.lp"
                    model.write(str(lp_path), io_options={"symbolic_solver_labels": True})
                    solver_meta["infeasible_model_lp"] = str(lp_path)
                    logger.error("Infeasible model snapshot written to %s", lp_path)
                except Exception as lp_err:
                    logger.error("Failed to write infeasible model snapshot: %s", lp_err)

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

        # Full-solution dump for the complete-MIP-start UC seed (main path; mirrors the
        # Stage-A dump). 2026-09-07, made UNCONDITIONAL 2026-09-26 (K1, docs SS4be):
        # every successful solve now persists its full solution by default (not just when
        # CALION_DUMP_VARS happens to be set) so a later run can warmstart from a COMPLETE
        # prior solution instead of the partial CSV-column-inferred binary hints that
        # _apply_warmstart uses -- that partial path was the confirmed root cause of the
        # SB-S0-HK0 seeded re-run's "User MIP start did not produce a new incumbent solution"
        # (only 17,520 of 1,208,895 binaries were hinted, everything else left for Gurobi's
        # own subMIP repair, which failed within its internal budget). CALION_DUMP_VARS still
        # works as an override for a custom/additional path.
        import os as _os_dm
        import json as _js
        _o, _Tt = {}, 0
        for _vv in model.component_objects(pyo.Var, active=True):
            _dd = {str(_i): float(_vv[_i].value) for _i in _vv if _vv[_i].value is not None}
            if _dd:
                _o[_vv.name] = _dd
                _Tt = max(_Tt, len(_dd))
        _dump_payload = _js.dumps({"T": _Tt, "vars": _o})
        _default_export_dir = Path(cfg.get('output', {}).get(
            'export_dir', resolve_runs_dir() + '/thermal_network_results'
        ))
        try:
            _default_export_dir.mkdir(parents=True, exist_ok=True)
            _default_dump_path = _default_export_dir / "full_solution_dump.json"
            _default_dump_path.write_text(_dump_payload, encoding="utf-8")
            logger.info("[SEED-DUMP] persisted full solution (%d var components, T=%d) -> %s",
                        len(_o), _Tt, _default_dump_path)
        except Exception as _dump_err:
            logger.warning("[SEED-DUMP] could not persist default full_solution_dump.json: %s",
                           _dump_err)
        _dm = _os_dm.environ.get("CALION_DUMP_VARS")
        if _dm:
            Path(_dm).write_text(_dump_payload, encoding="utf-8")
            logger.info("[SEED-DUMP] (CALION_DUMP_VARS override) wrote %d var components (T=%d) -> %s",
                        len(_o), _Tt, _dm)

        # ─── Log solution quality for fix-and-relax ───────────────────
        if binary_vals is not None:
            obj_val = pyo.value(model.obj) if hasattr(model, 'obj') else None
            logger.info(
                "[FIX-RELAX] Stage B solved successfully! "
                "Objective = %s, Termination = %s",
                f"{obj_val:.2f}" if obj_val is not None else "N/A",
                solver_meta["termination_condition"],
            )

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
