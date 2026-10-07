"""Compute IIS for the saved infeasible_model.lp using Gurobi directly."""
import sys
from pathlib import Path

LP_PATH = Path("output/paper2_runs/solver/infeasible_model.lp")

try:
    import gurobipy as gp
except ImportError:
    print("gurobipy not available")
    sys.exit(1)

if not LP_PATH.exists():
    print(f"LP file not found: {LP_PATH}")
    sys.exit(1)

print(f"Loading: {LP_PATH} ({LP_PATH.stat().st_size / 1e6:.1f} MB)")
m = gp.read(str(LP_PATH))

print(f"Model: {m.NumVars} vars, {m.NumConstrs} constraints, {m.NumQConstrs} qconstrs")

print("Optimizing to confirm infeasibility...")
m.setParam("OutputFlag", 0)
m.setParam("DualReductions", 0)  # distinguish infeasible from unbounded
m.setParam("TimeLimit", 60)
m.optimize()

if m.Status in (3, 4):  # INFEASIBLE or INF_OR_UNBD
    print("Confirmed infeasible. Computing IIS...")
    m.computeIIS()
    iis_path = LP_PATH.parent / "infeasible_model.ilp"
    m.write(str(iis_path))
    print(f"IIS written to {iis_path}")
    # Print IIS summary
    print(f"\nIIS has {m.IISNumConstrs} constraints, {m.IISNumVars} variables")
    print("\n--- IIS Constraints ---")
    for c in m.getConstrs():
        if c.IISConstr:
            print(f"  {c.ConstrName}: {c.Sense} {c.RHS}")
    print("\n--- IIS Bounds ---")
    for v in m.getVars():
        if v.IISLB:
            print(f"  LB: {v.VarName} >= {v.LB}")
        if v.IISUB:
            print(f"  UB: {v.VarName} <= {v.UB}")
elif m.Status == 2:
    print(f"Model is FEASIBLE! ObjVal = {m.ObjVal:.2f}")
else:
    print(f"Unexpected status: {m.Status}")
