"""
auto_cleanup_and_rerun.py
=========================
Waits for the current background synth run to finish, then:
  1. Deletes all *_L3 directories (produced with wrong physics: pressure_drop=False)
  2. Re-runs phase 4 with corrected physics (only L3 will re-run; everything else skips)
  3. Runs synth_gap_analysis.py
  4. Regenerates the 3 synth gap figures

Run with:
    python scripts/paper/auto_cleanup_and_rerun.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYNTH_DIR = ROOT / "output" / "paper_runs" / "synth"
PYTHON = sys.executable

EXPECTED_LEVELS = ["L1", "L2", "L3plus"]   # L3 will be deleted; L1cp already done
N_BASE_CONFIGS = 36


def _count_completed(suffix: str) -> int:
    return sum(1 for d in SYNTH_DIR.iterdir()
               if d.is_dir() and d.name.endswith(suffix)
               and "_L1cp" not in d.name and "_L1net" not in d.name
               and (d / "meta.json").exists())


def _wait_for_completion(poll_secs: int = 120) -> None:
    """Poll until all 36 base configs have L1, L2, L3plus completed."""
    print("[WAIT] Watching for background run to complete...", flush=True)
    while True:
        l1_done    = _count_completed("_L1")
        l2_done    = _count_completed("_L2")
        l3p_done   = _count_completed("_L3plus")
        l3_done    = _count_completed("_L3")
        print(f"  L1={l1_done}/36  L2={l2_done}/36  L3={l3_done}/36  L3plus={l3p_done}/36",
              flush=True)

        if l1_done >= N_BASE_CONFIGS and l2_done >= N_BASE_CONFIGS and l3p_done >= N_BASE_CONFIGS:
            print(f"[WAIT] All L1/L2/L3plus complete — proceeding.", flush=True)
            return

        print(f"  Still running — next check in {poll_secs}s", flush=True)
        time.sleep(poll_secs)


def _delete_l3_dirs() -> int:
    """Delete all *_L3 run directories (wrong physics)."""
    deleted = []
    for d in sorted(SYNTH_DIR.iterdir()):
        if d.is_dir() and d.name.endswith("_L3"):
            shutil.rmtree(d)
            deleted.append(d.name)
    print(f"[CLEAN] Deleted {len(deleted)} _L3 directories:", flush=True)
    for name in deleted[:5]:
        print(f"  {name}", flush=True)
    if len(deleted) > 5:
        print(f"  ... and {len(deleted) - 5} more", flush=True)
    return len(deleted)


def _run(cmd: list[str], label: str) -> int:
    print(f"\n[RUN] {label}", flush=True)
    print(f"  $ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"[ERROR] {label} failed (exit {result.returncode})", flush=True)
    else:
        print(f"[OK] {label} finished", flush=True)
    return result.returncode


def _verify_l3_pump_costs() -> None:
    """Spot-check a few L3 runs to confirm pump costs are non-zero (correct physics)."""
    import csv
    checked, passed = 0, 0
    for d in sorted(SYNTH_DIR.iterdir()):
        if not (d.is_dir() and d.name.endswith("_L3") and "_L1cp" not in d.name):
            continue
        eco_path = d / "economics.csv"
        if not eco_path.exists():
            continue
        with open(eco_path) as f:
            row = next(csv.DictReader(f))
        pump = float(row.get("cost_pump_eur", 0))
        checked += 1
        if pump > 0:
            passed += 1
        if checked >= 5:
            break
    print(f"\n[VERIFY] Pump cost > 0: {passed}/{checked} L3 runs checked", flush=True)
    if passed < checked:
        print("[WARN] Some L3 runs still show zero pump costs — check physics override!", flush=True)
    else:
        print("[OK] Pressure drop physics confirmed (non-zero pump costs)", flush=True)


def main() -> None:
    print("=" * 60)
    print("auto_cleanup_and_rerun.py")
    print("=" * 60)

    # 1. Wait for background process to finish
    _wait_for_completion(poll_secs=120)

    # 2. Delete all _L3 directories
    n_deleted = _delete_l3_dirs()
    if n_deleted == 0:
        print("[WARN] No _L3 directories found — nothing to delete", flush=True)

    # 3. Re-run L3 only with corrected physics — parallelized
    rc = _run(
        [PYTHON, "scripts/paper/run_synth_parallel.py", "--levels", "L3"],
        "Parallel L3 re-run (corrected physics, pressure_drop=True)",
    )
    if rc != 0:
        print("[ERROR] Re-run failed — aborting pipeline", flush=True)
        sys.exit(rc)

    # 4. Verify pump costs
    _verify_l3_pump_costs()

    # 5. Gap analysis
    _run(
        [PYTHON, "scripts/paper/synth_gap_analysis.py"],
        "Gap analysis",
    )

    # 6. Regenerate figures
    for fig in ["fig_synth_gap_distribution", "fig_synth_gap_direction", "fig_synth_gap_decomp"]:
        _run(
            [PYTHON, f"scripts/paper/figures/{fig}.py"],
            f"Figure: {fig}",
        )

    print("\n[DONE] Full pipeline complete.", flush=True)
    print(f"  Figures saved to: {ROOT / 'output' / 'paper_runs' / 'figures'}", flush=True)


if __name__ == "__main__":
    main()
