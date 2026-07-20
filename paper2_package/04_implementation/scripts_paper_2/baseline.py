"""Paper 2 baseline runner.

Runs the BC-MM and BC-SB scenarios (no investment, real heat curve).
These are already handled by scenario_runner.py with baseline=True in scenarios.yaml.

This module provides a standalone CLI to run baselines only,
and a helper to read baseline KPIs for comparison.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

logger = logging.getLogger(__name__)

OUT_BASE = _ROOT / "output" / "paper2_runs"


def run_baselines(dry_run: bool = False, force_rerun: bool = False) -> list[dict]:
    """Run BC-MM and BC-SB baseline scenarios."""
    from scripts.paper_2.scenario_runner import load_scenarios_config, run_single_scenario
    scen_cfg = load_scenarios_config()
    baselines = [s for s in scen_cfg["scenarios"] if s.get("baseline")]
    results = []
    for scen in baselines:
        logger.info("Running baseline: %s", scen["id"])
        res = run_single_scenario(scen, scen_cfg, dry_run=dry_run, force_rerun=force_rerun)
        results.append(res)
        logger.info("  %s → %s", scen["id"], res.get("status"))
    return results


def read_baseline_kpis(network: str) -> dict | None:
    """Read KPIs from the baseline scenario for a given network.

    Args:
        network: "memmingen" or "stadtbach"

    Returns:
        KPI dict from kpi_calculator, or None if not yet computed.
    """
    bc_id = "BC-MM" if network.lower().startswith("m") else "BC-SB"
    bc_dir = OUT_BASE / bc_id
    if not bc_dir.exists():
        logger.warning("Baseline dir not found: %s", bc_dir)
        return None

    from scripts.paper_2.kpi_calculator import compute_scenario_kpis
    return compute_scenario_kpis(bc_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import argparse
    p = argparse.ArgumentParser(description="Run Paper 2 baseline scenarios")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force-rerun", action="store_true")
    args = p.parse_args()
    run_baselines(dry_run=args.dry_run, force_rerun=args.force_rerun)
