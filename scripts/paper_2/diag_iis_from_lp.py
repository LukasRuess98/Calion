"""Fast-path D3(c)/(d) diagnostic: computeIIS() directly on an already-written infeasible LP
snapshot (calion.run.solver already writes one to <export_dir>/solver/infeasible_model.lp on any
infeasible solve). Avoids the slow Python-side gurobi_persistent.set_instance() rebuild -- reading
the LP natively and running IIS should be much faster for a pure LP-level infeasibility (root
relaxation infeasible, not integer-specific).

Usage: python scripts/paper_2/diag_iis_from_lp.py <path/to/infeasible_model.lp>
"""
import sys

import gurobipy as gp

path = sys.argv[1]
print(f"[iis] reading {path} ...")
m = gp.read(path)
print(f"[iis] model: {m.NumConstrs} constrs, {m.NumVars} vars, {m.NumBinVars} binary")
m.Params.IISMethod = 0  # default heuristic; 0=auto picks a fast method
m.Params.Threads = 16
print("[iis] computing IIS ...")
m.computeIIS()
constrs = [c.ConstrName for c in m.getConstrs() if c.IISConstr]
bounds = [(v.VarName, v.IISLB, v.IISUB) for v in m.getVars() if v.IISLB or v.IISUB]
print(f"[iis] IIS constraints ({len(constrs)}):")
for c in constrs[:200]:
    print(f"    {c}")
print(f"[iis] IIS variable bounds ({len(bounds)}):")
for name, lb, ub in bounds[:100]:
    print(f"    {name}  IISLB={lb} IISUB={ub}")
out = path.replace(".lp", "_IIS.ilp")
m.write(out)
print(f"[iis] IIS written to {out}")
