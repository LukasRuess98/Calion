#!/usr/bin/env python3
"""
Unified command-line interface for the CALION framework.

Usage:
    python -m calion.run <config1.yaml> <config2.yaml> ...
    python -m calion.run configs/scenarios/quick_test.yaml --dashboard
    python -m calion.run configs/templates/level1_copperplate.yaml --run-mode PF_ONLY

All workflow arguments (--run-mode, --sensitivity-*, --fix-design, etc.) and
export arguments (--dashboard, --save-lp) are available in a single CLI.
"""

import argparse
import sys
from pathlib import Path

from calion.logging_config import get_logger
from calion.run.export import export_workflow_results as _export_workflow_results
from calion.run import workflow as _wf
from calion.run.workflow import (
    _build_override_dict,
    _expand_sensitivity_runs,
    _merge_cli_and_env,
    add_workflow_cli_args,
)
from calion.run.utilities import _gather_env_overrides

logger = get_logger(__name__)


def main(argv=None):
    """Unified CLI entry point for ``python -m calion.run``.

    Returns 0 on success, 1 on failure.  When invoked as
    ``python -m calion.run`` the return value is passed to
    :func:`sys.exit` (see bottom of this module).
    """
    parser = argparse.ArgumentParser(
        description="CALION - District Heating Optimization Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Quick PF run
  python -m calion.run configs/scenarios/quick_test.yaml

  # Rolling Horizon with dashboard export
  python -m calion.run configs/scenarios/rh_full_system.yaml --dashboard

  # Override run mode via CLI
  python -m calion.run my_config.yaml --run-mode PF_THEN_RH

  # Sensitivity sweep over RH window sizes
  python -m calion.run my_config.yaml --run-mode RH_ONLY \\
      --sensitivity-horizon-hours 48,96,168

  # Multiple config files
  python -m calion.run base.yaml system.yaml scenario.yaml
""",
    )

    # -- positional: config files ------------------------------------------
    parser.add_argument(
        "configs",
        nargs="+",
        help="Config file(s) to load and merge",
    )

    # -- export flags ------------------------------------------------------
    parser.add_argument(
        "--dashboard", "-d",
        action="store_true",
        help="Save results for dashboard visualization (to outputs/workflows/)",
    )
    parser.add_argument(
        "--name", "-n",
        type=str,
        default=None,
        help="Name for the simulation run",
    )
    parser.add_argument(
        "--desc",
        type=str,
        default=None,
        help="Description for the simulation run",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Custom output directory",
    )
    parser.add_argument(
        "--save-lp",
        action="store_true",
        default=False,
        help=(
            "Copy the solved MILP model as model.lp into {outdir}/solver/ "
            "for post-hoc debugging and infeasibility analysis."
        ),
    )

    # -- workflow / override args (from workflow.py) ------------------------
    add_workflow_cli_args(parser)

    args = parser.parse_args(argv)

    # -- resolve overrides (CLI + env) -------------------------------------
    try:
        env_values = _gather_env_overrides()
    except ValueError as exc:
        parser.error(str(exc))

    values, horizon_value, step_value, overlap_value = _merge_cli_and_env(args, env_values)
    base_overrides = _build_override_dict(values)
    runs = _expand_sensitivity_runs(args, base_overrides, horizon_value, step_value, overlap_value)

    is_sweep = len(runs) > 1

    # -- banner ------------------------------------------------------------
    logger.info("=" * 70)
    logger.info("CALION - District Heating Optimization")
    logger.info("=" * 70)
    logger.info("Config files (%d):", len(args.configs))
    for path in args.configs:
        logger.info("  - %s", path)
    if is_sweep:
        logger.info("Sensitivity sweep: %d runs", len(runs))
    if args.dashboard:
        logger.info("Dashboard export: ENABLED")
        if args.name:
            logger.info("  Name: %s", args.name)

    # -- run loop ----------------------------------------------------------
    for idx, (horizon, step, overlap, override_cfg) in enumerate(runs, start=1):
        if is_sweep:
            logger.info(
                "[workflow] Sweep run %d/%d: horizon=%s, step=%s, overlap=%s",
                idx, len(runs), horizon, step, overlap,
            )

        result = _wf.run_workflow(args.configs, overrides=override_cfg or None)
        steps_label = " -> ".join(result.plan.steps)
        logger.info("[workflow] Executed steps: %s", steps_label)

        # -- summary -------------------------------------------------------
        _print_result_summary(result, args)

        # -- export --------------------------------------------------------
        if args.dashboard or args.dir:
            sweep_subdir = f"sweep_{idx:03d}" if is_sweep else None
            _export_result(result, args, sweep_subdir)

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_result_summary(result, args):
    """Log a concise cost / result summary."""

    def _cost_block(label, costs):
        if not costs:
            return
        logger.info("=== %s COSTS (objective.*) ===", label)
        for k, v in sorted(costs.items()):
            if not k.startswith("objective."):
                continue
            if not isinstance(v, (int, float)):
                continue
            if abs(v) <= 1e-3:
                continue
            logger.info("%-40s: %s", k, format(v, ",.2f"))

    if result.pf_result is not None:
        pf_obj = (result.pf_result.costs or {}).get("objective.OBJ_value_EUR")
        logger.info("  PF time steps: %d", len(result.pf_result.table))
        if pf_obj is not None:
            logger.info("  PF objective: %s", pf_obj)
        _cost_block("PF", result.pf_result.costs)

    if result.rh_result is not None:
        logger.info("  RH windows: %d", len(result.rh_result.windows))
        logger.info("  RH committed steps: %d", len(result.rh_result.table))

    if result.mpc_result is not None:
        _cost_block("MPC", getattr(result.mpc_result, "costs", None))

    if args.print_design and result.design is not None:
        hp_parts = ", ".join(sorted(result.design.heat_pumps.keys())) or "none"
        logger.info("  Design heat pumps: %s", hp_parts)
        if result.design.storage is not None:
            logger.info("  Storage design: %s", result.design.storage)


def _export_result(result, args, sweep_subdir):
    """Export a single workflow result (dashboard or standard)."""
    outdir = args.dir

    if sweep_subdir and outdir:
        outdir = str(Path(outdir) / sweep_subdir)
    elif sweep_subdir:
        from calion.io._output_paths import resolve_runs_dir
        outdir = str(Path(resolve_runs_dir()) / sweep_subdir)

    if args.dashboard:
        from calion.io.notebook_helpers import save_workflow_run

        save_dir = outdir or None  # None → resolve_workflows_dir() inside save_workflow_run
        output_dir = save_workflow_run(
            result,
            name=args.name or "CLI Simulation",
            description=args.desc or f"Config: {', '.join(args.configs)}",
            config_paths=args.configs,
            save_dir=save_dir,
        )
        logger.info("=" * 70)
        logger.info("SUCCESS! Results saved for dashboard:")
        logger.info("  %s", output_dir)
        logger.info("View in dashboard:  python start_dashboard.py")
        logger.info("=" * 70)
    else:
        export = _export_workflow_results(
            result,
            outdir=outdir,
            save_lp=args.save_lp,
        )
        logger.info("=" * 70)
        logger.info("SUCCESS! Results exported to:")
        logger.info("  %s", export["outdir"])
        if export.get("network_files"):
            logger.info("  Thermal network: %s/thermal_network/", export["outdir"])
        if export.get("lp_file"):
            logger.info("  LP model:        %s", export["lp_file"])
        logger.info("Tip: Use --dashboard flag to save for dashboard visualization")
        logger.info("Tip: Use --save-lp to export solver model for debugging")
        logger.info("=" * 70)


if __name__ == "__main__":
    raise SystemExit(main())
