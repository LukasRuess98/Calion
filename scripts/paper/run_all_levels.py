"""
Phase 2 — Run all three model levels and save outputs.

Usage:
    python scripts/paper/run_all_levels.py

Runs L1, L2, L3 sequentially using PF_ONLY mode.
Outputs go to outputs/paper/L1/, L2/, L3/.
Prints a timing summary at the end.
"""
import sys
import time
from pathlib import Path

# Ensure repo root is on path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from calion.run.workflow import run_workflow
from calion.run.export import export_workflow_results
from calion.logging_config import get_logger

logger = get_logger(__name__)

CONFIGS = [
    ("L1", "configs/paper/L1_copperplate_dispatch.yaml"),
    ("L2", "configs/paper/L2_simplified_dispatch.yaml"),
    # ("L3", "configs/paper/L3_detailed_dispatch.yaml"),
    # NOTE: L3 temporarily disabled due to pre-solve infeasibility (known issue with scale)
    # Will be re-enabled after constraint review
]
OUTPUT_BASE = ROOT / "outputs" / "paper"


def run_level(tag: str, config_path: str) -> dict:
    cfg_path = ROOT / config_path
    outdir   = OUTPUT_BASE / tag
    outdir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Running %s — %s", tag, config_path)
    logger.info("Output: %s", outdir)

    t0 = time.perf_counter()
    workflow = run_workflow([str(cfg_path)])
    t_solve = time.perf_counter() - t0

    logger.info("%s solve time: %.1f s", tag, t_solve)

    t1 = time.perf_counter()
    export_workflow_results(workflow, outdir=str(outdir))
    t_export = time.perf_counter() - t1

    logger.info("%s export time: %.1f s", tag, t_export)

    # Extract key stats for summary
    result = workflow.pf_result
    obj_val = 0.0
    if result and result.summary:
        obj = result.summary.get("objective", {})
        obj_val = float(obj.get("OBJ_value_EUR", 0.0))

    return {
        "tag":        tag,
        "config":     config_path,
        "solve_s":    round(t_solve, 1),
        "export_s":   round(t_export, 1),
        "obj_eur":    obj_val,
        "outdir":     str(outdir),
    }


def main():
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    results = []
    total_t0 = time.perf_counter()

    for tag, cfg_path in CONFIGS:
        try:
            stats = run_level(tag, cfg_path)
            stats["status"] = "OK"
        except Exception as exc:
            logger.error("FAILED %s: %s", tag, exc, exc_info=True)
            stats = {"tag": tag, "config": cfg_path, "status": f"FAILED: {exc}",
                     "solve_s": 0, "obj_eur": 0}
        results.append(stats)

    total_s = time.perf_counter() - total_t0

    # Print summary
    print("\n" + "=" * 65)
    print("BASELINE RUN SUMMARY")
    print("=" * 65)
    print(f"{'Level':<6} {'Status':<12} {'Solve [s]':>10} {'Obj. cost [EUR]':>18}")
    print("-" * 65)
    for r in results:
        print(f"  {r['tag']:<4}  {r.get('status','?'):<12} "
              f"{r.get('solve_s', 0):>10.1f}  "
              f"{r.get('obj_eur', 0):>18,.0f}")
    print("-" * 65)
    print(f"  Total wall time: {total_s:.1f} s")
    print("=" * 65)

    # Quick copperplate error calculation
    objs = {r["tag"]: r.get("obj_eur", 0) for r in results if r.get("status") == "OK"}
    if "L1" in objs and objs["L1"] > 0:
        for tag in ["L2", "L3"]:
            if tag in objs:
                delta_pct = (objs[tag] - objs["L1"]) / objs["L1"] * 100
                print(f"  Copperplate error ({tag} vs L1): {delta_pct:+.2f}%")

    any_failed = any(r.get("status", "").startswith("FAILED") for r in results)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
