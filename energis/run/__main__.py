#!/usr/bin/env python3
"""
Command-line interface for EnerGIS framework.

Usage:
    python -m energis.run <config1.yaml> <config2.yaml> ...
    python -m energis.run configs/scenarios/quick_test.yaml
    python -m energis.run configs/scenarios/rh_full_system.yaml --dashboard

Options:
    --dashboard     Save results for dashboard (to notebooks/saved_workflows/)
    --name NAME     Name for the simulation run
    --desc DESC     Description for the simulation run
    --dir DIR       Custom output directory (default: notebooks/saved_workflows/ with --dashboard)
"""

import argparse
import sys
from pathlib import Path
from energis.run import rolling_horizon as rh

from energis.logging_config import get_logger

logger = get_logger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='EnerGIS - District Heating Optimization Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test
  python -m energis.run configs/scenarios/quick_test.yaml

  # Rolling Horizon with dashboard export
  python -m energis.run configs/scenarios/rh_full_system.yaml --dashboard

  # With custom name
  python -m energis.run configs/scenarios/rh_full_system.yaml --dashboard --name "Baseline Q1"

  # Multiple config files
  python -m energis.run configs/00_base/solver.yaml configs/03_systems/full.yaml configs/04_scenarios/rh_q1_2023.yaml
        """
    )

    parser.add_argument(
        'configs',
        nargs='+',
        help='Config file(s) to load and merge'
    )

    parser.add_argument(
        '--dashboard', '-d',
        action='store_true',
        help='Save results for dashboard visualization (to notebooks/saved_workflows/)'
    )

    parser.add_argument(
        '--name', '-n',
        type=str,
        default=None,
        help='Name for the simulation run'
    )

    parser.add_argument(
        '--desc',
        type=str,
        default=None,
        help='Description for the simulation run'
    )

    parser.add_argument(
        '--dir',
        type=str,
        default=None,
        help='Custom output directory'
    )

    parser.add_argument(
        '--save-lp',
        action='store_true',
        default=False,
        help=(
            'Copy the solved MILP model as model.lp into {outdir}/solver/ '
            'for post-hoc debugging and infeasibility analysis. '
            'Requires output.export_solver_solution: true in config (default).'
        ),
    )

    args = parser.parse_args()

    # Validate paths
    for path in args.configs:
        if not Path(path).exists():
            logger.info(f"Error: Config file not found: {path}")
            sys.exit(1)

    logger.info("="*70)
    logger.info("EnerGIS - District Heating Optimization")
    logger.info("="*70)
    logger.info(f"\nConfig files ({len(args.configs)}):")
    for path in args.configs:
        logger.info(f"  - {path}")

    if args.dashboard:
        logger.info(f"\nDashboard export: ENABLED")
        if args.name:
            logger.info(f"  Name: {args.name}")
        if args.desc:
            logger.info(f"  Description: {args.desc}")


    try:
        # Run optimization
        workflow = rh.run_workflow(args.configs)
                # NEU: PF- und MPC-Kostenblock in der Konsole ausgeben
                # NEU: PF- und MPC-Kostenblock in der Konsole ausgeben
        def _print_cost_block(label, costs):
            if not costs:
                return
            logger.info(f"\n=== {label} COSTS (objective.*) ===")
            for k, v in sorted(costs.items()):
                # Nur objective.*-Keys und nur numerische Werte ausgeben
                if not k.startswith("objective."):
                    continue
                if not isinstance(v, (int, float)):   # Strings, dicts etc. überspringen
                    continue
                if abs(v) <= 1e-3:
                    continue
                logger.info(f"{k:40s}: {v:,.2f}")
                
        if workflow.pf_result and workflow.pf_result.costs:
            _print_cost_block("PF", workflow.pf_result.costs)

        if workflow.mpc_result and workflow.mpc_result.costs:
            _print_cost_block("MPC", workflow.mpc_result.costs)
        
        # Export results
        if args.dashboard:
            # Use save_workflow_run for dashboard compatibility
            from energis.io.notebook_helpers import save_workflow_run

            save_dir = args.dir or "notebooks/saved_workflows"
            output_dir = save_workflow_run(
                workflow,
                name=args.name or "CLI Simulation",
                description=args.desc or f"Config: {', '.join(args.configs)}",
                config_paths=args.configs,
                save_dir=save_dir,
            )
            logger.info("=" * 70)
            logger.info(f"SUCCESS! Results saved for dashboard:")
            logger.info(f"  {output_dir}")
            logger.info(f"\nView in dashboard:")
            logger.info(f"  python start_dashboard.py")
            logger.info("="*70)
        else:
            # Standard export to exports/
            result = rh.export_workflow_results(
                workflow,
                outdir=args.dir,
                save_lp=args.save_lp,
            )
            logger.info("=" * 70)
            logger.info(f"SUCCESS! Results exported to:")
            logger.info(f"  {result['outdir']}")
            if result.get('network_files'):
                logger.info(f"  Thermal network: {result['outdir']}/thermal_network/")
            if result.get('lp_file'):
                logger.info(f"  LP model:        {result['lp_file']}")
            logger.info(f"\nTip: Use --dashboard flag to save for dashboard visualization")
            logger.info(f"Tip: Use --save-lp to export solver model for debugging")
            logger.info("="*70)

        sys.exit(0)

    except Exception as e:
        logger.info("=" * 70)
        logger.info(f"ERROR: {e}")
        logger.info("="*70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
