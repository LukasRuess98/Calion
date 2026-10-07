"""Study-G / F2 TES-ladder sweep (2026-09-09) — the co-designed result for a TES scenario
IS the min over the discrete ladder (exact for a discrete set; one sentence in section 2).

For each rung R the model is solved with TES FIXED at R (CALION_TES_FIX_MWH=R), HP + dispatch
free, matched-effort settings (MIPFocus=1, 2h, Cuts=2). Seeding is a HOMOTOPY CLIMB: rung R is
warm-started by the previous (smaller) rung's dumped solution — its SoC ≤ R_prev ≤ R, so it is
feasible for the larger store and injects into the TES-FIXED model (which accepts complete
starts, unlike the investable model). The first climbed rung uses clean_seed (built at v_seed).
Rung 0 (no storage) = the S0 solution by construction, so it is taken from S0's incumbent, not
re-solved. The sweep yields BOTH the scenario result (argmin TAC) AND the F2 sizing curve, and
satisfies the dominance gate automatically (rung 0 ≤ S0).

Usage:
  PYTHONPATH=. python scripts/paper_2/sweep_tes.py MM-S1-HK0 \
      --seed output/uc_seed/MM-S1-HK0/clean_seed.json --seed-rung 2.2 \
      --s0-obj 298691 [--rungs 2.2,3.3,4.3,...] [--timelimit 7200]
Output: output/paper2_sweeps/<scenario>/study_g_<scenario>.csv  (rung_mwh,incumbent,bound,gap,runtime,status)
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
from scripts.paper_2 import scenario_runner as sr  # noqa: E402
import yaml  # noqa: E402


def _ladder_for(scen_id: str) -> list[float]:
    g = yaml.safe_load(open(_ROOT / "configs/paper_2/storage_geometry.yaml", encoding="utf-8"))
    pa = g["storage_geometry"]["per_asset"]
    key = "tes_main" if scen_id.startswith("MM") else "tes_sb"
    return list(pa[key]["discrete_energies_mwh"])


def sweep(scen_id: str, seed: str | None, seed_rung: float, s0_obj: float | None,
          rungs: list[float] | None, timelimit: int) -> Path:
    ladder = _ladder_for(scen_id)
    if rungs is None:
        # climb the rungs >= seed_rung (homotopy needs SoC to fit); ascending
        rungs = [r for r in ladder if r >= seed_rung - 1e-9]
    out = _ROOT / "output" / "paper2_sweeps" / scen_id
    (out / "runs").mkdir(parents=True, exist_ok=True)
    csv_path = out / f"study_g_{scen_id}.csv"
    rows: list[dict] = []
    # rung 0 == S0 (no storage) by construction
    if s0_obj is not None and (not rungs or ladder[0] == 0):
        rows.append({"rung_mwh": 0.0, "incumbent": s0_obj, "bound": "", "gap": "",
                     "runtime_s": 0, "status": "inherited_from_S0"})
    prev_dump = seed
    orig_out = sr.OUT_BASE
    try:
        for R in rungs:
            rdir = out / "runs" / f"r{R:g}"
            rdir.mkdir(parents=True, exist_ok=True)
            this_dump = rdir / "dump.json"
            env = {
                "CALION_TES_FIX_MWH": f"{R}",
                "CALION_MIPFOCUS": "1",
                "CALION_TIMELIMIT": str(timelimit),
                "CALION_DUMP_VARS": str(this_dump),
                "CALION_SEED_FILL_ZERO": "1",
                "PYTHONIOENCODING": "utf-8",
            }
            if prev_dump:
                env["CALION_WARMSTART_DUMP"] = str(prev_dump)
            os.environ.update(env)
            sr.OUT_BASE = rdir
            res = sr.run_all_scenarios(scenario_ids=[scen_id], dry_run=False,
                                       force_rerun=True, gurobi_threads=4)
            # read this rung's meta for T-GAP fields
            mf = rdir / scen_id / "meta.json"
            m = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
            rows.append({
                "rung_mwh": R,
                "incumbent": m.get("obj_eur") or m.get("incumbent"),
                "bound": m.get("best_bound", ""),
                "gap": m.get("mip_gap", ""),
                "runtime_s": m.get("runtime_s", ""),
                "status": m.get("status", (res[0].get("status") if res else "?")),
            })
            # homotopy: next rung climbs from this one IF this dump was produced
            if this_dump.exists():
                prev_dump = this_dump
            # persist after every rung (long campaign — never lose finished rungs)
            _write(csv_path, rows)
            print(f"[sweep {scen_id}] rung {R:g} MWh -> {rows[-1]['incumbent']} "
                  f"({rows[-1]['status']}, gap={rows[-1]['gap']})")
    finally:
        sr.OUT_BASE = orig_out
        for k in ("CALION_TES_FIX_MWH", "CALION_WARMSTART_DUMP", "CALION_DUMP_VARS",
                  "CALION_SEED_FILL_ZERO", "CALION_MIPFOCUS", "CALION_TIMELIMIT"):
            os.environ.pop(k, None)
    _write(csv_path, rows)
    best = min((r for r in rows if isinstance(r["incumbent"], (int, float))),
               key=lambda r: r["incumbent"], default=None)
    if best:
        print(f"[sweep {scen_id}] ARGMIN TAC = {best['incumbent']:,.0f} EUR at {best['rung_mwh']:g} MWh")
    return csv_path


def _write(p: Path, rows: list[dict]) -> None:
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rung_mwh", "incumbent", "bound", "gap", "runtime_s", "status"])
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--seed", default=None)
    ap.add_argument("--seed-rung", type=float, default=0.0)
    ap.add_argument("--s0-obj", type=float, default=None)
    ap.add_argument("--rungs", default=None, help="comma-sep MWh; default = ladder rungs >= seed-rung")
    ap.add_argument("--timelimit", type=int, default=7200)
    a = ap.parse_args()
    rungs = [float(x) for x in a.rungs.split(",")] if a.rungs else None
    sweep(a.scenario, a.seed, a.seed_rung, a.s0_obj, rungs, a.timelimit)
