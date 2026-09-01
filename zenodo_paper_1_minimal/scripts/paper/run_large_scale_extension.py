"""
run_large_scale_extension.py
============================
Extends the synthetic sweep with large-network configs (30/50 km) and runs the
full topology/physics ladder for robustness against reviewer attacks on
pipe-length extrapolation.

Default levels:
    L1cp, L1, L2, L3, L3plus

Output:
    output/paper_runs/synth_large_scale_results.csv
        Schema-compatible with output/paper_runs/synth_sweep_results.csv
    output/paper_runs/synth_large_scale_log.json
        Per-job execution status/timing
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SYNTH_DIR = ROOT / "synth_configs"
SYNTH_OUT = ROOT / "output" / "paper_runs" / "synth"
OUT_DIR = ROOT / "output" / "paper_runs"
OUT_RESULTS = OUT_DIR / "synth_large_scale_results.csv"
OUT_LOG = OUT_DIR / "synth_large_scale_log.json"

LARGE_KM = [30.0, 50.0]
N_NODES = [5, 15, 30]
HI = 0.4
STORAGE_H = 6
PEAK_DEMAND_MW = 76.0

LEVELS = ["L1cp", "L1", "L2", "L3", "L3plus"]

PHYSICS = {
    "L1": {"network": {"physics": {"heat_loss": False, "pressure_drop": False, "transport_delay": False}}},
    "L2": {"network": {"physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False}}},
    "L3": {"network": {"physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": False}}},
    "L3plus": {"network": {"physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True}}},
}


class _IndentedDumper(yaml.Dumper):
    def increase_indent(self, flow=False, **_):
        return super().increase_indent(flow=flow, indentless=False)


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _yaml_read(path: Path) -> dict:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return yaml.safe_load(path.read_text(encoding=enc)) or {}
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Cannot decode {path}")


def _yaml_write(cfg: dict, path: Path) -> None:
    path.write_text(
        yaml.dump(
            cfg,
            Dumper=_IndentedDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _config_stem(km: float, n_nodes: int) -> str:
    return (
        f"synth_n{n_nodes:02d}"
        f"_L{str(km).replace('.', 'p')}km"
        f"_hi{str(HI).replace('.', 'p')}"
        f"_s{STORAGE_H}h"
    )


def _generate_large_yamls() -> list[Path]:
    """Generate base and L1cp YAMLs for 30/50-km stress configs."""
    from tools.gen_synth import (
        PEAK_DEMAND_MW as _PEAK,
        _balanced_tree_pipes,
        _gini_allocations,
        build_config,
    )
    from tools.gen_synth_copperplate import _make_copperplate

    created: list[Path] = []
    for km in LARGE_KM:
        for n in N_NODES:
            stem = _config_stem(km, n)
            base_path = SYNTH_DIR / f"{stem}.yaml"
            cp_path = SYNTH_DIR / f"{stem}_L1cp.yaml"

            if not base_path.exists():
                seed = hash((km, n, HI, STORAGE_H)) % (2**31)
                fracs = _gini_allocations(n, HI, seed)
                pipes = _balanced_tree_pipes(n, km, fracs, _PEAK, seed)
                cfg = build_config(
                    {"length_km": km, "hi": HI, "n_nodes": n, "storage_h": STORAGE_H},
                    fracs,
                    pipes,
                )
                _yaml_write(cfg, base_path)
                print(f"  [GEN] {base_path.name}")
            else:
                print(f"  [SKIP-exists] {base_path.name}")

            if not cp_path.exists():
                cp_cfg = _make_copperplate(_yaml_read(base_path), stem)
                _yaml_write(cp_cfg, cp_path)
                print(f"  [GEN] {cp_path.name}")
            else:
                print(f"  [SKIP-exists] {cp_path.name}")

            created.append(base_path)

    return created


def _build_jobs(base_yamls: list[Path], gurobi_threads: int) -> list[dict]:
    jobs: list[dict] = []
    for base_yaml in base_yamls:
        stem = base_yaml.stem
        for level in LEVELS:
            run_id = f"{stem}_{level}"
            outdir = SYNTH_OUT / run_id
            if (outdir / "meta.json").exists():
                continue

            if level == "L1cp":
                yaml_path = base_yaml.parent / f"{stem}_L1cp.yaml"
                override = {}
            else:
                yaml_path = base_yaml
                override = copy.deepcopy(PHYSICS[level])

            jobs.append(
                {
                    "yaml_path": str(yaml_path),
                    "run_id": run_id,
                    "outdir": str(outdir),
                    "override": override,
                    "gurobi_threads": gurobi_threads,
                }
            )
    return jobs


def _run_job(job: dict) -> dict:
    """Run one synthetic config/level and extract standard artefacts."""
    import time as _time

    yaml_path = Path(job["yaml_path"])
    run_id = job["run_id"]
    outdir = Path(job["outdir"])
    override = job["override"]
    n_threads = int(job["gurobi_threads"])

    t0 = _time.perf_counter()
    outdir.mkdir(parents=True, exist_ok=True)

    cfg = _yaml_read(yaml_path)
    cfg = _deep_merge(cfg, override)
    cfg = _deep_merge(cfg, {"run": {"solver_options": {"Threads": n_threads}}})

    tmp = yaml_path.parent / f"_tmp_{yaml_path.stem}_{uuid.uuid4().hex[:8]}.yaml"
    _yaml_write(cfg, tmp)

    try:
        from calion.run.workflow import run_workflow
        from scripts.paper.extract_artefacts import extract_all

        wf = run_workflow([str(tmp)])
        elapsed = _time.perf_counter() - t0
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
        return {
            "run_id": run_id,
            "status": "error",
            "error": str(exc),
            "elapsed_s": round(elapsed, 1),
        }
    finally:
        if tmp.exists():
            tmp.unlink()


def _read_cost_co2(run_dir: Path) -> tuple[float, float]:
    eco = run_dir / "economics.csv"
    if not eco.exists():
        raise FileNotFoundError(f"Missing economics.csv in {run_dir}")
    row = pd.read_csv(eco).iloc[0]
    return float(row["cost_total_eur"]), float(row["co2_total_t"])


def _read_demand_mwh(run_dir: Path) -> float:
    disp = run_dir / "dispatch_hourly.csv"
    if not disp.exists():
        return 0.0
    df = pd.read_csv(disp, parse_dates=["timestamp"])
    if "Q_demand_total_MW" not in df.columns:
        return 0.0
    dt_h = (
        (df["timestamp"].iloc[1] - df["timestamp"].iloc[0]).total_seconds() / 3600
        if len(df) > 1
        else 1.0
    )
    return float(df["Q_demand_total_MW"].sum() * dt_h)


def _chain_ok(values: list[float], tol: float = 0.0) -> bool:
    return all(values[i] <= values[i + 1] * (1.0 + tol) for i in range(len(values) - 1))


def _build_results() -> pd.DataFrame:
    rows: list[dict] = []
    for km in LARGE_KM:
        for n in N_NODES:
            stem = _config_stem(km, n)
            level_dirs = {lvl: SYNTH_OUT / f"{stem}_{lvl}" for lvl in LEVELS}

            missing = [lvl for lvl, d in level_dirs.items() if not (d / "meta.json").exists()]
            if missing:
                print(f"  [WARN] Incomplete config {stem}, missing: {missing}")
                continue

            cost: dict[str, float] = {}
            co2: dict[str, float] = {}
            for lvl, d in level_dirs.items():
                c, e = _read_cost_co2(d)
                cost[lvl] = c
                co2[lvl] = e

            demand_mwh = _read_demand_mwh(level_dirs["L3"])

            decomp_topology = cost["L1"] - cost["L1cp"]
            decomp_heatloss = cost["L2"] - cost["L1"]
            decomp_pressure = cost["L3"] - cost["L2"]
            decomp_combined = cost["L3"] - cost["L1cp"]

            chain = [cost["L1cp"], cost["L1"], cost["L2"], cost["L3"]]
            rows.append(
                {
                    "config_id": stem,
                    "n_nodes": n,
                    "pipe_length_km": km,
                    "HI": HI,
                    "storage_h": STORAGE_H,
                    "peak_demand_MW": PEAK_DEMAND_MW,
                    "demand_total_MWh": round(demand_mwh, 4),
                    "cost_L1cp": round(cost["L1cp"], 6),
                    "cost_L1": round(cost["L1"], 6),
                    "cost_L2": round(cost["L2"], 6),
                    "cost_L3": round(cost["L3"], 6),
                    "cost_L3plus": round(cost["L3plus"], 6),
                    "co2_L1cp": round(co2["L1cp"], 6),
                    "co2_L3": round(co2["L3"], 6),
                    "decomp_topology_eur": round(decomp_topology, 6),
                    "decomp_heatloss_eur": round(decomp_heatloss, 6),
                    "decomp_pressure_eur": round(decomp_pressure, 6),
                    "decomp_combined_eur": round(decomp_combined, 6),
                    "lb_strict": _chain_ok(chain, tol=0.0),
                    "lb_05pct": _chain_ok(chain, tol=0.005),
                }
            )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["pipe_length_km", "n_nodes"]).reset_index(drop=True)


def _print_summary(df: pd.DataFrame) -> None:
    if df.empty:
        print("\n[INFO] No complete large-scale config results yet.")
        return

    tmp = df.copy()
    tmp["gap_L1_L3_pct"] = 100.0 * (tmp["cost_L3"] - tmp["cost_L1cp"]) / tmp["cost_L3"]
    print("\nâ€” Large-scale summary (L1cpâ†’L3) â€”")
    print(tmp[["n_nodes", "pipe_length_km", "cost_L1cp", "cost_L3", "gap_L1_L3_pct"]].to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run large-pipe synthetic extension")
    parser.add_argument("--workers", type=int, default=None, help="Parallel workers (default auto by RAM)")
    parser.add_argument("--threads", type=int, default=None, help="Gurobi threads per worker (default auto)")
    parser.add_argument("--dry-run", action="store_true", help="Show pending jobs only")
    parser.add_argument("--results-only", action="store_true", help="Skip runs and rebuild results CSV")
    args = parser.parse_args()

    print("=" * 60)
    print("run_large_scale_extension.py")
    print("=" * 60)
    print(f"  Large lengths: {LARGE_KM} km")
    print(f"  Node counts:   {N_NODES}")
    print(f"  HI/storage_h:  {HI} / {STORAGE_H}")
    print(f"  Levels:        {LEVELS}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    SYNTH_OUT.mkdir(parents=True, exist_ok=True)

    if not args.results_only:
        print("\n[1/4] Ensuring 30/50-km YAML configs exist...")
        base_yamls = _generate_large_yamls()

        try:
            import psutil

            ram_gb = psutil.virtual_memory().available / 1e9
        except ImportError:
            ram_gb = 40.0

        ram_per_job = 3.5
        auto_workers = max(1, min(6, int(ram_gb // ram_per_job)))
        n_workers = args.workers or auto_workers
        phys_cores = os.cpu_count() or 4
        n_threads = args.threads or max(2, phys_cores // n_workers)

        print("\n[2/4] Discovering pending jobs...")
        jobs = _build_jobs(base_yamls, n_threads)
        print(f"  Pending: {len(jobs)} (workers={n_workers}, threads/worker={n_threads})")
        for j in jobs:
            print(f"    {j['run_id']}")

        if args.dry_run:
            print("\n[DRY] Exiting without execution.")
            return

        if jobs:
            print("\n[3/4] Running missing jobs...")
            t0 = time.perf_counter()
            results: list[dict] = []
            done = 0
            with ProcessPoolExecutor(max_workers=n_workers) as pool:
                futures = {pool.submit(_run_job, job): job for job in jobs}
                for fut in as_completed(futures):
                    res = fut.result()
                    results.append(res)
                    done += 1
                    tag = "[OK]" if res["status"] == "ok" else "[ERR]"
                    print(f"  {tag} {done}/{len(jobs)} {res['run_id']} ({res['elapsed_s']/60:.1f} min)", flush=True)

            elapsed_min = (time.perf_counter() - t0) / 60
            ok = sum(1 for r in results if r["status"] == "ok")
            print(f"  Completed: {ok}/{len(results)} successful ({elapsed_min:.1f} min)")
            OUT_LOG.write_text(json.dumps(results, indent=2), encoding="utf-8")
            print(f"  Log: {OUT_LOG}")
        else:
            print("  No missing jobs found.")

    print("\n[4/4] Building consolidated large-scale results CSV...")
    df = _build_results()

    expected_rows = len(LARGE_KM) * len(N_NODES)
    if len(df) != expected_rows:
        print(f"[WARN] Expected {expected_rows} completed configs, found {len(df)}")
    else:
        print(f"  QA: {len(df)} / {expected_rows} configs complete (each includes {len(LEVELS)} levels)")

    if not df.empty:
        OUT_RESULTS.write_text(df.to_csv(index=False), encoding="utf-8")
        print(f"  Results: {OUT_RESULTS}")
        _print_summary(df)


if __name__ == "__main__":
    main()

