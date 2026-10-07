"""Step-6 campaign queue (2026-09-21): core S1/S2/S3, break-even, regret, interaction, BC-SB rerun.

Runs every job through scripts/paper_2/run_mm_s4_reconcile.py (isolated output dir per tag, per-run
export dir, mandatory integrity check inside scenario_runner). Dependencies: a seeded job waits for
its seed job (S0 with CALION_DUMP_VARS) and then starts from the S0 incumbent
(CALION_WARMSTART_DUMP + CALION_SEED_FILL_ZERO = complete MIP start, tank in the no-build state).

Usage (detached):   ( python scripts/paper_2/run_step6_queue.py > output/mm_s4_reconcile/step6_queue.log 2>&1 ) & disown
Options:            --dry   print plan only        --resume   skip jobs whose result already exists
Status:             output/mm_s4_reconcile/step6_status.json  (updated every poll)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "output" / "mm_s4_reconcile"
SEEDS = RECON / "seeds"
STATUS = RECON / ("step6_status_regret2.json" if "--regret2" in sys.argv else "step6_status.json")

# slots per network (4 solver threads each) and resource guards
MAX_SLOTS = {"SB": 4, "MM": 4}
MIN_FREE_RAM_GB = {"SB": 45.0, "MM": 20.0}
MIN_FREE_DISK_GB = 15.0
POLL_S = 30


def J(name, scen, net, *, tl, gap, needs=(), seed_out=None, seeded_from=None, env=None,
      after_all=False):
    return dict(name=name, tag=f"s6_{name}", scen=scen, net=net, tl=tl, gap=gap, needs=list(needs),
                seed_out=seed_out, seeded_from=seeded_from, env=dict(env or {}), after_all=after_all)


def build_jobs():
    S = lambda n: str(SEEDS / n)
    jobs = [
        # ── phase 0: S0 incumbents that double as seeds and as comparators ─────────────────────
        J("seed_MM_S0HK0", "MM-S0-HK0", "MM", tl=7200, gap=0.005, seed_out=S("MM_S0_HK0.json")),
        J("seed_MM_S0HK2", "MM-S0-HK2", "MM", tl=7200, gap=0.005, seed_out=S("MM_S0_HK2.json")),
        J("seed_SB_S0HK0", "SB-S0-HK0", "SB", tl=14400, gap=0.01, seed_out=S("SB_S0_HK0.json")),
        # ── (b) regret: ONE fixed practical size per network, no seed (fixed tank != inheritance) ─
        J("mm_S2HK0_fix1.1", "MM-S2-HK0", "MM", tl=5400, gap=0.005, env={"CALION_TES_FIX_MWH": "1.1"}),
        J("sb_S2HK0_fix219", "SB-S2-HK0", "SB", tl=14400, gap=0.01, env={"CALION_TES_FIX_MWH": "219"}),
    ]
    # ── (a) core: S1/S2/S3 endogenous (investable, ladder incl. rung 0), seeded with S0-HK0 ─────
    for s in ("S1", "S2", "S3"):
        jobs.append(J(f"mm_{s}HK0", f"MM-{s}-HK0", "MM", tl=7200, gap=0.005,
                      needs=["seed_MM_S0HK0"], seeded_from=S("MM_S0_HK0.json")))
        jobs.append(J(f"sb_{s}HK0", f"SB-{s}-HK0", "SB", tl=14400, gap=0.01,
                      needs=["seed_SB_S0HK0"], seeded_from=S("SB_S0_HK0.json")))
    # ── (c) break-even: S2-HK0, tank cost anchor c0 x 0.7 / 0.5 / 0.3 (100% = core S2 run) ──────
    for f in ("0.7", "0.5", "0.3"):
        pct = int(round(float(f) * 100))
        jobs.append(J(f"mm_S2HK0_c{pct}", "MM-S2-HK0", "MM", tl=7200, gap=0.005,
                      needs=["seed_MM_S0HK0"], seeded_from=S("MM_S0_HK0.json"),
                      env={"CALION_TES_C0_SCALE": f}))
        jobs.append(J(f"sb_S2HK0_c{pct}", "SB-S2-HK0", "SB", tl=14400, gap=0.01,
                      needs=["seed_SB_S0HK0"], seeded_from=S("SB_S0_HK0.json"),
                      env={"CALION_TES_C0_SCALE": f}))
    # ── (d) interaction (MM only): S2 with the strongest heat curve, vs S0-HK2 and S2-HK0 ────────
    jobs.append(J("mm_S2HK2", "MM-S2-HK2", "MM", tl=7200, gap=0.005,
                  needs=["seed_MM_S0HK2"], seeded_from=S("MM_S0_HK2.json")))
    # ── last in the queue: BC-SB rerun (valid time series; acceptance test of the export fix) ──
    jobs.append(J("sb_BC-SB", "BC-SB", "SB", tl=14400, gap=0.01, after_all=True))
    return jobs


def regret2_jobs():
    """Regret runs with the UNIFORM rule (author 2026-09-21): V = annual heat demand / 365 (model output of the
    S0-HK0 seed runs), rounded to the nearest ladder rung, both networks. Unseeded (fixed tank != inheritance)."""
    import pandas as pd
    import yaml
    g = yaml.safe_load(open(ROOT / "configs/paper_2/storage_geometry.yaml", encoding="utf-8"))["storage_geometry"]["per_asset"]
    jobs = []
    for net, tag, scen, asset, name, tl, gap in (("MM", "seed_MM_S0HK0", "MM-S0-HK0", "tes_main", "mm_S2HK0_fix{}", 5400, 0.005),
                                                 ("SB", "seed_SB_S0HK0", "SB-S0-HK0", "tes_sb", "sb_S2HK0_fix{}", 14400, 0.01)):
        h = pd.read_csv(RECON / f"s6_{tag}" / "runs" / scen / "dispatch_hourly.csv")
        day = float(h.Q_demand_total_MW.sum()) / 365.0
        rung = min([x for x in g[asset]["discrete_energies_mwh"] if x > 0], key=lambda x: abs(x - day))
        jobs.append(J(name.format(f"{rung:g}"), scen.replace("S0", "S2"), net, tl=tl, gap=gap,
                      env={"CALION_TES_FIX_MWH": f"{rung:g}"}))
    return jobs


def free_ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().available / 2**30
    except Exception:  # noqa: BLE001
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong), ("tp", ctypes.c_ulonglong),
                        ("ap", ctypes.c_ulonglong), ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong),
                        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        ms = MS(); ms.l = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return ms.ap / 2**30


def free_disk_gb() -> float:
    return shutil.disk_usage(str(ROOT)).free / 2**30


def result_dir(job) -> Path:
    return RECON / job["tag"] / "runs" / job["scen"]


def result_ok(job) -> bool:
    d = result_dir(job)
    try:
        m = json.load(open(d / "meta.json"))
        return (m.get("obj_eur") is not None) and (d / "economics.csv").exists() \
            and (d / "node_heat_audit.json").exists() and not (d / "FAILED_INTEGRITY.txt").exists()
    except Exception:  # noqa: BLE001
        return False


def launch(job) -> subprocess.Popen:
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONPATH": ".", "CALION_ATMOSPHERIC_TES": "1",
                "CALION_TIMELIMIT": str(job["tl"]), "CALION_MIPGAP": str(job["gap"])})
    if job["seed_out"]:
        env["CALION_DUMP_VARS"] = job["seed_out"]
    if job["seeded_from"]:
        env["CALION_WARMSTART_DUMP"] = job["seeded_from"]
        env["CALION_SEED_FILL_ZERO"] = "1"
    env.update(job["env"])
    (RECON / job["tag"]).mkdir(parents=True, exist_ok=True)
    out = open(RECON / f"{job['tag']}.out", "w", encoding="utf-8")
    return subprocess.Popen([sys.executable, "scripts/paper_2/run_mm_s4_reconcile.py", job["tag"], job["scen"]],
                            cwd=str(ROOT), env=env, stdout=out, stderr=subprocess.STDOUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--regret2", action="store_true", help="only the two uniform-rule regret jobs (demand/365 -> nearest rung)")
    a = ap.parse_args()
    jobs = regret2_jobs() if a.regret2 else build_jobs()
    SEEDS.mkdir(parents=True, exist_ok=True)
    if a.dry:
        for j in jobs:
            print(f"{j['name']:20s} {j['scen']:12s} {j['net']} tl={j['tl']} gap={j['gap']} needs={j['needs']} "
                  f"seed_out={bool(j['seed_out'])} seeded={bool(j['seeded_from'])} env={j['env']} after_all={j['after_all']}")
        print(len(jobs), "jobs"); return
    state = {j["name"]: "pending" for j in jobs}
    if a.resume:
        for j in jobs:
            if result_ok(j):
                state[j["name"]] = "done"
    procs: dict[str, subprocess.Popen] = {}
    t0 = time.time()
    while True:
        # reap finished
        for name, p in list(procs.items()):
            if p.poll() is not None:
                job = next(x for x in jobs if x["name"] == name)
                state[name] = "done" if result_ok(job) else "failed"
                del procs[name]
        running_net = {"SB": 0, "MM": 0}
        for name in procs:
            running_net[next(x for x in jobs if x["name"] == name)["net"]] += 1
        # start ready jobs
        for job in jobs:
            n = job["name"]
            if state[n] != "pending":
                continue
            if any(state[d] == "failed" for d in job["needs"]):
                state[n] = "blocked"; continue
            if any(state[d] != "done" for d in job["needs"]):
                continue
            if job["after_all"] and any(s in ("pending", "running") for k, s in state.items() if k != n):
                continue
            if running_net[job["net"]] >= MAX_SLOTS[job["net"]]:
                continue
            if free_ram_gb() < MIN_FREE_RAM_GB[job["net"]] or free_disk_gb() < MIN_FREE_DISK_GB:
                continue
            procs[n] = launch(job); state[n] = "running"; running_net[job["net"]] += 1
            print(f"[{time.strftime('%H:%M:%S')}] START {n} ({job['scen']})", flush=True)
            time.sleep(20)  # stagger the memory-heavy build phases
        STATUS.write_text(json.dumps({"updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                                      "elapsed_h": round((time.time() - t0) / 3600, 2),
                                      "free_ram_gb": round(free_ram_gb(), 1), "free_disk_gb": round(free_disk_gb(), 1),
                                      "jobs": state}, indent=1), encoding="utf-8")
        if not procs and all(s in ("done", "failed", "blocked") for s in state.values()):
            break
        time.sleep(POLL_S)
    print("QUEUE FINISHED", state, flush=True)


if __name__ == "__main__":
    main()
