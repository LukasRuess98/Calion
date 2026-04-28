"""§4 Sensitivity runner — 7 scenarios x L3 (and optionally L3NL).

Requires Gurobi for 8760h runs. Each scenario overrides one parameter from
the baseline L3 config and writes results to output/paper_runs/sensitivity/.

Usage:
    python scripts/paper/sensitivity_runner.py --runs baseline gas_high elec_low
    python scripts/paper/sensitivity_runner.py --all
    python scripts/paper/sensitivity_runner.py --all --level L3NL  # needs Gurobi
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.paper.extract_artefacts import extract_all

SCENARIOS = {
    "baseline": {},
    "gas_high": {
        "assets": {"chp_main": {"fuel_cost_eur_per_mwh": 48.0}}
    },
    "elec_low": {
        "market": {"electricity_buy_price_eur_per_mwh": 64.0}
    },
    "co2_high": {
        "assets": {"chp_main": {"co2_cost_eur_per_t": 200.0}}
    },
    "cold": {
        "demand": {"scale_factor": 1.05},
        "network": {"physics": {"T_supply_nominal": 93.0}},
    },
    "warm": {
        "demand": {"scale_factor": 0.95},
        "network": {"physics": {"T_supply_nominal": 87.0}},
    },
    "cop_low": {
        "assets": {"hp_main": {"cop_carnot_factor": 0.45}}
    },
}

BASE_CONFIGS = {
    "L3":   ROOT / "configs" / "memmingen" / "Memmingen_L3_MILP.yaml",
    "L3NL": ROOT / "configs" / "memmingen" / "Memmingen_L3_MIQP.yaml",
}

NEEDS_GUROBI = {"L3NL"}


def _deep_merge(base: dict, override: dict) -> dict:
    import copy
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def run_scenario(level: str, scenario: str, dry_run: bool = False) -> None:
    import yaml
    from calion.workflow import run_workflow

    config_path = BASE_CONFIGS[level]
    overrides = SCENARIOS[scenario]

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    cfg = _deep_merge(cfg, overrides)

    out_dir = ROOT / "output" / "paper_runs" / "sensitivity" / f"{level}_{scenario}"
    out_dir.mkdir(parents=True, exist_ok=True)

    tmp_cfg = out_dir / "_scenario_config.yaml"
    with open(tmp_cfg, "w") as f:
        yaml.dump(cfg, f, allow_unicode=True)

    if dry_run:
        print(f"[DRY] {level}/{scenario} -> {out_dir}")
        return

    print(f"[RUN] {level}/{scenario} ...")
    t0 = time.time()
    result = run_workflow([str(tmp_cfg)])
    elapsed = time.time() - t0

    extract_all(
        run_id=f"{level}_{scenario}",
        config_path=tmp_cfg,
        workflow=result,
        solve_time_s=elapsed,
        outdir=out_dir,
    )
    print(f"[DONE] {level}/{scenario} in {elapsed:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sensitivity scenario runner")
    parser.add_argument("--runs", nargs="+", choices=list(SCENARIOS.keys()),
                        help="Specific scenarios to run")
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--level", choices=list(BASE_CONFIGS.keys()), default="L3")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.level in NEEDS_GUROBI:
        try:
            import gurobipy  # noqa: F401
        except ImportError:
            print(f"[SKIP] {args.level} requires Gurobi (not installed). Exiting.")
            sys.exit(0)

    scenarios = list(SCENARIOS.keys()) if args.all else (args.runs or ["baseline"])

    for s in scenarios:
        if s not in SCENARIOS:
            print(f"[WARN] Unknown scenario: {s}")
            continue
        run_scenario(args.level, s, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
