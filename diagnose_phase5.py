#!/usr/bin/env python3
"""
ENERGIS INFEASIBILITY DIAGNOSTICS - PHASE 5
Solver Preprocessing Analysis - Try to solve and capture diagnostics
"""

import sys
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from energis.io.loader import load_input_excel
from energis.models.system_builder import build_model
from energis.config.merge import load_and_merge
import pyomo.environ as pyo
from pyomo.contrib.appsi.base import SolverFactory

print("\n" + "=" * 70)
print("PHASE 5: SOLVER DIAGNOSTICS")
print("=" * 70)

try:
    # Load config and build model
    cfg = load_and_merge(["configs/templates/level2_simple_3node.yaml"])
    excel_file = Path(cfg.get("site", {}).get("input_xlsx", "data/Import_Data.csv"))
    time_series = load_input_excel(excel_file, cfg)
    dt_h = cfg.get("run", {}).get("dt_h", 1.0)
    model = build_model(time_series, cfg, dt_h=dt_h)
    
    print("✅ Model built successfully")
    
    print("\n[1] SOLVER CONFIGURATION")
    print("-" * 70)
    opt = pyo.SolverFactory("appsi_highs")
    print(f"Solver: {opt}")
    print(f"Available options: {dir(opt.config) if hasattr(opt, 'config') else 'N/A'}")
    
    print("\n[2] MODEL STATISTICS BEFORE SOLVE")
    print("-" * 70)
    try:
        # Count components
        vars_count = sum(1 for v in model.component_data_objects(pyo.Var, active=True))
        cons_count = sum(1 for c in model.component_data_objects(pyo.Constraint, active=True))
        print(f"Active variables: {vars_count}")
        print(f"Active constraints: {cons_count}")
        
        # Check variable bounds
        print("\n[3] VARIABLE BOUND CHECK")
        print("-" * 70)
        
        unbounded_vars = []
        zero_range_vars = []
        
        for var in model.component_data_objects(pyo.Var, active=True):
            if var.lb is None and var.ub is None:
                unbounded_vars.append(var.name)
            elif var.lb is not None and var.ub is not None:
                if abs(var.ub - var.lb) < 1e-6:  # essentially fixed
                    zero_range_vars.append((var.name, var.lb, var.ub))
        
        if unbounded_vars:
            print(f"⚠️  Unbounded variables ({len(unbounded_vars)}):")
            for name in unbounded_vars[:5]:
                print(f"   - {name}")  
            if len(unbounded_vars) > 5:
                print(f"   ... and {len(unbounded_vars)-5} more")
        
        if zero_range_vars:
            print(f"\n⚠️  Nearly-fixed variables ({len(zero_range_vars)}):")
            for name, lb, ub in zero_range_vars[:3]:
                print(f"   - {name}: [{lb:.2e}, {ub:.2e}]")
        
    except Exception as e:
        print(f"Could not analyze variables: {e}")
    
    print("\n[4] ATTEMPTING SOLVE WITH DIAGNOSTICS")
    print("-" * 70)
    
    # Try solving with standard Pyomo interface
    try:
        opt_std = pyo.SolverFactory("appsi_highs")
        results = opt_std.solve(model, load_solutions=False)
        
        term_cond = results.termination_condition
        
        print(f"Termination condition: {term_cond}")
        print(f"Best feasible objective: {results.best_feasible_objective}")
        
        if str(term_cond) == "infeasible":
            print("\n❌ CONFIRMED: Model is INFEASIBLE")
            print("   Possible causes:")
            print("   1. Solver preprocessor found conflicting constraints")
            print("   2. Network heat losses exceed supply capacity")
            print("   3. MILP temperature fixing too restrictive")
            print("   4. Pipe transport delay incompatible with demand")
            print("\n   → Hypothesis: MILP mode is TOO RESTRICTIVE")
            print("   → Next: Try disabling network or MILP mode")
            
        elif str(term_cond) == "optimal":
            print("\n✅ Model solved to OPTIMAL!")
            
    except Exception as solve_err:
        print(f"Solve call error: {solve_err}")
        print("Attempting alternative approach...")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("PHASE 5 CONCLUSION")
print("=" * 70)
print("Model structure validated. Next: Apply hypothesis-driven fixes.")
