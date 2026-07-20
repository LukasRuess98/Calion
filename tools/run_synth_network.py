"""
run_synth_network.py
====================
Runs all 36 synthetic network configs at the L3 physics level and extracts
artefacts to output/paper_runs/synth/<config>_L3/

Physics preset applied (L3):
    heat_loss=True, pressure_drop=False, transport_delay=False

These runs provide the topology-aware baseline for the topology gap comparison
(L1cp -> L3) in the synthetic generalizability study.  The output directories
use the same _L3 suffix expected by synth_gap_analysis.py.

Estimated time: ~3-10 min per run (15-30 node network, full year)
                ~4 h total serial,  ~1 h with 4 workers

Usage:
    python tools/run_synth_network.py                 # all 36 configs
    python tools/run_synth_network.py --workers 4     # parallel
    python tools/run_synth_network.py --dry-run       # preview only
    python tools/run_synth_network.py --resume        # skip completed runs
    python tools/run_synth_network.py --level L3plus  # physics level (default: L3)
"""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
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

# Physics presets — same as SYNTH_PHYSICS in run_paper_full.py
PHYSICS_PRESETS: dict[str, dict] = {
    "L3": {
        "network": {"physics": {
            "heat_loss": True,
            "pressure_drop": False,
            "transport_delay": False,
        }}
    },
    "L3plus": {
        "network": {"physics": {
            "heat_loss": True,
            "pressure_drop": True,
            "transport_delay": True,
        }}
    },
    "L2": {
        "network": {"physics": {
            "heat_loss": True,
            "pressure_drop": False,
            "transport_delay": False,
        }}
    },
    "L1": {
        "network": {"physics": {
            "heat_loss": False,
            "pressure_drop": False,
            "transport_delay": False,
        }}
    },
}


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


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _run_one(yaml_path: Path, run_id: str, outdir: Path,
             physics_override: dict) -> dict:
    """Run a single network config with physics override and extract artefacts."""
    from calion.run.workflow import run_workflow
    from scripts.paper.extract_artefacts import extract_all

    start = time.time()
    tmp = yaml_path.parent / f"_tmp_{uuid.uuid4().hex[:8]}.yaml"
    try:
        cfg = _load_yaml(yaml_path)
        cfg = _deep_merge(cfg, physics_override)
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

        meta = {
            "run_id":           run_id,
            "config_path":      str(yaml_path),
            "solve_time_s":     round(elapsed, 2),
            "model_class":      "MILP-network",
            "physics_override": physics_override,
            "wall_clock":       time.strftime("%Y-%m-%dT%H:%M:%S"),
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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume",  action="store_true",
                        help="Skip runs where economics.csv already exists")
    parser.add_argument("--level",   default="L3",
                        choices=list(PHYSICS_PRESETS.keys()),
                        help="Physics level to apply (default: L3)")
    args = parser.parse_args()

    physics_override = PHYSICS_PRESETS[args.level]

    # All synth configs that are NOT copperplate variants
    configs = sorted(p for p in SYNTH_CONFIGS.glob("synth_*.yaml")
                     if "_L1cp" not in p.stem)
    if not configs:
        print(f"[ERROR] No synth_*.yaml found in {SYNTH_CONFIGS}")
        sys.exit(1)

    jobs = []
    for yaml_path in configs:
        run_id = f"{yaml_path.stem}_{args.level}"
        outdir = OUT_BASE / run_id
        if args.resume and (outdir / "economics.csv").exists():
            print(f"  [SKIP] {run_id}  (already complete)")
            continue
        jobs.append((yaml_path, run_id, outdir))

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Synthetic network runs  (level={args.level})")
    print(f"  Configs : {len(configs)}")
    print(f"  To run  : {len(jobs)}")
    print(f"  Workers : {args.workers}")
    print(f"  Output  : {OUT_BASE}")
    print(f"  Physics : {physics_override}")

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
            r = _run_one(yp, rid, od, physics_override)
            elapsed = time.time() - t0
            if r["status"] == "ok":
                print(f"  -> done in {elapsed:.0f}s", flush=True)
            else:
                print(f"  -> ERROR: {r.get('error','?')}", flush=True)
            results.append(r)

    # --- Parallel ---
    else:
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as exe:
            futures = {exe.submit(_run_one, yp, rid, od, physics_override): rid
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
                t = r.get("elapsed_s", "?")
                print(f"  [{done}/{len(jobs)}] {rid}  {r['status']}  {t}s", flush=True)

    # --- Summary ---
    ok  = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] != "ok"]
    print(f"\n=== Done: {len(ok)}/{len(results)} successful ===")
    if err:
        print(f"  {len(err)} ERRORS:")
        for r in err:
            print(f"    {r['run_id']}: {r.get('error','?')}")
        if any(r.get("traceback") for r in err):
            print("\n  First traceback:")
            for r in err:
                if r.get("traceback"):
                    print(r["traceback"][:1000])
                    break
    else:
        print("  All runs completed successfully.")
        print()
        print("  Next step:")
        print("    python scripts/paper/synth_gap_analysis.py")


if __name__ == "__main__":
    main()
