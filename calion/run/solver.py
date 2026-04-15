"""Solver invocation wrapper.

Encapsulates the ``build_model → SolverFactory → solve → extract`` pipeline
so that callers only need to provide a table, config, and solver name.

Enhanced with comprehensive infeasibility diagnosis including Gurobi IIS computation.
"""

from __future__ import annotations

import os
import tempfile
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

try:  # pragma: no cover - optional dependency
    import gurobipy as gp
    HAVE_GUROBI = True
except ImportError:  # pragma: no cover
    HAVE_GUROBI = False
    gp = None


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

def _compute_gurobi_iis(
    model,
    log_file: str | None = None,
    verbose: bool = False
) -> dict[str, Any]:
    """
    Berechnet das Irreducible Infeasible Subsystem (IIS) mit Gurobi.
    
    Das IIS ist die minimale Menge von Constraints, die zusammen infeasible sind.
    Entfernt man eine beliebige Constraint aus dem IIS, wird das Teilproblem feasible.
    
    Args:
        model: Pyomo ConcreteModel
        log_file: Pfad zur Log-Datei
        verbose: Konsolenausgabe
        
    Returns:
        Dict mit IIS-Informationen:
        - iis_file: Pfad zur .ilp Datei
        - iis_constraints: Liste der konfliktierenden Constraints
        - iis_variables: Liste der Variablen mit Bounds-Konflikten
        - success: True wenn IIS berechnet werden konnte

    """
    result = {
        "success": False,
        "iis_file": None,
        "iis_constraints": [],
        "iis_variables": [],
        "error": None
    }
    
    lines = []
    
    def log(msg: str):
        lines.append(msg)
        if verbose:
            print(msg)
    
    log("")
    log("-" * 50)
    log("IIS COMPUTATION (Irreducible Infeasible Subsystem)")
    log("-" * 50)
    
    if not HAVE_GUROBI:
        log("WARNING: gurobipy not available - skipping IIS computation")
        log("Install with: pip install gurobipy")
        result["error"] = "gurobipy not installed"
        
        if log_file:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        return result
    
    lp_path = None
    
    try:
        # 1. Modell als LP exportieren
        log("Step 1: Exporting model to LP format...")
        
        with tempfile.NamedTemporaryFile(suffix=".lp", delete=False, mode='w') as lp_file:
            lp_path = lp_file.name
        
        model.write(lp_path, io_options={"symbolic_solver_labels": True})
        log(f"  Model exported to: {lp_path}")
        
        # Dateigröße prüfen
        file_size_mb = os.path.getsize(lp_path) / (1024 * 1024)
        log(f"  LP file size: {file_size_mb:.2f} MB")
        
        # 2. Mit Gurobi einlesen
        log("")
        log("Step 2: Loading model into Gurobi...")
        grb_model = gp.read(lp_path)
        log(f"  Loaded: {grb_model.NumVars} variables, {grb_model.NumConstrs} constraints")
        
        # 3. IIS berechnen
        log("")
        log("Step 3: Computing IIS (this may take a while)...")
        grb_model.computeIIS()
        log("  IIS computation complete!")
        
        # 4. IIS-Datei speichern
        if log_file:
            iis_dir = os.path.dirname(log_file)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            iis_path = os.path.join(iis_dir, f"IIS_{timestamp}.ilp")
        else:
            iis_path = lp_path.replace(".lp", "_IIS.ilp")
        
        grb_model.write(iis_path)
        result["iis_file"] = iis_path
        log(f"  IIS written to: {iis_path}")
        
        # 5. IIS-Constraints analysieren
        log("")
        log("Step 4: Analyzing IIS...")
        
        iis_constrs = [c for c in grb_model.getConstrs() if c.IISConstr]
        result["iis_constraints"] = [c.ConstrName for c in iis_constrs]
        
        log("")
        log(f"CONFLICTING CONSTRAINTS ({len(iis_constrs)} total):")
        log("-" * 40)
        
        # Gruppiere nach Constraint-Typ für bessere Übersicht
        constr_groups = {}
        for c in iis_constrs:
            # Extrahiere Präfix (z.B. "BOILER_MAIN_cap" aus "BOILER_MAIN_cap[1]")
            name = c.ConstrName
            prefix = name.split("[")[0] if "[" in name else name
            if prefix not in constr_groups:
                constr_groups[prefix] = []
            constr_groups[prefix].append(name)
        
        for prefix, names in sorted(constr_groups.items()):
            if len(names) <= 3:
                for name in names:
                    log(f"  • {name}")
            else:
                log(f"  • {prefix}[...] ({len(names)} constraints)")
                # Zeige erste und letzte
                log(f"      First: {names[0]}")
                log(f"      Last:  {names[-1]}")
        
        # 6. IIS-Variablen (Bounds-Konflikte) analysieren
        iis_vars_lb = [v for v in grb_model.getVars() if v.IISLB]
        iis_vars_ub = [v for v in grb_model.getVars() if v.IISUB]
        
        result["iis_variables"] = {
            "lower_bound": [v.VarName for v in iis_vars_lb],
            "upper_bound": [v.VarName for v in iis_vars_ub]
        }
        
        if iis_vars_lb or iis_vars_ub:
            log("")
            log(f"VARIABLE BOUNDS IN IIS:")
            log("-" * 40)
            
            if iis_vars_lb:
                log(f"  Lower bound conflicts ({len(iis_vars_lb)}):")
                for v in iis_vars_lb[:10]:
                    log(f"    • {v.VarName} >= {v.LB}")
                if len(iis_vars_lb) > 10:
                    log(f"    ... and {len(iis_vars_lb) - 10} more")
            
            if iis_vars_ub:
                log(f"  Upper bound conflicts ({len(iis_vars_ub)}):")
                for v in iis_vars_ub[:10]:
                    log(f"    • {v.VarName} <= {v.UB}")
                if len(iis_vars_ub) > 10:
                    log(f"    ... and {len(iis_vars_ub) - 10} more")
        
        # 7. Interpretation
        log("")
        log("INTERPRETATION:")
        log("-" * 40)
        
        if "cap" in str(constr_groups.keys()).lower():
            log("  → CAPACITY constraints are in conflict!")
            log("    Likely cause: Demand exceeds available capacity")
            log("    Solution: Increase component capacities in YAML config")
        
        if "balance" in str(constr_groups.keys()).lower() or "flow" in str(constr_groups.keys()).lower():
            log("  → BALANCE/FLOW constraints are in conflict!")
            log("    Likely cause: Mass/energy balance cannot be satisfied")
            log("    Solution: Check network topology and connection definitions")
        
        if "pressure" in str(constr_groups.keys()).lower() or "head" in str(constr_groups.keys()).lower():
            log("  → PRESSURE constraints are in conflict!")
            log("    Likely cause: Pump capacity insufficient for network")
            log("    Solution: Increase pump head or reduce network pressure drops")
        
        result["success"] = True
        log("")
        log(f"✓ IIS analysis complete. See {iis_path} for full details.")
        
    except gp.GurobiError as e:
        error_msg = f"Gurobi error: {e}"
        log(f"ERROR: {error_msg}")
        result["error"] = error_msg
        
    except Exception as e:
        error_msg = f"IIS computation failed: {e}"
        log(f"ERROR: {error_msg}")
        import traceback
        log(traceback.format_exc())
        result["error"] = error_msg
        
    finally:
        # Temporäre LP-Datei aufräumen
        if lp_path and os.path.exists(lp_path):
            try:
                os.unlink(lp_path)
            except OSError:
                pass
    
    # Alles in Log-Datei schreiben
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    
    return result


