"""Parallel driver for the value-saturation probe (Stadtbach, full-mesh fidelity).

The single-process probe runs points sequentially; Stadtbach's full-mesh L3+
MILP needs ~hours/point to converge, so we run the points CONCURRENTLY (one
subprocess per energy level, bounded pool) and merge afterwards. Each subprocess
writes an isolated per-tag CSV (`--out-tag e<E>`) and its own solve artefacts
(`output/paper2_value_probe/VPROBE_..._e<E>/`), so there is no write contention.

Concurrency is capped well below the box limit: solve-phase RAM spikes far above
build-phase (a documented trap on this host), so 4×8 threads (of 66 CPUs, 206 GB)
leaves real headroom. Bump --concurrency only after watching steady-state RAM.

Usage:
    python scripts/paper_2/value_probe_parallel.py SB-S1-HK0 \
        --energies 0,100,200,400,800,1600 --concurrency 4 --threads 8 \
        --time-limit 86400 --mip-gap 0.02
    python scripts/paper_2/value_probe_parallel.py SB-S1-HK0 --merge   # merge only
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
RESULTS = _ROOT / "results"
PROBE = _ROOT / "scripts" / "paper_2" / "value_saturation_probe.py"
LOGDIR = _ROOT / "output"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("value_probe_parallel")


def _tag(e: float) -> str:
    return f"e{e:g}"


def _network_of(scenario_id: str) -> str:
    from scripts.paper_2.main_result_loader import load_main_result
    return load_main_result(scenario_id)["network"]


def merge(scenario_id: str, energies: list[float]) -> Path:
    network = _network_of(scenario_id)
    frames = []
    for e in energies:
        f = RESULTS / f"value_probe_{network}_{scenario_id}__{_tag(e)}.csv"
        if f.exists():
            frames.append(pd.read_csv(f))
        else:
            logger.warning("missing per-point CSV: %s", f.name)
    if not frames:
        raise FileNotFoundError("no per-point CSVs found to merge")
    df = pd.concat(frames, ignore_index=True).sort_values("E_mwh").reset_index(drop=True)
    if "OPEX_annual_eur_per_a" in df.columns:
        df["marginal_value_eur_per_a_per_mwh"] = (
            -df["OPEX_annual_eur_per_a"].diff() / df["E_mwh"].diff()).round(1)
    out = RESULTS / f"value_probe_{network}_{scenario_id}.csv"
    df.to_csv(out, index=False)
    logger.info("Merged %d point(s) -> %s", len(frames), out)
    print(df.to_string(index=False))
    return out


def run(scenario_id: str, energies: list[float], concurrency: int, threads: int,
        time_limit: int, mip_gap: float, relax_commitment: bool = True) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    logger.info("Parallel probe %s: %d points, concurrency=%d, threads=%d/solve, "
                "TimeLimit=%ds, MIPGap=%.3f", scenario_id, len(energies), concurrency,
                threads, time_limit, mip_gap)
    pending = list(energies)
    running: list[tuple[float, subprocess.Popen, object]] = []
    while pending or running:
        while pending and len(running) < concurrency:
            e = pending.pop(0)
            log = open(LOGDIR / f"value_probe_{scenario_id}_{_tag(e)}.log", "w")
            cmd = [sys.executable, str(PROBE), scenario_id,
                   "--energies", f"{e:g}",
                   "--out-tag", _tag(e), "--time-limit", str(time_limit),
                   "--threads", str(threads), "--mip-gap", str(mip_gap)]
            if relax_commitment:
                cmd.append("--relax-commitment")
            p = subprocess.Popen(cmd, cwd=str(_ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
            running.append((e, p, log))
            logger.info("  launched E=%g MWh (pid=%s), %d running / %d pending",
                        e, p.pid, len(running), len(pending))
            time.sleep(30)  # stagger build phases so 4 don't peak RAM simultaneously
        # reap
        still = []
        for e, p, log in running:
            if p.poll() is None:
                still.append((e, p, log))
            else:
                log.close()
                logger.info("  DONE E=%g MWh exit=%s (%d running / %d pending)",
                            e, p.returncode, len(still), len(pending))
        running = still
        time.sleep(20)
    logger.info("All points finished; merging.")
    merge(scenario_id, energies)


def main() -> None:
    ap = argparse.ArgumentParser(description="Parallel value-saturation probe driver")
    ap.add_argument("scenario_id")
    ap.add_argument("--energies", type=str, default="0,100,200,400,800,1600")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--time-limit", type=int, default=86400)
    ap.add_argument("--mip-gap", type=float, default=0.02)
    ap.add_argument("--merge", action="store_true", help="merge existing per-point CSVs only")
    ap.add_argument("--no-relax-commitment", action="store_true",
                    help="do NOT relax generator min_load (keep full UC MILP; use for Memmingen)")
    args = ap.parse_args()
    energies = sorted({float(x) for x in args.energies.split(",")})
    if args.merge:
        merge(args.scenario_id, energies)
        return
    run(args.scenario_id, energies, args.concurrency, args.threads,
        args.time_limit, args.mip_gap, relax_commitment=not args.no_relax_commitment)


if __name__ == "__main__":
    main()
