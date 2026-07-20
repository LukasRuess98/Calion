"""
run_synth_copperplate.py
========================
Runs all 36 L1-copperplate synthetic configs and extracts artefacts to
output/paper_runs/synth/<config>_L1cp/

These runs provide the true copperplate baseline for the topology gap
comparison (L1cp → L3) in the synthetic generalizability study.

Estimated time: ~50-150 s per run (single node, no thermal network)
                ~1.5 h total serial,  ~25 min with 4 workers

Usage:
    python tools/run_synth_copperplate.py                 # all 36 configs
    python tools/run_synth_copperplate.py --workers 4     # parallel
    python tools/run_synth_copperplate.py --dry-run       # preview only
    python tools/run_synth_copperplate.py --resume        # skip completed runs
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SYNTH_CONFIGS = ROOT / "synth_configs"
OUT_BASE      = ROOT / "output" / "paper_runs" / "synth"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dump_yaml(cfg: dict, path: Path) -> None:
    import yaml

    class _IndentedDumper(yaml.Dumper):
        def increase_indent(self, flow=False, **_):
            return super().increase_indent(flow=flow, indentless=False)

    path.write_text(
        yaml.dump(cfg, Dumper=_IndentedDumper, allow_unicode=True,
                  default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _run_one(yaml_path: Path, run_id: str, outdir: Path) -> dict:
    """Run a single copperplate config and extract artefacts."""
    from calion.run.workflow import run_workflow
    from scripts.paper.extract_artefacts import extract_all

    start = time.time()
    tmp = yaml_path.parent / f"_tmp_L1cp_{uuid.uuid4().hex[:8]}.yaml"
    try:
        # Write temp copy (run_workflow may mutate state)
        cfg = _load_yaml(yaml_path)
        _dump_yaml(cfg, tmp)

        wf = run_workflow([str(tmp)])
        elapsed = time.time() - start

        outdir.mkdir(parents=True, exist_ok=True)
        extract_all(
            run_id=run_id,
            config_path=str(yaml_path),
            workflow=wf,
            solve_time_s=elapsed,
            outdir=outdir,
        )

        # Write meta.json
        meta = {
            "run_id":       run_id,
            "config_path":  str(yaml_path),
            "solve_time_s": round(elapsed, 2),
            "model_class":  "MILP-copperplate",
            "wall_clock":   time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        try:
            obj = getattr(wf, "objective_value", None) or getattr(wf, "objective", None)
            if obj is not None:
                meta["objective"] = float(obj)
        except Exception:
            pass
        (outdir / "meta.json").write_text(json.dumps(meta, indent=2))

        return {"run_id": run_id, "status": "ok", "elapsed_s": round(elapsed, 1)}

    except Exception as e:
        return {"run_id": run_id, "status": "error", "error": str(e),
                "traceback": traceback.format_exc()}
    finally:
        if tmp.exists():
            tmp.unlink()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel workers (default: 1 = serial)")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--resume",   action="store_true",
                        help="Skip runs where economics.csv already exists")
    args = parser.parse_args()

    configs = sorted(SYNTH_CONFIGS.glob("synth_*_L1cp.yaml"))
    if not configs:
        print(f"[ERROR] No *_L1cp.yaml found in {SYNTH_CONFIGS}")
        print("  Run first: python tools/gen_synth_copperplate.py")
        sys.exit(1)

    # Build job list
    jobs = []
    for yaml_path in configs:
        run_id = yaml_path.stem          # e.g.  synth_n05_L15p0km_hi0p1_s12h_L1cp
        outdir = OUT_BASE / run_id
        if args.resume and (outdir / "economics.csv").exists():
            print(f"  [SKIP] {run_id}  (already complete)")
            continue
        jobs.append((yaml_path, run_id, outdir))

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}L1-Copperplate synthetic runs")
    print(f"  Configs : {len(configs)}")
    print(f"  To run  : {len(jobs)}")
    print(f"  Workers : {args.workers}")
    print(f"  Output  : {OUT_BASE}")

    if args.dry_run:
        for yp, rid, od in jobs:
            print(f"  [DRY] {rid}  -> {od}")
        return

    if not jobs:
        print("  Nothing to do.")
        return

    # --- Serial ---
    if args.workers == 1:
        results = []
        for i, (yp, rid, od) in enumerate(jobs, 1):
            print(f"\n[{i}/{len(jobs)}] {rid}", flush=True)
            t0 = time.time()
            r = _run_one(yp, rid, od)
            elapsed = time.time() - t0
            status = r["status"]
            if status == "ok":
                print(f"  -> done in {elapsed:.0f}s", flush=True)
            else:
                print(f"  -> ERROR: {r.get('error','?')}", flush=True)
            results.append(r)

    # --- Parallel ---
    else:
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as exe:
            futures = {exe.submit(_run_one, yp, rid, od): rid
                       for yp, rid, od in jobs}
            done = 0
            for fut in concurrent.futures.as_completed(futures):
                done += 1
                rid = futures[fut]
                try:
                    r = fut.result()
                except Exception as e:
                    r = {"run_id": rid, "status": "error", "error": str(e)}
                results.append(r)
                status = r["status"]
                t = r.get("elapsed_s", "?")
                print(f"  [{done}/{len(jobs)}] {rid}  {status}  {t}s", flush=True)

    # --- Summary ---
    ok  = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] != "ok"]
    print(f"\n=== Done: {len(ok)}/{len(results)} successful ===")
    if err:
        print(f"  {len(err)} ERRORS:")
        for r in err:
            print(f"    {r['run_id']}: {r.get('error','?')}")
    else:
        print("  All runs completed successfully.")
        print()
        print("  Next step:")
        print("    python scripts/paper/synth_gap_analysis.py")


if __name__ == "__main__":
    main()