def _analyze_model_structure(
    model,
    log_file: str | None = None,
    verbose: bool = False
) -> dict[str, Any]:
    """
    Analysiert die Modellstruktur auf potenzielle Probleme.
    
    Args:
        model: Pyomo ConcreteModel
        log_file: Pfad zur Log-Datei
        verbose: Konsolenausgabe
        
    Returns:
        Dict mit Analyseergebnissen
    """
    lines = []
    analysis = {
        "statistics": {},
        "potential_issues": [],
        "recommendations": []
    }
    
    def log(msg: str):
        lines.append(msg)
        if verbose:
            print(msg)
    
    log("")
    log("-" * 50)
    log("MODEL STRUCTURE ANALYSIS")
    log("-" * 50)
    
    try:
        # Basis-Statistiken
        n_vars = sum(1 for _ in model.component_data_objects(pyo.Var, active=True))
        n_cons = sum(1 for _ in model.component_data_objects(pyo.Constraint, active=True))
        n_obj = sum(1 for _ in model.component_data_objects(pyo.Objective, active=True))
        
        n_binary = sum(1 for v in model.component_data_objects(pyo.Var, active=True) 
                      if v.is_binary())
        n_integer = sum(1 for v in model.component_data_objects(pyo.Var, active=True) 
                       if v.is_integer() and not v.is_binary())
        n_continuous = n_vars - n_binary - n_integer
        
        analysis["statistics"] = {
            "total_variables": n_vars,
            "binary_variables": n_binary,
            "integer_variables": n_integer,
            "continuous_variables": n_continuous,
            "constraints": n_cons,
            "objectives": n_obj
        }
        
        log("")
        log("STATISTICS:")
        log(f"  Total Variables:    {n_vars:,}")
        log(f"    - Binary:         {n_binary:,}")
        log(f"    - Integer:        {n_integer:,}")
        log(f"    - Continuous:     {n_continuous:,}")
        log(f"  Constraints:        {n_cons:,}")
        log(f"  Objectives:         {n_obj}")
        
        # Constraint-Typen analysieren
        log("")
        log("CONSTRAINT TYPES:")
        
        constr_types = {}
        for c in model.component_objects(pyo.Constraint, active=True):
            name = c.name
            prefix = name.split("_")[0] if "_" in name else name
            count = sum(1 for _ in c)
            if prefix not in constr_types:
                constr_types[prefix] = 0
            constr_types[prefix] += count
        
        for prefix, count in sorted(constr_types.items(), key=lambda x: -x[1])[:15]:
            log(f"  {prefix}: {count:,}")
        
        # Variablen-Bounds prüfen
        log("")
        log("VARIABLE BOUNDS CHECK:")
        
        vars_no_upper = []
        vars_no_lower = []
        vars_fixed = []
        
        for v in model.component_data_objects(pyo.Var, active=True):
            lb = v.lb
            ub = v.ub
            
            if lb is not None and ub is not None and abs(lb - ub) < 1e-10:
                vars_fixed.append(v.name)
            elif ub is None and not v.is_binary():
                vars_no_upper.append(v.name)
            elif lb is None and not v.is_binary():
                vars_no_lower.append(v.name)
        
        log(f"  Fixed variables (lb=ub): {len(vars_fixed):,}")
        log(f"  Variables without upper bound: {len(vars_no_upper):,}")
        log(f"  Variables without lower bound: {len(vars_no_lower):,}")
        
        if vars_no_upper:
            analysis["potential_issues"].append(
                f"{len(vars_no_upper)} variables have no upper bound"
            )
        
        # Zeitschritte ermitteln
        if hasattr(model, 't'):
            n_timesteps = len(list(model.t))
            log(f"  Time steps: {n_timesteps}")
            analysis["statistics"]["timesteps"] = n_timesteps
        
    except Exception as e:
        log(f"Error in structure analysis: {e}")
        analysis["error"] = str(e)
    
    # In Log-Datei schreiben
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    
    return analysis


