"""Achieved MIP gaps of all perfect-foresight runs (run_metadata.json) and of the rolling-horizon windows
(window_solver.csv), summarised per run set. Absolute gap = objective − best bound [EUR/a].

    python -m scripts.dhn_study.central_tes.solver_gaps
Output: results/central_tes/solver_gaps/{solver_gaps_runs.csv, solver_gaps_summary.csv, rh_window_gaps.csv}
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C


def _set(rel: Path) -> str:
    p = rel.parts
    if p[0] == "scenario_runs":
        return f"factorial PF, Mode {'H' if p[1].endswith('-H') else 'E'}"
    if p[0] == "sensitivities":
        return {"X": "X/X4/XR/XN", "X4": "X/X4/XR/XN", "XR": "X/X4/XR/XN", "XN": "X/X4/XR/XN"}.get(p[1], f"sensitivity {p[1]}")
    if p[0] == "hosting":
        return "hosting"
    return p[0]


def collect(r: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(r.rglob("run_metadata.json")):
        rel = f.parent.relative_to(r)
        if rel.parts[0] not in ("scenario_runs", "sensitivities", "hosting"):
            continue
        si = json.loads(f.read_text()).get("solver_info", {})
        if not si or not np.isfinite(si.get("bound", np.nan)):
            continue
        mode = "H" if any(s.endswith("-H") for s in rel.parts) else "E"
        rows.append({"set": _set(rel), "run": str(rel), "mode": mode, "status": si.get("status"),
                     "objective_EUR": si["objective"], "bound_EUR": si["bound"], "gap_rel": si["gap"],
                     "gap_abs_EUR": abs(si["objective"] - si["bound"]), "runtime_s": si.get("runtime_s")})
    return pd.DataFrame(rows)


def rh_windows(r: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(r.rglob("window_solver.csv")):
        w = pd.read_csv(f)
        rows.append({"run": str(f.parent.relative_to(r)), "windows": len(w), "gap_rel_max": w["gap"].max(),
                     "gap_rel_median": w["gap"].median(), "gap_abs_max_EUR": (w["objective"] - w["bound"]).abs().max(),
                     "gap_abs_median_EUR": (w["objective"] - w["bound"]).abs().median(),
                     "gap_abs_sum_EUR": (w["objective"] - w["bound"]).abs().sum(),
                     "not_optimal": int((~w["status"].str.contains("optimal")).sum())})
    return pd.DataFrame(rows)


def summary(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby(["set", "mode"])
    return pd.DataFrame({"runs": g.size(), "gap_rel_max": g["gap_rel"].max(), "gap_rel_median": g["gap_rel"].median(),
                         "gap_abs_max_kEUR": g["gap_abs_EUR"].max() / 1e3, "gap_abs_median_kEUR": g["gap_abs_EUR"].median() / 1e3,
                         "not_optimal": g["status"].apply(lambda s: int((~s.str.contains("optimal")).sum()))}).reset_index()


def main():
    cfg = C.load()
    r = C.root() / cfg["paths"]["results"]
    out = r / "solver_gaps"
    out.mkdir(parents=True, exist_ok=True)
    d = collect(r)
    d.to_csv(out / "solver_gaps_runs.csv", index=False)
    s = summary(d)
    s.to_csv(out / "solver_gaps_summary.csv", index=False)
    w = rh_windows(r)
    w.to_csv(out / "rh_window_gaps.csv", index=False)
    pd.set_option("display.width", 200)
    print(s.round(6).to_string(index=False))
    print(w.round(6).to_string(index=False))


if __name__ == "__main__":
    main()
