"""
Main paper run orchestrator (§2 + §3).

Usage:
    python scripts/paper/paper_runner.py [--runs L1 L2 L3 L3plus L3NL] [--horizon 8760]

Runs all 5 primary configs sequentially, extracts §3 artefacts per run,
validates against schemas, and writes output/paper_runs/REPORT.md.

Requires Gurobi for L3NL (MIQCP). L1/L2/L3/L3plus fall back to HiGHS if
Gurobi is unavailable (useful for development; warn prominently).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from calion.run.workflow import run_workflow
from scripts.paper.extract_artefacts import extract_all

OUT_BASE = ROOT / "output" / "paper_runs"
CONFIGS_DIR = ROOT / "configs" / "memmingen"

# Primary run definitions (§2)
PRIMARY_RUNS = [
    {
        "run_id": "L1",
        "config": CONFIGS_DIR / "Memmingen_L1.yaml",
        "overrides": None,
        "model_class": "MILP",
        "needs_gurobi": False,
    },
    {
        "run_id": "L2",
        "config": CONFIGS_DIR / "Memmingen_L2.yaml",
        "overrides": None,
        "model_class": "MILP",
        "needs_gurobi": False,
    },
    {
        "run_id": "L3",
        "config": CONFIGS_DIR / "Memmingen_L3_MILP.yaml",
        # L3 = L3_MILP with basic physics only (pressure_drop=false, transport_delay=false)
        "overrides": {
            "network": {
                "physics": {
                    "pressure_drop": False,
                    "transport_delay": False,
                    "heat_loss": True,
                }
            }
        },
        "model_class": "MILP",
        "needs_gurobi": False,
    },
    {
        "run_id": "L3plus",
        "config": CONFIGS_DIR / "Memmingen_L3_MILP.yaml",
        # L3+ = full extended physics
        "overrides": {
            "network": {
                "physics": {
                    "pressure_drop": True,
                    "transport_delay": True,
                    "heat_loss": True,
                }
            }
        },
        "model_class": "MILP",
        "needs_gurobi": False,
    },
    {
        "run_id": "L3NL",
        "config": CONFIGS_DIR / "Memmingen_L3_MIQP.yaml",
        "overrides": None,
        "model_class": "MIQCP",
        "needs_gurobi": True,
    },
]

SCHEMA_DIR = OUT_BASE / "_schemas"


def _gurobi_available() -> bool:
    try:
        import gurobipy  # noqa: F401
        return True
    except ImportError:
        return False


def _validate_schema(outdir: Path, schema_name: str) -> bool:
    schema_path = SCHEMA_DIR / schema_name
    if not schema_path.exists():
        return True
    try:
        import jsonschema
        schema = json.loads(schema_path.read_text())
        if schema_name == "economics.json":
            csv_path = outdir / "economics.csv"
            if csv_path.exists():
                import pandas as pd
                df = pd.read_csv(csv_path)
                if df.empty:
                    return False
                row = df.iloc[0].to_dict()
                jsonschema.validate(row, schema)
        return True
    except Exception as e:
        print(f"  [SCHEMA WARN] {schema_name}: {e}")
        return False


def run_one(spec: dict, gurobi_ok: bool) -> dict:
    run_id = spec["run_id"]
    config = spec["config"]
    overrides = spec.get("overrides")

    if spec["needs_gurobi"] and not gurobi_ok:
        print(f"\n[SKIP] {run_id} — Gurobi not available (needs NonConvex=2 for MIQCP)")
        return {"run_id": run_id, "status": "skipped_no_gurobi"}

    if not config.exists():
        print(f"\n[SKIP] {run_id} — config not found: {config}")
        return {"run_id": run_id, "status": "skipped_missing_config"}

    print(f"\n{'='*60}")
    print(f"Running {run_id} — {config.name}")
    if overrides:
        print(f"  physics overrides: {overrides.get('network', {}).get('physics', {})}")

    t0 = time.perf_counter()
    try:
        wf = run_workflow([str(config)], overrides=overrides)
        elapsed = time.perf_counter() - t0

        result = wf.pf_result
        status = result.solver.get("termination_condition", "unknown") if result else "failed"
        obj = 0.0
        if result and result.summary:
            obj = float(result.summary.get("objective", {}).get("OBJ_value_EUR", 0.0))

        print(f"  Status:    {status}")
        print(f"  Objective: {obj:,.0f} EUR")
        print(f"  Time:      {elapsed:.1f}s")

        outdir = extract_all(
            run_id=run_id,
            config_path=str(config),
            workflow=wf,
            solve_time_s=elapsed,
        )

        # Schema validation
        _validate_schema(outdir, "meta.json")
        _validate_schema(outdir, "economics.json")

        return {
            "run_id": run_id,
            "status": status,
            "objective_eur": obj,
            "solve_time_s": round(elapsed, 1),
            "outdir": str(outdir),
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "run_id": run_id,
            "status": "error",
            "error": str(e),
            "solve_time_s": round(elapsed, 1),
        }


def write_report(results: list[dict]) -> None:
    lines = [
        "# Paper Run Report\n\n",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        "## Primary Runs\n\n",
        "| run_id | status | objective (EUR) | solve_time (s) |\n",
        "|--------|--------|-----------------|----------------|\n",
    ]
    for r in results:
        obj = f"{r.get('objective_eur', 'N/A'):,.0f}" if isinstance(r.get("objective_eur"), float) else "N/A"
        lines.append(
            f"| {r['run_id']} | {r['status']} | {obj} | {r.get('solve_time_s', 'N/A')} |\n"
        )

    lines.append("\n## Artefact Locations\n\n")
    for r in results:
        if "outdir" in r:
            lines.append(f"- **{r['run_id']}**: `{r['outdir']}`\n")

    report_path = OUT_BASE / "REPORT.md"
    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"\nReport: {report_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runs", nargs="*",
        default=["L1", "L2", "L3", "L3plus", "L3NL"],
        help="Which run_ids to execute",
    )
    args = parser.parse_args(argv)

    gurobi_ok = _gurobi_available()
    if not gurobi_ok:
        print("[WARN] Gurobi not available — L3NL will be skipped. L1/L2/L3/L3plus use HiGHS.")

    selected = {r["run_id"]: r for r in PRIMARY_RUNS if r["run_id"] in args.runs}
    results = []

    for run_id in args.runs:
        if run_id not in selected:
            print(f"[SKIP] Unknown run_id: {run_id}")
            continue
        r = run_one(selected[run_id], gurobi_ok)
        results.append(r)
        # Save intermediate results
        (OUT_BASE / "run_results.json").write_text(
            json.dumps(results, indent=2, default=str), encoding="utf-8"
        )

    write_report(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