def _check_demand_vs_capacity(
    model,
    log_file: str | None = None,
    verbose: bool = False
) -> dict[str, Any]:
    """
    Prüft ob die Nachfrage die verfügbare Kapazität übersteigt.
    
    Args:
        model: Pyomo ConcreteModel
        log_file: Pfad zur Log-Datei
        verbose: Konsolenausgabe
        
    Returns:
        Dict mit Demand/Capacity-Analyse
    """
    lines = []
    check = {
        "demands": {},
        "capacities": {},
        "issues": []
    }
    
    def log(msg: str):
        lines.append(msg)
        if verbose:
            print(msg)
    
    log("")
    log("-" * 50)
    log("DEMAND VS. CAPACITY ANALYSIS")
    log("-" * 50)
    
    try:
        # Demand-Parameter suchen
        demand_params = ['demand', 'total_demand', 'heat_demand', 'Q_demand', 
                        'el_demand', 'P_demand', 'load']
        
        total_max_demand = 0
        
        for param_name in demand_params:
            if hasattr(model, param_name):
                param = getattr(model, param_name)
                try:
                    if hasattr(param, '__iter__'):
                        values = []
                        for idx in param:
                            val = pyo.value(param[idx])
                            if val is not None:
                                values.append(val)
                        if values:
                            max_val = max(values)
                            sum_val = sum(values)
                            check["demands"][param_name] = {
                                "max": max_val,
                                "sum": sum_val,
                                "count": len(values)
                            }
                            total_max_demand = max(total_max_demand, max_val)
                            log(f"  {param_name}:")
                            log(f"    Max:   {max_val:,.2f}")
                            log(f"    Sum:   {sum_val:,.2f}")
                            log(f"    Count: {len(values)}")
                except Exception:
                    pass
        
        log("")
        log("CAPACITIES:")
        
        # Capacity-Parameter suchen
        capacity_params = ['capacity', 'max_capacity', 'P_max', 'Q_max', 
                          'cap', 'nominal_capacity']
        
        total_capacity = 0
        
        # Suche nach Komponenten-Kapazitäten
        for comp in model.component_objects(pyo.Var, active=True):
            comp_name = comp.name
            if any(cap_term in comp_name.lower() for cap_term in ['cap', 'qth', 'p_el', 'power']):
                try:
                    for idx in comp:
                        var = comp[idx]
                        ub = var.ub
                        if ub is not None and ub > 0:
                            check["capacities"][f"{comp_name}[{idx}]"] = ub
                            # Nur einmal pro Komponente zählen
                            if idx == list(comp)[0]:
                                total_capacity += ub
                                log(f"  {comp_name}: max = {ub:,.2f}")
                            break
                except Exception:
                    pass
        
        # Parameter-Kapazitäten
        for param in model.component_objects(pyo.Param, active=True):
            param_name = param.name
            if any(cap_term in param_name.lower() for cap_term in ['cap', 'max', 'limit']):
                try:
                    val = pyo.value(param)
                    if val is not None and val > 0:
                        check["capacities"][param_name] = val
                        log(f"  {param_name}: {val:,.2f}")
                except Exception:
                    pass
        
        # Vergleich
        log("")
        log("COMPARISON:")
        log(f"  Max instantaneous demand: {total_max_demand:,.2f}")
        log(f"  Total capacity found:     {total_capacity:,.2f}")
        
        if total_max_demand > 0 and total_capacity > 0:
            ratio = total_capacity / total_max_demand
            log(f"  Capacity/Demand ratio:    {ratio:.2f}")
            
            if ratio < 1.0:
                issue = f"CRITICAL: Capacity ({total_capacity:,.0f}) < Peak Demand ({total_max_demand:,.0f})"
                check["issues"].append(issue)
                log(f"  ⚠️  {issue}")
            elif ratio < 1.1:
                issue = f"WARNING: Capacity margin very tight (ratio={ratio:.2f})"
                check["issues"].append(issue)
                log(f"  ⚠️  {issue}")
            else:
                log(f"  ✓ Capacity appears sufficient")
        
    except Exception as e:
        log(f"Error in demand/capacity check: {e}")
        check["error"] = str(e)
    
    # In Log-Datei schreiben
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    
    return check


