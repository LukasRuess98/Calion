"""
Quick IIS diagnostic: load the saved infeasible_model.lp and compute IIS.
This avoids rebuilding the model and directly uses the saved LP.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]

LP_PATH = ROOT / "output/results/solver/infeasible_model.lp"
IIS_PATH = ROOT / "output/validation/debug_iis.ilp"
IIS_PATH.parent.mkdir(parents=True, exist_ok=True)

if not LP_PATH.exists():
    print(f"LP file not found: {LP_PATH}")
    sys.exit(1)

print(f"Loading LP: {LP_PATH}")

try:
    import gurobipy as gp
    from gurobipy import GRB

    env = gp.Env(empty=True)
    env.setParam("OutputFlag", 1)
    env.start()

    m = gp.read(str(LP_PATH), env)
    print(f"Model loaded: {m.NumVars} vars, {m.NumConstrs} constrs, {m.NumQConstrs} quad constrs")

    # Disable presolve and dual reductions so IIS works properly
    m.setParam("Presolve", 0)
    m.setParam("DualReductions", 0)
    m.setParam("NonConvex", 2)
    m.setParam("TimeLimit", 60)
    m.setParam("OutputFlag", 0)

    m.optimize()
    status = m.Status
    print(f"Gurobi status: {status} (INFEASIBLE={GRB.INFEASIBLE})")

    if status == GRB.INFEASIBLE:
        print("Model is infeasible — computing IIS...")
        m.computeIIS()

        print("\n=== IIS Constraints (first 50) ===")
        iis_constrs = []
        for c in m.getConstrs():
            if c.IISConstr:
                iis_constrs.append(c.ConstrName)
        for name in iis_constrs[:50]:
            print(f"  {name}")
        print(f"  ... ({len(iis_constrs)} total)")

        iis_qconstrs = []
        for qc in m.getQConstrs():
            if qc.IISQConstr:
                iis_qconstrs.append(qc.QCName)
        if iis_qconstrs:
            print(f"\n=== IIS Quad Constraints ===")
            for name in iis_qconstrs[:20]:
                print(f"  {name}")

        print("\n=== IIS Variable Bounds ===")
        iis_lb = []
        iis_ub = []
        for v in m.getVars():
            if v.IISLB:
                iis_lb.append(f"LB({v.VarName})={v.LB}")
            if v.IISUB:
                iis_ub.append(f"UB({v.VarName})={v.UB}")
        for b in (iis_lb + iis_ub)[:30]:
            print(f"  {b}")

        m.write(str(IIS_PATH))
        print(f"\nIIS written to: {IIS_PATH}")

    elif status == GRB.OPTIMAL:
        print("Model is FEASIBLE (optimal) — not infeasible!")
    else:
        print(f"Unexpected status: {status}")

except ImportError:
    print("gurobipy not available — trying via pyomo...")
    sys.exit(1)
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
