"""
run_synth_parallel.py
=====================
Parallelized synthetic run orchestrator. Replaces the sequential phase 4
loop in run_paper_full.py by distributing (config, level) jobs across N
worker processes.

Usage:
    python scripts/paper/run_synth_parallel.py              # auto workers
    python scripts/paper/run_synth_parallel.py --workers 8  # explicit
    python scripts/paper/run_synth_parallel.py --workers 8 --threads-per-worker 4
    python scripts/paper/run_synth_parallel.py --levels L3  # only L3 level
    python scripts/paper/run_synth_parallel.py --after-cleanup  # delete L3 dirs first, then run

After all jobs finish:
    python scripts/paper/synth_gap_analysis.py
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SYNTH_DIR  = ROOT / "synth_configs"
SYNTH_OUT  = ROOT / "output" / "paper_runs" / "synth"

# ── Physics hierarchy (must be import-safe, so defined here redundantly) ──────
SYNTH_PHYSICS_PARALLEL = {
    "L1": {
        "network": {"physics": {"heat_loss": False, "pressure_drop": False, "transport_delay": False}}
    },
    "L2": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False}}
    },
    "L3": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": False}}
    },
    "L3plus": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True}}
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_yaml(path: Path) -> dict:
    import yaml
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return yaml.safe_load(path.read_text(encoding=enc)) or {}
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Cannot decode {path}")


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


# ── Worker function (runs in subprocess) ──────────────────────────────────────

def _run_job(job: dict) -> dict:
    """Execute one (yaml_path, level) job. Returns result dict."""
    import time as _time
    yaml_path  = Path(job["yaml_path"])
    level      = job["level"]
    run_id     = job["run_id"]
    outdir     = Path(job["outdir"])
    physics    = job["physics_override"]
    n_threads  = job["gurobi_threads"]

    t0 = _time.perf_counter()
    outdir.mkdir(parents=True, exist_ok=True)

    # Inject Gurobi thread limit into solver options
    thread_override = {"run": {"solver_options": {"Threads": n_threads}}}
    override = _deep_merge(physics, thread_override)

    # Build temp config
    cfg = _load_yaml(yaml_path)
    cfg = _deep_merge(cfg, override)
    tmp = yaml_path.parent / f"_tmp_{yaml_path.stem}_{uuid.uuid4().hex[:8]}.yaml"
    _dump_yaml(cfg, tmp)

    try:
        from calion.run.workflow import run_workflow
        wf = run_workflow([str(tmp)])
        elapsed = _time.perf_counter() - t0

        from scripts.paper.extract_artefacts import extract_all
        extract_all(
            run_id=run_id,
            config_path=str(yaml_path),
            workflow=wf,
            solve_time_s=elapsed,
            outdir=outdir,
        )
        return {"run_id": run_id, "status": "ok", "elapsed_s": round(elapsed, 1)}

    except Exception as exc:
        elapsed = _time.perf_counter() - t0
        return {"run_id": run_id, "status": "error", "error": str(exc),
                "elapsed_s": round(elapsed, 1)}
    finally:
        if tmp.exists():
            tmp.unlink()


# ── Job discovery ──────────────────────────────────────────────────────────────

def _discover_jobs(levels_filter: list[str] | None, skip_nl: bool) -> list[dict]:
    """Return list of pending (config, level) job dicts."""
    synth_yamls = sorted(
        p for p in SYNTH_DIR.glob("synth_*.yaml")
        if "_L1cp" not in p.stem and not p.stem.startswith("_")
    )
    levels = levels_filter or list(SYNTH_PHYSICS_PARALLEL.keys())

    jobs = []
    for yaml_path in synth_yamls:
        synth_id = yaml_path.stem
        for level in levels:
            if level not in SYNTH_PHYSICS_PARALLEL:
                continue
            run_id = f"{synth_id}_{level}"
            outdir = SYNTH_OUT / run_id
            if outdir.exists() and (outdir / "meta.json").exists():
                continue  # already done
            jobs.append({
                "yaml_path":       str(yaml_path),
                "level":           level,
                "run_id":          run_id,
                "outdir":          str(outdir),
                "physics_override": copy.deepcopy(SYNTH_PHYSICS_PARALLEL[level]),
                "gurobi_threads":  4,  # set per-worker below
            })
    return jobs


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel synthetic run orchestrator")
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of parallel workers (default: auto from RAM)")
    parser.add_argument("--threads-per-worker", type=int, default=None,
                        help="Gurobi threads per worker (default: auto)")
    parser.add_argument("--levels", nargs="+", default=None,
                        help="Only run specific levels, e.g. --levels L3")
    parser.add_argument("--after-cleanup", action="store_true",
                        help="Delete all *_L3 dirs first (wrong physics), then run")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show jobs but don't execute")
    args = parser.parse_args()

    # ── Auto-size workers based on available RAM ───────────────────────────────
    try:
        import psutil
        ram_gb = psutil.virtual_memory().available / 1e9
    except ImportError:
        ram_gb = 40.0  # conservative fallback

    ram_per_worst = 3.5  # GB (L3plus peak)
    auto_workers  = max(1, min(16, int(ram_gb // ram_per_worst)))
    n_workers     = args.workers or auto_workers

    phys_cores    = os.cpu_count() or 4
    n_threads     = args.threads_per_worker or max(2, phys_cores // n_workers)

    print("=" * 60)
    print("run_synth_parallel.py")
    print("=" * 60)
    print(f"  Workers:              {n_workers}")
    print(f"  Gurobi threads/worker:{n_threads}")
    print(f"  RAM available:        {ram_gb:.0f} GB")

    # ── Optional cleanup of wrong-physics L3 dirs ─────────────────────────────
    if args.after_cleanup:
        deleted = []
        for d in sorted(SYNTH_OUT.iterdir()):
            if d.is_dir() and d.name.endswith("_L3"):
                shutil.rmtree(d)
                deleted.append(d.name)
        print(f"\n[CLEANUP] Deleted {len(deleted)} *_L3 directories")

    # ── Discover pending jobs ──────────────────────────────────────────────────
    jobs = _discover_jobs(args.levels, skip_nl=True)

    if not jobs:
        print("\n[INFO] No pending jobs — all runs already complete.")
        return

    # Assign thread count
    for j in jobs:
        j["gurobi_threads"] = n_threads

    # Level count summary
    from collections import Counter
    level_counts = Counter(j["level"] for j in jobs)
    print(f"\n  Pending jobs: {len(jobs)}")
    for lvl, cnt in sorted(level_counts.items()):
        print(f"    {lvl}: {cnt}")

    if args.dry_run:
        print("\n[DRY] Would run the above jobs. Exiting.")
        return

    # ── Run in parallel ────────────────────────────────────────────────────────
    print(f"\n[RUN] Starting {n_workers} workers ...\n")
    t_start = time.perf_counter()
    results = []
    done = 0

    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = {pool.submit(_run_job, job): job for job in jobs}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            done += 1
            status = "[OK]" if res["status"] == "ok" else "[ERR]"
            mins   = res["elapsed_s"] / 60
            print(f"  {status} {done}/{len(jobs)}  {res['run_id']}  ({mins:.1f} min)",
                  flush=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_elapsed = time.perf_counter() - t_start
    ok_count  = sum(1 for r in results if r["status"] == "ok")
    err_count = len(results) - ok_count
    print(f"\n[DONE] {ok_count}/{len(results)} jobs succeeded "
          f"({total_elapsed/60:.1f} min wall time)")

    if err_count:
        print(f"[WARN] {err_count} jobs failed:")
        for r in results:
            if r["status"] != "ok":
                print(f"  {r['run_id']}: {r.get('error', '?')}")

    # ── Save results log ──────────────────────────────────────────────────────
    log_path = ROOT / "output" / "paper_runs" / "synth_parallel_log.json"
    log_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"  Log: {log_path}")


if __name__ == "__main__":
    main()