def _diagnose_infeasibility(
    model, 
    solver_result, 
    log_file: str | None = None,
    verbose: bool = False
) -> dict[str, Any]:
    """
    Umfassende Diagnose für infeasible Pyomo-Modelle.
    
    Führt mehrere Analysen durch:
    1. Gurobi IIS-Berechnung (wenn verfügbar)
    2. Pyomo Constraint-Verletzungen
    3. Bounds-Verletzungen
    4. Modellstruktur-Analyse
    5. Demand vs. Capacity Check
    6. Troubleshooting-Empfehlungen
    
    Args:
        model: Pyomo ConcreteModel
        solver_result: Ergebnis von opt.solve()
        log_file: Pfad zur Log-Datei (None = kein File-Logging)
        verbose: Wenn True, auch auf Konsole ausgeben
        
    Returns:
        Dict mit allen Diagnose-Ergebnissen
    """
    import sys
    from io import StringIO
    
    diagnosis = {
        "timestamp": datetime.now().isoformat(),
        "solver_status": None,
        "iis": None,
        "structure": None,
        "demand_capacity": None,
        "violated_constraints": [],
        "violated_bounds": [],
        "recommendations": []
    }
    
    lines = []
    
    def log(msg: str):
        lines.append(msg)
        if verbose:
            print(msg)
    
    log("")
    log("=" * 70)
    log("╔══════════════════════════════════════════════════════════════════╗")
    log("║           INFEASIBILITY DIAGNOSIS REPORT                        ║")
    log("╚══════════════════════════════════════════════════════════════════╝")
    log("=" * 70)
    log(f"Timestamp: {diagnosis['timestamp']}")
    
    # ──────────────────────────────────────────────────────────────────
    # 0. SOLVER STATUS
    # ──────────────────────────────────────────────────────────────────
    solver_info = getattr(solver_result, 'solver', None)
    if solver_info:
        status = str(getattr(solver_info, 'status', 'unknown'))
        term_cond = str(getattr(solver_info, 'termination_condition', 'unknown'))
        diagnosis["solver_status"] = {"status": status, "termination": term_cond}
        log(f"Solver Status:      {status}")
        log(f"Termination:        {term_cond}")
    
    # In Log-Datei schreiben (Header)
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        lines = []
    
    # ──────────────────────────────────────────────────────────────────
    # 1. GUROBI IIS COMPUTATION (Most Important!)
    # ──────────────────────────────────────────────────────────────────
    iis_result = _compute_gurobi_iis(model, log_file=log_file, verbose=verbose)
    diagnosis["iis"] = iis_result
    
    # ──────────────────────────────────────────────────────────────────
    # 2. MODEL STRUCTURE ANALYSIS
    # ──────────────────────────────────────────────────────────────────
    structure = _analyze_model_structure(model, log_file=log_file, verbose=verbose)
    diagnosis["structure"] = structure
    
    # ──────────────────────────────────────────────────────────────────
    # 3. DEMAND VS CAPACITY CHECK
    # ──────────────────────────────────────────────────────────────────
    demand_cap = _check_demand_vs_capacity(model, log_file=log_file, verbose=verbose)
    diagnosis["demand_capacity"] = demand_cap
    
    # ──────────────────────────────────────────────────────────────────
    # 4. PYOMO CONSTRAINT VIOLATIONS
    # ──────────────────────────────────────────────────────────────────
    log("")
    log("-" * 50)
    log("PYOMO CONSTRAINT ANALYSIS")
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
            log("Violated constraints (from Pyomo):")
            for line in constraint_output.strip().split("\n")[:30]:
                log(f"  {line}")
                diagnosis["violated_constraints"].append(line)
            if len(constraint_output.strip().split("\n")) > 30:
                log(f"  ... and more (see full output)")
        else:
            log("No constraint violations found by Pyomo")
            log("(This is expected when no solution was found)")
            
    except ImportError:
        log("WARNING: pyomo.util.infeasible not available")
    except Exception as e:
        log(f"Error in Pyomo constraint analysis: {e}")
    
    # ──────────────────────────────────────────────────────────────────
    # 5. BOUNDS VIOLATIONS
    # ──────────────────────────────────────────────────────────────────
    log("")
    log("-" * 50)
    log("BOUNDS VIOLATIONS")
    log("-" * 50)
    
    try:
        from pyomo.util.infeasible import log_infeasible_bounds
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        log_infeasible_bounds(model, tol=1e-6)
        
        bounds_output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        if bounds_output.strip():
            for line in bounds_output.strip().split("\n")[:20]:
                log(f"  {line}")
                diagnosis["violated_bounds"].append(line)
        else:
            log("No bounds violations found")
            
    except Exception as e:
        log(f"Error in bounds analysis: {e}")
    
    # ──────────────────────────────────────────────────────────────────
    # 6. RECOMMENDATIONS
    # ──────────────────────────────────────────────────────────────────
    log("")
    log("-" * 50)
    log("TROUBLESHOOTING RECOMMENDATIONS")
    log("-" * 50)
    log("")
    
    recommendations = []
    
    # Basierend auf IIS-Ergebnissen
    if iis_result.get("success") and iis_result.get("iis_constraints"):
        iis_constrs = iis_result["iis_constraints"]
        
        if any("cap" in c.lower() for c in iis_constrs):
            rec = "1. INCREASE CAPACITY: Some capacity constraints are in the IIS"
            recommendations.append(rec)
            log(rec)
            log("   → Edit YAML: Increase 'capacity' or 'capacity_max' for components")
            log("")
        
        if any("balance" in c.lower() or "flow" in c.lower() for c in iis_constrs):
            rec = "2. CHECK ENERGY BALANCE: Flow/balance constraints are conflicting"
            recommendations.append(rec)
            log(rec)
            log("   → Verify all nodes have sufficient supply")
            log("   → Check network topology for disconnected nodes")
            log("")
        
        if any("pressure" in c.lower() or "head" in c.lower() for c in iis_constrs):
            rec = "3. CHECK HYDRAULICS: Pressure constraints are in conflict"
            recommendations.append(rec)
            log(rec)
            log("   → Increase pump head capacity")
            log("   → Check pipe dimensions and pressure drops")
            log("")
    
    # Basierend auf Demand/Capacity
    if demand_cap.get("issues"):
        rec = "4. CAPACITY INSUFFICIENT: Peak demand exceeds available capacity"
        recommendations.append(rec)
        log(rec)
        log("   → Add more generation capacity")
        log("   → Enable grid import/backup systems")
        log("")
    
    # Allgemeine Empfehlungen
    log("GENERAL DEBUGGING STEPS:")
    log("")
    log("  a) Reduce time horizon for faster testing:")
    log('     horizon: { start: "2025-01-01", end: "2025-01-01 23:00" }')
    log("")
    log("  b) Temporarily relax constraints:")
    log("     - Set min_load: 0 for all components")
    log("     - Increase all capacities by 2x")
    log("     - Remove storage terminal constraints")
    log("")
    log("  c) Check the IIS file for exact conflicting constraints:")
    if iis_result.get("iis_file"):
        log(f"     {iis_result['iis_file']}")
    log("")
    log("  d) Enable verbose solver output:")
    log("     run:")
    log("       verbose_logging: true")
    log("       solver_options:")
    log("         OutputFlag: 1")
    log("")
    
    diagnosis["recommendations"] = recommendations
    
    log("=" * 70)
    log("END OF DIAGNOSIS REPORT")
    log("=" * 70)
    
    # Finale Ausgabe in Log-Datei
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        
        # Info über Log-Datei
        if verbose:
            print(f"\n📄 Full diagnosis saved to: {log_file}")
        if iis_result.get("iis_file"):
            if verbose:
                print(f"📄 IIS file saved to: {iis_result['iis_file']}")
    
    return diagnosis


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
    """
    Löst ein Optimierungsszenario.
    
    Args:
        table: TimeSeriesTable mit Zeitreihendaten
        cfg: Konfigurationsdict aus YAML
        dt_h: Zeitschrittlänge in Stunden
        solver_name: Name des Solvers (z.B. 'gurobi', 'cbc', 'highs')
        soc_init_override: Optionaler Override für initialen Speicher-SOC
        terminal_target_override: Optionaler Override für Terminal-SOC-Target
        
    Returns:
        ScenarioResult mit Zeitreihen, Summary und Solver-Metadaten
    """
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
        "gurobi_available": HAVE_GUROBI,
        "model_built": model is not None,
        "log_file": log_file,
    }
    
    if model is not None and HAVE_PYOMO:
        # Log solver start
        _log_solver_start(log_file, cfg, solver_name, verbose=verbose)
        
        # ══════════════════════════════════════════════════════════════════
        # Check milp_linearize from multiple possible YAML locations
        # ══════════════════════════════════════════════════════════════════
        milp_linearize = (
            cfg.get('thermal_network', {}).get('milp_linearize', False) or
            cfg.get('network', {}).get('physics', {}).get('milp_linearize', False) or
            cfg.get('scenario', {}).get('milp_linearize', False)
        )
        
        lp_only_solvers = ('highs', 'appsi_highs', 'cbc', 'glpk')
        if not milp_linearize and any(s in solver_name.lower() for s in lp_only_solvers):
            warning_msg = (
                f"WARNING: milp_linearize is False but solver '{solver_name}' only supports LP/MILP. "
                "Bilinear terms (m_dot * T) will cause solver failure. "
                "Set thermal_network.milp_linearize: true OR network.physics.milp_linearize: true in your config."
            )
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
            solver_result = opt.solve(model, tee=verbose, load_solutions=load_solutions)
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

        # ══════════════════════════════════════════════════════════════════
        # Check termination condition BEFORE exporting!
        # ══════════════════════════════════════════════════════════════════
        term_cond = solver_meta["termination_condition"].lower()
        
        # Bei Infeasibility: NICHT exportieren, Diagnose starten und Return
        if "infeasible" in term_cond or "unbounded" in term_cond:
            error_msg = (
                f"ERROR: Solver returned {solver_meta['status']}. Model is {term_cond}. "
                "Starting comprehensive infeasibility diagnosis..."
            )
            _write_log(log_file, error_msg, verbose=True)  # Immer auf Konsole bei Fehler
            
            # Run comprehensive infeasibility diagnosis
            diagnosis = _diagnose_infeasibility(
                model, 
                solver_result, 
                log_file=log_file,
                verbose=verbose
            )
            
            # Diagnose-Ergebnisse in solver_meta speichern
            solver_meta["diagnosis"] = diagnosis
            
            # Return OHNE Export (keine Lösung vorhanden!)
            series, summary, costs = _collect_timeseries_and_summary(
                table, cfg, dt_h, None  # None = kein Modell = keine Werte
            )
            return ScenarioResult(table, series, summary, costs, solver_meta)
        
        # ══════════════════════════════════════════════════════════════════
        # NUR bei Erfolg: Lösung laden
        # ══════════════════════════════════════════════════════════════════
        if not load_solutions:
            try:
                model.solutions.load_from(solver_result)
                _write_log(log_file, "Solution loaded successfully", verbose=verbose)
            except Exception as e:
                _write_log(log_file, f"WARNING: Could not load solution: {e}", verbose=verbose)
                # Return ohne Export wenn Lösung nicht geladen werden konnte
                series, summary, costs = _collect_timeseries_and_summary(
                    table, cfg, dt_h, None
                )
                solver_meta["status"] = "error"
                solver_meta["termination_condition"] = f"solution_load_failed: {e}"
                return ScenarioResult(table, series, summary, costs, solver_meta)

        # ══════════════════════════════════════════════════════════════════
        # NUR bei Erfolg: Export (Lösung existiert garantiert)
        # ══════════════════════════════════════════════════════════════════
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

                _write_log(log_file, f"Exported {len(export_files)} files to {export_dir}", verbose=verbose)

                solver_meta['export_files'] = export_files
                solver_meta['export_dir'] = export_dir
                solver_meta['network_data'] = network_data

            except Exception as e:
                _write_log(log_file, f"WARNING: Export failed: {e}", verbose=verbose)
                import traceback
                _write_log(log_file, traceback.format_exc(), verbose=verbose)
        
        # Log success
        _write_log(log_file, f"\n✓ Solver completed successfully in {elapsed_time:.2f}s", verbose=verbose)
                
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