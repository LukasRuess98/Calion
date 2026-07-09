#!/usr/bin/env python
"""Paper 2 master orchestrator.

Mirrors the pattern of scripts/paper/run_paper_full.py for Paper 2.

Phases:
  0 — Baseline runs (BC-MM, BC-SB): reference case without investment
  1 — 18 investment optimization MILP runs (all non-baseline scenarios)
  2 — Sensitivity analysis (tornado) for best scenario per network
  3 — KPI calculation and aggregation (scenarios_kpis.csv)
  4 — Figure generation (figgen_p2.py)
  5 — LaTeX table generation (tablegen_p2.py)

Usage:
  python scripts/paper_2/run_paper2_full.py
  python scripts/paper_2/run_paper2_full.py --phases 0 1
  python scripts/paper_2/run_paper2_full.py --phases 3 4 5
  python scripts/paper_2/run_paper2_full.py --dry-run
  python scripts/paper_2/run_paper2_full.py --scenario MM-S1-HK0
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

OUT_BASE = _ROOT / "output" / "paper2_runs"
LOG_FILE = OUT_BASE / "run_log.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("paper2")


# ── Phase definitions ──────────────────────────────────────────────────────

BASELINE_IDS = ["BC-MM", "BC-SB"]
ALL_PHASES = [0, 1, 2, 3, 4, 5]


def phase0_baseline(dry_run: bool, force_rerun: bool) -> list[dict]:
    """Run baseline cases (no investment, real heat curve)."""
    logger.info("-- Phase 0: Baseline Runs ------------------------------------------")
    from scripts.paper_2.scenario_runner import load_scenarios_config, run_single_scenario
    scen_cfg = load_scenarios_config()
    baselines = [s for s in scen_cfg["scenarios"] if s.get("baseline")]
    results = []
    for scen in baselines:
        res = run_single_scenario(scen, scen_cfg, dry_run=dry_run, force_rerun=force_rerun)
        results.append(res)
        logger.info("Baseline %s -> %s", scen["id"], res.get("status"))
    return results


def phase1_optimization(
    dry_run: bool,
    force_rerun: bool,
    scenario_ids: list[str] | None = None,
) -> list[dict]:
    """Run all 18 investment optimization scenarios."""
    logger.info("-- Phase 1: Investment Optimization Runs ---------------------------")
    from scripts.paper_2.scenario_runner import load_scenarios_config, run_single_scenario
    scen_cfg = load_scenarios_config()
    opt_scenarios = [s for s in scen_cfg["scenarios"] if not s.get("baseline")]
    if scenario_ids:
        opt_scenarios = [s for s in opt_scenarios if s["id"] in scenario_ids]
    results = []
    for scen in opt_scenarios:
        res = run_single_scenario(scen, scen_cfg, dry_run=dry_run, force_rerun=force_rerun)
        results.append(res)
        status = res.get("status", "?")
        logger.info("  %s -> %s (%.1f s)", scen["id"], status, res.get("solve_s", 0))
    return results


def phase2_sensitivity(dry_run: bool) -> dict:
    """Run sensitivity (tornado) analysis for best scenario per network."""
    logger.info("-- Phase 2: Sensitivity Analysis -----------------------------------")
    if dry_run:
        logger.info("[DRY-RUN] Would run sensitivity analysis")
        return {"status": "dry_run"}
    try:
        from scripts.paper_2.sensitivity import run_sensitivity
        return run_sensitivity(OUT_BASE)
    except Exception as exc:
        logger.error("Sensitivity failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def phase3_kpis(dry_run: bool) -> dict:
    """Compute KPIs and write scenarios_kpis.csv."""
    logger.info("-- Phase 3: KPI Calculation ----------------------------------------")
    if dry_run:
        logger.info("[DRY-RUN] Would compute KPIs")
        return {"status": "dry_run"}
    try:
        from scripts.paper_2.kpi_calculator import compute_all_kpis
        kpi_path = compute_all_kpis(OUT_BASE)
        logger.info("KPIs written to %s", kpi_path)
        return {"status": "ok", "kpi_file": str(kpi_path)}
    except Exception as exc:
        logger.error("KPI calculation failed: %s", exc)
        return {"status": "error", "error": str(exc)}


_FIGDIR = _ROOT / "scripts" / "paper_2" / "figures"


def _run_generators(scripts: list[Path]) -> dict:
    """Run each canonical generator script in a subprocess; return {name: status}.

    Subprocess isolation keeps one generator's failure from aborting the phase and
    avoids import-path coupling (each script has its own __main__ that produces its
    full output set into results/paper2_figures/).
    """
    import subprocess
    out: dict[str, str] = {}
    for script in scripts:
        if not script.exists():
            out[script.name] = "missing"
            continue
        try:
            r = subprocess.run([sys.executable, str(script)], cwd=str(_ROOT),
                               capture_output=True, text=True, timeout=3600)
            out[script.name] = "ok" if r.returncode == 0 else f"rc={r.returncode}"
            if r.returncode != 0:
                logger.error("  [%s] stderr: %s", script.name, r.stderr[-400:])
        except Exception as exc:  # noqa: BLE001
            out[script.name] = f"error: {exc}"
        logger.info("  [%s] %s", script.name, out[script.name])
    return out


def phase4_figures(dry_run: bool) -> dict:
    """Generate the canonical Paper 2 figure set (F1–F9) → results/paper2_figures/.

    Legacy figgen_p2 output is produced too (best-effort) for continuity.
    """
    logger.info("-- Phase 4: Figure Generation --------------------------------------")
    if dry_run:
        logger.info("[DRY-RUN] Would generate figures F1-F9")
        return {"status": "dry_run"}
    results = _run_generators([
        _FIGDIR / "fig_f1_architecture.py",
        _FIGDIR / "fig_f2_network_maps.py",
        _FIGDIR / "fig_p2_campaign.py",
    ])
    try:
        from tools.figgen_p2 import generate_all_figures
        legacy = OUT_BASE / "figures"
        legacy.mkdir(parents=True, exist_ok=True)
        generate_all_figures(OUT_BASE, legacy)
        results["legacy_figgen_p2"] = "ok"
    except Exception as exc:  # noqa: BLE001
        results["legacy_figgen_p2"] = f"skipped: {exc}"
    return {"status": "ok", "generators": results,
            "out": str(_ROOT / "results" / "paper2_figures")}


def phase5_tables(dry_run: bool) -> dict:
    """Generate the canonical Paper 2 tables (T1–T5, CSV + LaTeX)."""
    logger.info("-- Phase 5: Table Generation ---------------------------------------")
    if dry_run:
        logger.info("[DRY-RUN] Would generate tables T1-T5")
        return {"status": "dry_run"}
    results = _run_generators([_FIGDIR / "gen_tables.py"])
    try:
        from tools.tablegen_p2 import generate_all_tables
        legacy = OUT_BASE / "tables"
        legacy.mkdir(parents=True, exist_ok=True)
        generate_all_tables(OUT_BASE, legacy)
        results["legacy_tablegen_p2"] = "ok"
    except Exception as exc:  # noqa: BLE001
        results["legacy_tablegen_p2"] = f"skipped: {exc}"
    return {"status": "ok", "generators": results,
            "out": str(_ROOT / "results" / "paper2_figures")}


# ── Log helpers ────────────────────────────────────────────────────────────

def _load_log() -> dict:
    if LOG_FILE.exists():
        with open(LOG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"runs": [], "phases": {}}


def _save_log(log: dict) -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def _record_phase(log: dict, phase: int, result: dict | list) -> None:
    log.setdefault("phases", {})[str(phase)] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": result if isinstance(result, dict) else {"n": len(result)},
    }
    if isinstance(result, list):
        for r in result:
            log.setdefault("runs", []).append(r)


# ── CLI ───────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Paper 2 master orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--phases", nargs="+", type=int, default=ALL_PHASES,
        metavar="N", help=f"Phases to run (default: {ALL_PHASES})",
    )
    p.add_argument(
        "--scenario", nargs="+", default=None,
        help="Run only specific scenario IDs in phase 1",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Preview plan without solving",
    )
    p.add_argument(
        "--force-rerun", action="store_true",
        help="Re-run scenarios even if output already exists",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    phases = sorted(set(args.phases))
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    log = _load_log()

    logger.info("=" * 56)
    logger.info("  PAPER 2 FULL RUN  |  phases=%s  |  dry=%s", phases, args.dry_run)
    logger.info("=" * 56)

    t_start = time.perf_counter()

    if 0 in phases:
        result = phase0_baseline(dry_run=args.dry_run, force_rerun=args.force_rerun)
        _record_phase(log, 0, result)
        _save_log(log)

    if 1 in phases:
        result = phase1_optimization(
            dry_run=args.dry_run,
            force_rerun=args.force_rerun,
            scenario_ids=args.scenario,
        )
        _record_phase(log, 1, result)
        _save_log(log)

    if 2 in phases:
        result = phase2_sensitivity(dry_run=args.dry_run)
        _record_phase(log, 2, result)
        _save_log(log)

    if 3 in phases:
        result = phase3_kpis(dry_run=args.dry_run)
        _record_phase(log, 3, result)
        _save_log(log)

    if 4 in phases:
        result = phase4_figures(dry_run=args.dry_run)
        _record_phase(log, 4, result)
        _save_log(log)

    if 5 in phases:
        result = phase5_tables(dry_run=args.dry_run)
        _record_phase(log, 5, result)
        _save_log(log)

    elapsed = time.perf_counter() - t_start
    logger.info("Total wall time: %.1f s (%.1f min)", elapsed, elapsed / 60)
    logger.info("Run log: %s", LOG_FILE)


if __name__ == "__main__":
    main()
