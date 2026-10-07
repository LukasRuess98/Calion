"""D3(c) diagnostic (2026-09-22): targeted feasRelax on the PRESSURE constraint group only,
for the confirmed-infeasible "C1 alone" full-year MM-BASE-FIX model (CALION_PRESSURE_SLACK_MODE=
preprocessed, CALION_DUMP_MODE unset/legacy). Reads CALION_PRESSURE_SLACK_MODE / CALION_DUMP_MODE
/ CALION_ATMOSPHERIC_TES from the environment exactly like a normal run -- set them before invoking.

Builds the EXACT model scenario_runner would build (reuses its own config-prep code via
run_single_scenario), intercepts right after calion.run.solver.build_model() (before any solve
attempt), attaches gurobi_persistent, and calls Gurobi's native Model.feasRelax(relaxobjtype=0,
minrelax=True, vars=[], lbpen=[], ubpen=[], constrs=<station_dp constraints ONLY>, rhspen=[1]*n)
-- minimizing total relaxation, with EVERY constraint outside that explicit list held hard. Reports
which (node, hour) pairs needed relaxation and by how much.

Usage: PYTHONIOENCODING=utf-8 PYTHONPATH=. CALION_PRESSURE_SLACK_MODE=preprocessed \
       python scripts/paper_2/diag_feasrelax.py <SCEN_ID> [--group pressure|heatbalance]
--group pressure (default): station_dp constraints only (C1 suspect group).
--group heatbalance: ht_balance_* (node heat balance) + *_cap_lo (min-load) constraints (C3
  suspect group, "Waermebilanz/Mindestlast").
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, ".")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


_captured = {}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    scen_id = args[0] if args else "BC-MM"
    group = "pressure"
    if "--group" in sys.argv:
        group = sys.argv[sys.argv.index("--group") + 1]

    import calion.run.solver as solver_mod
    _real_build_model = solver_mod.build_model

    def _capturing_build_model(*a, **kw):
        m = _real_build_model(*a, **kw)
        _captured["model"] = m
        return m  # let the normal (doomed, infeasible) file-based solve run its course --
                  # harmless, we grab our own gurobi_persistent handle on the SAME model after.

    solver_mod.build_model = _capturing_build_model

    from scripts.paper_2 import scenario_runner as sr
    scen_cfg = sr.load_scenarios_config()
    scen = next(s for s in scen_cfg["scenarios"] if s["id"] == scen_id)
    try:
        result = sr.run_single_scenario(scen, scen_cfg, force_rerun=True)
        print(f"[diag] run_single_scenario returned: {result.get('status')} "
             f"(expected: infeasible/no_incumbent -- that path is NOT what we're using)")
    finally:
        solver_mod.build_model = _real_build_model

    model = _captured.get("model")
    if model is None:
        print("ERROR: build_model was never called / not intercepted")
        return

    print(f"[diag] model captured: scenario={scen_id} "
         f"(CALION_PRESSURE_SLACK_MODE={os.environ.get('CALION_PRESSURE_SLACK_MODE')}, "
         f"CALION_DUMP_MODE={os.environ.get('CALION_DUMP_MODE')})")

    import pyomo.environ as pyo
    opt = pyo.SolverFactory("gurobi_persistent")
    opt.set_instance(model)
    grb = opt._solver_model
    grb.setParam("OutputFlag", 1)
    grb.setParam("Threads", 8)
    grb.setParam("TimeLimit", 600)

    if group == "pressure":
        target = [c for c in grb.getConstrs() if "_station_dp(" in c.ConstrName]
    elif group == "heatbalance":
        target = [c for c in grb.getConstrs()
                 if c.ConstrName.startswith("ht_balance_") or "_cap_lo(" in c.ConstrName]
    else:
        raise ValueError(f"unknown --group {group}")
    print(f"[diag] group={group}: {len(target)} constraints found")
    if not target:
        print("[diag] NOTHING to relax -- naming pattern mismatch, aborting")
        return

    rhspen = [1.0] * len(target)
    feasobj = grb.feasRelax(0, True, [], [], [], target, rhspen)
    print(f"[diag] Model.feasRelax return (obj/inf/const): {feasobj}")
    grb.optimize()
    print(f"[diag] feasRelax solve status: {grb.Status}")
    if grb.SolCount > 0:
        print(f"[diag] total relaxation (sum |violation|) = {grb.ObjVal:.4f}")
        art_vars = [v for v in grb.getVars() if v.VarName.startswith(("ArtP_", "ArtN_"))]
        viol = [(v.VarName, v.X) for v in art_vars if abs(v.X) > 1e-6]
        viol.sort(key=lambda x: -abs(x[1]))
        print(f"[diag] nonzero relaxations on station_dp constraints ({len(viol)}):")
        for name, val in viol[:80]:
            print(f"    {name:55s} {val:10.4f}")
        if not viol:
            print("[diag] feasRelax solved with 0 relaxation needed -- station_dp group is "
                 "NOT the infeasibility source (or the artificial-var naming differs in this "
                 "Gurobi version; check grb.getVars() names manually).")
    else:
        print("[diag] feasRelax itself found NO solution -- the pressure group alone cannot "
             "restore feasibility; the true culprit lies OUTSIDE station_dp "
             "(heat balance / min-load / UC most likely). Broaden the relaxable set.")


if __name__ == "__main__":
    main()
