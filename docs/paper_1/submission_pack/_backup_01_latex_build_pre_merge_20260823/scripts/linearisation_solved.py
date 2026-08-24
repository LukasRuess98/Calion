"""
Solved temperature-linearisation error (Paper 1, advancement #3, R2.3).

The full-year native nonconvex QCP is intractable (no incumbent within the solver's 1800 s QCP
cap), so we solve the native reference on representative winter and summer weeks. For each window
the MILP twin (T2P3, PWL temperature) is solved, ALL binaries are fixed, and the native-
temperature QCP (milp_linearize=false, only the heat-loss bilinear differs) is re-solved. Both
share the operating point (100/50 heating curve, dp 0.6) and the same integer schedule, so the
objective difference is a directly SOLVED bound on the temperature-linearisation error --
replacing the forward/decomposition estimate previously reported in tab_linearisation.

    lin_error_pct = (cost_native - cost_milp) / cost_milp * 100

Both the native incumbent and its QCP optimality gap (from the solver log) are reported: the
incumbent gives lin_error at the incumbent; the native lower bound gives the conservative edge.

Reads the native economics.csv (Stage-B native cost) and recovers each window's Stage-A MILP
objective + native QCP gap from the calion run log. Output: results/v2/analysis/
linearisation_solved.csv + console.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

WT = Path("../paper1_faithful_c19d690")
A = Path("results/v2/analysis")
TASKDIR = Path(r"C:/Users/LKR/AppData/Local/Temp/4/claude/c--Users-LKR-Documents-GitHub-Energy-Framwork-Planing-Framework-for-Heat/7ddb987a-9163-4830-9016-d5c6ce47b065/tasks")

# window label -> (native output dir, calion run-log task file)
WINDOWS = {
    "winter": ("output/paper1_v2/T2P3_native_w3_winter", "bzf6vp47c.output"),
    "autumn": ("output/paper1_v2/T2P3_native_w3_autumn", "b7wenj7mz.output"),
}


def _native_cost(run_dir):
    """Native model objective = Model_OBJ_value_EUR in costs.json (same objective definition as
    the MILP twin's Gurobi objective; the reduced OBJ_value_EUR omits CO2 and is NOT comparable)."""
    d = json.loads((WT / run_dir / "costs.json").read_text())["PF"]
    return float(d["Model_OBJ_value_EUR"])


def _parse_log(task_file):
    """Recover Stage-A MILP objective and the final native QCP incumbent/bound/gap from the log.
    The MILP twin (Stage A) writes to console (no LogFile); the native QCP writes both. The FIRST
    'Best objective ... gap' after 'Stage A: Solving MILP' is the MILP; the LAST is the native."""
    txt = (TASKDIR / task_file).read_text(errors="ignore").replace("\x00", "")
    milp_obj = None
    m = re.search(r"Stage A: Solving MILP.*?Best objective ([\d.eE+]+), best bound", txt, re.S)
    if m:
        milp_obj = float(m.group(1))
    qcp = re.findall(r"Best objective ([\d.eE+]+), best bound ([\d.eE+]+), gap ([\d.eE+-]+)%", txt)
    nat_inc = nat_bound = nat_gap = None
    if len(qcp) >= 2:  # [0] is the MILP stage; take the LAST for the native QCP
        nat_inc, nat_bound, nat_gap = (float(x) for x in qcp[-1])
    return milp_obj, nat_inc, nat_bound, nat_gap


def main():
    rows = []
    missing = []
    for w, (run_dir, task) in WINDOWS.items():
        costs = WT / run_dir / "costs.json"
        if not costs.exists():
            missing.append(w)
            continue
        c_nat = _native_cost(run_dir)
        milp_obj, nat_inc, nat_bound, nat_gap = _parse_log(task)
        lin_inc = (c_nat - milp_obj) / milp_obj * 100 if milp_obj else float("nan")
        lin_bound = (nat_bound - milp_obj) / milp_obj * 100 if (milp_obj and nat_bound) else float("nan")
        rows.append({"window": w, "cost_milp_eur": milp_obj, "cost_native_eur": c_nat,
                     "native_lower_bound_eur": nat_bound, "native_qcp_gap_pct": nat_gap,
                     "lin_error_incumbent_pct": lin_inc, "lin_error_bound_pct": lin_bound})
    _ = nat_inc  # native incumbent from log == c_nat (cross-check available)

    if not rows:
        print(f"[wait] no native windows finished yet (missing: {missing})")
        sys.exit(2)

    df = pd.DataFrame(rows)
    A.mkdir(parents=True, exist_ok=True)
    df.to_csv(A / "linearisation_solved.csv", index=False)
    pd.set_option("display.width", 160)
    print("=== Solved temperature-linearisation error, representative weeks (R2.3) ===")
    for _, r in df.iterrows():
        print(f"  [{r['window']:>6}] MILP={r['cost_milp_eur']:,.1f}  native={r['cost_native_eur']:,.1f}  "
              f"(bound {r['native_lower_bound_eur']:,.1f}, QCP gap {r['native_qcp_gap_pct']:.2f}%)")
        print(f"           lin.error = {r['lin_error_incumbent_pct']:+.3f}% (incumbent) "
              f".. {r['lin_error_bound_pct']:+.3f}% (native LB)")
    if missing:
        print(f"  [pending: {missing}]")
    absmax = df[["lin_error_incumbent_pct", "lin_error_bound_pct"]].abs().max().max()
    print(f"  => |linearisation error| <= {absmax:.2f}% across solved windows")
    print("wrote", A / "linearisation_solved.csv")


if __name__ == "__main__":
    main()
