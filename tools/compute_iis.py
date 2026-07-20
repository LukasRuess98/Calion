import gurobipy as gp
import sys

lp_file = "output/paper2_runs/solver/infeasible_model.lp"
print(f"Reading {lp_file}")
m = gp.read(lp_file)
m.setParam("InfUnbdInfo", 1)
m.setParam("DualReductions", 0)
m.setParam("OutputFlag", 0)
m.optimize()

if m.status == gp.GRB.INFEASIBLE:
    print("Model is INFEASIBLE. Computing IIS...")
    m.computeIIS()
    iis_constrs = [c for c in m.getConstrs() if c.IISConstr]
    iis_lb_vars = [v for v in m.getVars() if v.IISLB]
    iis_ub_vars = [v for v in m.getVars() if v.IISUB]
    print(f"IIS: {len(iis_constrs)} constraints, {len(iis_lb_vars)} LB vars, {len(iis_ub_vars)} UB vars")
    print("\nIIS Constraints:")
    for c in iis_constrs:
        print(f"  {c.ConstrName}  sense={c.Sense}  rhs={c.RHS}")
    print("\nIIS LB violations:")
    for v in iis_lb_vars:
        print(f"  LB {v.VarName} >= {v.LB}")
    print("\nIIS UB violations:")
    for v in iis_ub_vars:
        print(f"  UB {v.VarName} <= {v.UB}")
    m.write("output/paper2_runs/solver/iis.ilp")
    print("\nIIS written to output/paper2_runs/solver/iis.ilp")
else:
    print(f"Model status: {m.status}")
