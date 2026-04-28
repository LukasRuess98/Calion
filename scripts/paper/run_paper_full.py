"""
Full paper run orchestrator — executes all phases in order.

Phases:
  1. Primary runs     (§2): L1, L2, L3, L3+, L3NL
  2. Sensitivity runs (§4): 7 scenarios x L1/L2/L3/L3+
  3. Synthetic runs   (§5): 36 configs x 5 levels = 180 runs
  4. Tables           (§7): tablegen.py
  5. Fill paper       (§8): fill_paper.py --auto

Usage:
    python scripts/paper/run_paper_full.py                  # all phases
    python scripts/paper/run_paper_full.py --phases 1 2     # only primary + sensitivity
    python scripts/paper/run_paper_full.py --phases 3       # only synthetic
    python scripts/paper/run_paper_full.py --phases 4 5     # tables + fill paper
    python scripts/paper/run_paper_full.py --skip-nl        # skip all L3NL runs (no Gurobi)
    python scripts/paper/run_paper_full.py --dry-run        # print plan, do not run

Notes:
  - L1/L2/L3/L3+ fall back to HiGHS if Gurobi is unavailable.
  - L3NL is skipped automatically if Gurobi is not installed (unless --fail-on-skip).
  - Results go to output/paper_runs/<run_id>/.
  - Sensitivity to output/paper_runs/sensitivity/<level>_<scenario>/.
  - Synthetic  to output/paper_runs/synth/<synth_id>_<level>/.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT_BASE   = ROOT / "output" / "paper_runs"
SYNTH_DIR  = ROOT / "synth_configs"
CONFIGS    = ROOT / "configs" / "memmingen"

# ──────────────────────────────────────────────────────────────────────────────
# Gurobi detection
# ──────────────────────────────────────────────────────────────────────────────

def _gurobi_ok() -> bool:
    try:
        import gurobipy  # noqa: F401
        return True
    except ImportError:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — Primary runs
# ──────────────────────────────────────────────────────────────────────────────

PRIMARY_RUNS = [
    {
        "run_id": "L1",
        "config": CONFIGS / "Memmingen_L1.yaml",
        "overrides": None,
        "needs_gurobi": False,
    },
    {
        "run_id": "L2",
        "config": CONFIGS / "Memmingen_L2.yaml",
        "overrides": None,
        "needs_gurobi": False,
    },
    {
        "run_id": "L3",
        "config": CONFIGS / "Memmingen_L3_MILP.yaml",
        # L3 = basic physics only (no pressure drop, no transport delay)
        "overrides": {
            "network": {"physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False}}
        },
        "needs_gurobi": False,
    },
    {
        "run_id": "L3plus",
        "config": CONFIGS / "Memmingen_L3_MILP.yaml",
        # L3+ = full extended physics
        "overrides": {
            "network": {"physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True}}
        },
        "needs_gurobi": False,
    },
    {
        "run_id": "L3NL",
        "config": CONFIGS / "Memmingen_L3_MIQP.yaml",
        "overrides": None,
        "needs_gurobi": True,
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — Sensitivity scenarios (§4)
# ──────────────────────────────────────────────────────────────────────────────

SENSITIVITY_SCENARIOS = {
    "baseline": {},
    "gas_high":  {"fuels": {"gas": {"price_eur_mwh": 54.0}}},           # x1.20
    "elec_low":  {"_market_scale": 0.80},                                # spot x0.80 (applied at runtime)
    "co2_high":  {"costs": {"co2_price_eur_per_t": 200.0}},
    "co2_market":{"costs": {"co2_price_eur_per_t": 100.0}},
    "cold":      {"_demand_scale": 1.05},                                # demand x1.05
    "warm":      {"_demand_scale": 0.95},                                # demand x0.95
    "cop_low":   {"assets": {"hp_main": {"carnot_efficiency": 0.54}}},
}

# Levels to run sensitivities on (paper §4: L1, L2, L3, L3+)
SENSITIVITY_LEVELS = ["L1", "L2", "L3", "L3plus"]

# Map level → primary config + physics overrides
LEVEL_TO_PRIMARY = {r["run_id"]: r for r in PRIMARY_RUNS}


# ──────────────────────────────────────────────────────────────────────────────
# Physics override presets for synthetic runs
# ──────────────────────────────────────────────────────────────────────────────

SYNTH_PHYSICS = {
    "L1": {
        "network": {"physics": {"heat_loss": False, "pressure_drop": False, "transport_delay": False}}
    },
    "L2": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False}}
    },
    "L3": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False}}
    },
    "L3plus": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True}}
    },
    "L3NL": {
        "scenario": {"milp_linearize": False},
        "network":  {"milp_linearize": False,
                     "physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True}},
        "run": {"solver": "gurobi", "solver_options": {
            "NonConvex": 2, "MIPGap": 0.005, "TimeLimit": 86400,
            "NumericFocus": 3, "Heuristics": 0.2, "OutputFlag": 1,
        }},
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        import json as _json
        raise RuntimeError("PyYAML required: pip install pyyaml")


def _dump_yaml(cfg: dict, path: Path) -> None:
    try:
        import yaml
        path.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False,
                                  sort_keys=False), encoding="utf-8")
    except ImportError:
        raise RuntimeError("PyYAML required: pip install pyyaml")


def _run_workflow_with_overrides(config_path: Path, overrides: dict | None):
    """Load config, apply overrides, run workflow, return workflow object."""
    from calion.run.workflow import run_workflow
    if not overrides:
        return run_workflow([str(config_path)])
    cfg = _load_yaml(config_path)
    cfg = _deep_merge(cfg, overrides)
    tmp = config_path.parent / f"_tmp_{config_path.stem}.yaml"
    _dump_yaml(cfg, tmp)
    try:
        return run_workflow([str(tmp)])
    finally:
        if tmp.exists():
            tmp.unlink()


def _extract(run_id: str, config_path: Path, workflow, elapsed: float,
             outdir: Path | None = None) -> Path:
    from scripts.paper.extract_artefacts import extract_all
    return extract_all(
        run_id=run_id,
        config_path=str(config_path),
        workflow=workflow,
        solve_time_s=elapsed,
        outdir=outdir,
    )


def _record(log: list[dict], entry: dict) -> None:
    log.append(entry)
    (OUT_BASE / "run_log.json").write_text(
        json.dumps(log, indent=2, default=str), encoding="utf-8"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase runners
# ──────────────────────────────────────────────────────────────────────────────

def phase1_primary(gurobi: bool, skip_nl: bool, dry_run: bool, log: list) -> None:
    print("\n" + "="*70)
    print("PHASE 1 — Primary runs (§2)")
    print("="*70)

    for spec in PRIMARY_RUNS:
        run_id  = spec["run_id"]
        config  = spec["config"]
        overrides = spec.get("overrides")
        needs_g = spec["needs_gurobi"]

        if (needs_g and not gurobi) or (skip_nl and run_id == "L3NL"):
            print(f"\n[SKIP] {run_id} — {'no Gurobi' if needs_g else 'skip-nl flag'}")
            _record(log, {"phase": 1, "run_id": run_id, "status": "skipped"})
            continue

        if not config.exists():
            print(f"\n[SKIP] {run_id} — config missing: {config}")
            _record(log, {"phase": 1, "run_id": run_id, "status": "missing_config"})
            continue

        if dry_run:
            phys = overrides.get("network", {}).get("physics", {}) if overrides else {}
            print(f"\n[DRY] {run_id}  config={config.name}  physics={phys or 'default'}")
            continue

        print(f"\n[RUN] {run_id} — {config.name}")
        if overrides:
            print(f"      physics: {overrides.get('network', {}).get('physics', {})}")

        t0 = time.perf_counter()
        try:
            wf = _run_workflow_with_overrides(config, overrides)
            elapsed = time.perf_counter() - t0
            outdir  = _extract(run_id, config, wf, elapsed)
            obj = 0.0
            if wf.pf_result and wf.pf_result.summary:
                obj = float(wf.pf_result.summary.get("objective", {}).get("OBJ_value_EUR", 0.0))
            print(f"      done in {elapsed:.1f}s  obj={obj:,.0f} EUR  out={outdir}")
            _record(log, {"phase": 1, "run_id": run_id, "status": "ok",
                          "solve_s": round(elapsed, 1), "obj_eur": obj})
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"      ERROR after {elapsed:.1f}s: {exc}")
            _record(log, {"phase": 1, "run_id": run_id, "status": "error", "error": str(exc)})


def phase2_sensitivity(gurobi: bool, skip_nl: bool, dry_run: bool, log: list) -> None:
    print("\n" + "="*70)
    print("PHASE 2 — Sensitivity runs (§4)")
    print("="*70)

    sens_base = OUT_BASE / "sensitivity"
    sens_base.mkdir(parents=True, exist_ok=True)

    combos = [(lvl, sc) for lvl in SENSITIVITY_LEVELS for sc in SENSITIVITY_SCENARIOS]
    print(f"  {len(combos)} runs total ({len(SENSITIVITY_LEVELS)} levels x {len(SENSITIVITY_SCENARIOS)} scenarios)")

    for level, scenario in combos:
        run_id  = f"{level}_{scenario}"
        primary = LEVEL_TO_PRIMARY[level]
        config  = primary["config"]

        if not config.exists():
            print(f"\n[SKIP] {run_id} — config missing")
            _record(log, {"phase": 2, "run_id": run_id, "status": "missing_config"})
            continue

        if dry_run:
            print(f"  [DRY] {run_id}")
            continue

        # Build override: merge physics preset + scenario delta
        physics_override = primary.get("overrides") or {}
        scenario_delta   = SENSITIVITY_SCENARIOS[scenario]
        # Skip special keys (handled externally — spot/demand scaling not yet wired)
        clean_delta = {k: v for k, v in scenario_delta.items() if not k.startswith("_")}
        overrides = _deep_merge(physics_override, clean_delta)

        outdir = sens_base / run_id
        outdir.mkdir(parents=True, exist_ok=True)

        print(f"\n[RUN] {run_id}")
        t0 = time.perf_counter()
        try:
            wf = _run_workflow_with_overrides(config, overrides or None)
            elapsed = time.perf_counter() - t0
            _extract(run_id, config, wf, elapsed, outdir=outdir)
            print(f"      done in {elapsed:.1f}s")
            _record(log, {"phase": 2, "run_id": run_id, "status": "ok",
                          "solve_s": round(elapsed, 1)})
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"      ERROR: {exc}")
            _record(log, {"phase": 2, "run_id": run_id, "status": "error", "error": str(exc)})

    # Roll-up summary CSV
    _write_sensitivity_summary(sens_base)


def _write_sensitivity_summary(sens_base: Path) -> None:
    """Collect all economics.csv from sensitivity runs into one summary.csv."""
    try:
        import pandas as pd
        rows = []
        for sub in sorted(sens_base.iterdir()):
            econ = sub / "economics.csv"
            if econ.exists():
                df = pd.read_csv(econ)
                if not df.empty:
                    row = df.iloc[0].to_dict()
                    # Parse level and scenario from folder name
                    parts = sub.name.rsplit("_", 1)
                    row["level"]    = parts[0] if len(parts) == 2 else sub.name
                    row["scenario"] = parts[1] if len(parts) == 2 else "unknown"
                    rows.append(row)
        if rows:
            pd.DataFrame(rows).to_csv(sens_base / "summary.csv", index=False)
            print(f"\n  [SUMMARY] sensitivity/summary.csv ({len(rows)} rows)")
    except Exception as e:
        print(f"\n  [WARN] sensitivity summary failed: {e}")


def phase3_synthetic(gurobi: bool, skip_nl: bool, dry_run: bool, log: list) -> None:
    print("\n" + "="*70)
    print("PHASE 3 — Synthetic runs (§5): 36 configs x 5 levels")
    print("="*70)

    synth_yamls = sorted(SYNTH_DIR.glob("synth_*.yaml"))
    if not synth_yamls:
        print("  [WARN] No synth configs found. Run: python tools/gen_synth.py --seed 42")
        return

    synth_out = OUT_BASE / "synth"
    synth_out.mkdir(parents=True, exist_ok=True)

    levels = list(SYNTH_PHYSICS.keys())
    total  = len(synth_yamls) * len(levels)
    print(f"  {len(synth_yamls)} configs x {len(levels)} levels = {total} runs")

    done = 0
    for yaml_path in synth_yamls:
        synth_id = yaml_path.stem

        for level, physics_override in SYNTH_PHYSICS.items():
            run_id = f"{synth_id}_{level}"

            if (level == "L3NL" and not gurobi) or (skip_nl and level == "L3NL"):
                if dry_run:
                    print(f"  [SKIP] {run_id} — no Gurobi")
                _record(log, {"phase": 3, "run_id": run_id, "status": "skipped"})
                done += 1
                continue

            outdir = synth_out / run_id
            if outdir.exists() and (outdir / "meta.json").exists():
                print(f"  [CACHE] {run_id} — already done, skipping")
                done += 1
                continue

            if dry_run:
                print(f"  [DRY] {run_id}")
                done += 1
                continue

            outdir.mkdir(parents=True, exist_ok=True)
            t0 = time.perf_counter()
            try:
                wf = _run_workflow_with_overrides(yaml_path, physics_override)
                elapsed = time.perf_counter() - t0
                _extract(run_id, yaml_path, wf, elapsed, outdir=outdir)
                done += 1
                print(f"  [OK] {run_id}  {elapsed:.1f}s  ({done}/{total})")
                _record(log, {"phase": 3, "run_id": run_id, "status": "ok",
                              "solve_s": round(elapsed, 1)})
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                done += 1
                print(f"  [ERR] {run_id}  {elapsed:.1f}s  {exc}")
                _record(log, {"phase": 3, "run_id": run_id, "status": "error",
                              "error": str(exc)})


def phase4_tables(dry_run: bool, log: list) -> None:
    print("\n" + "="*70)
    print("PHASE 4 — Generate LaTeX tables (§7)")
    print("="*70)
    if dry_run:
        print("  [DRY] python tools/tablegen.py")
        return
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "tablegen.py")],
        cwd=ROOT, capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"  [WARN] tablegen exited {result.returncode}: {result.stderr[:500]}")
        _record(log, {"phase": 4, "status": "error", "stderr": result.stderr[:500]})
    else:
        _record(log, {"phase": 4, "status": "ok"})


def phase5_fill_paper(dry_run: bool, log: list) -> None:
    print("\n" + "="*70)
    print("PHASE 5 — Fill paper placeholders (§8)")
    print("="*70)
    fill_py = ROOT / "tools" / "fill_paper.py"
    if dry_run:
        print("  [DRY] python tools/fill_paper.py --auto")
        return
    result = subprocess.run(
        [sys.executable, str(fill_py), "--auto"],
        cwd=ROOT, capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"  [WARN] fill_paper exited {result.returncode}: {result.stderr[:500]}")
        _record(log, {"phase": 5, "status": "error", "stderr": result.stderr[:500]})
    else:
        _record(log, {"phase": 5, "status": "ok"})


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Full paper orchestrator — runs all phases in order.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--phases", nargs="+", type=int, choices=[1, 2, 3, 4, 5],
        default=[1, 2, 3, 4, 5],
        metavar="N",
        help="Phases to run (default: all). 1=primary 2=sensitivity 3=synth 4=tables 5=fill",
    )
    parser.add_argument("--skip-nl", action="store_true",
                        help="Skip all L3NL (Gurobi NonConvex) runs unconditionally")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan only — do not run any solver")
    parser.add_argument("--fail-on-skip", action="store_true",
                        help="Exit non-zero if any run is skipped due to missing Gurobi")
    args = parser.parse_args(argv)

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    log: list[dict] = []

    gurobi = _gurobi_ok()
    if not gurobi:
        print("[WARN] Gurobi not available — L3NL runs will be skipped.")
        print("       L1/L2/L3/L3+ will use HiGHS (no --skip-nl needed).")
    else:
        print("[INFO] Gurobi detected.")

    if args.dry_run:
        print("[DRY RUN] No solver calls will be made.\n")

    t_total = time.perf_counter()

    phase_map = {
        1: lambda: phase1_primary(gurobi, args.skip_nl, args.dry_run, log),
        2: lambda: phase2_sensitivity(gurobi, args.skip_nl, args.dry_run, log),
        3: lambda: phase3_synthetic(gurobi, args.skip_nl, args.dry_run, log),
        4: lambda: phase4_tables(args.dry_run, log),
        5: lambda: phase5_fill_paper(args.dry_run, log),
    }

    for p in sorted(args.phases):
        phase_map[p]()

    elapsed = time.perf_counter() - t_total
    skipped = sum(1 for e in log if e.get("status") == "skipped")
    errors  = sum(1 for e in log if e.get("status") == "error")
    ok      = sum(1 for e in log if e.get("status") == "ok")

    print(f"\n{'='*70}")
    print(f"DONE  total={elapsed:.0f}s  ok={ok}  errors={errors}  skipped={skipped}")
    print(f"  log -> {OUT_BASE / 'run_log.json'}")
    print(f"{'='*70}")

    if errors:
        print(f"[WARN] {errors} run(s) failed — check run_log.json for details.")

    if args.fail_on_skip and skipped:
        print(f"[FAIL] {skipped} run(s) skipped (--fail-on-skip set).")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
