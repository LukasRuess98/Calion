#!/usr/bin/env python3
"""
Command-line interface for EnerGIS framework.

Usage:
    python -m energis.run <config1.yaml> <config2.yaml> ...
    python -m energis.run configs/presets/quick_test.yaml
    python -m energis.run configs/presets/rh_full_system.yaml --dashboard

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


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='EnerGIS - District Heating Optimization Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test
  python -m energis.run configs/presets/quick_test.yaml

  # Rolling Horizon with dashboard export
  python -m energis.run configs/presets/rh_full_system.yaml --dashboard

  # With custom name
  python -m energis.run configs/presets/rh_full_system.yaml --dashboard --name "Baseline Q1"

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

    args = parser.parse_args()

    # Validate paths
    for path in args.configs:
        if not Path(path).exists():
            print(f"Error: Config file not found: {path}")
            sys.exit(1)

    print("=" * 70)
    print("EnerGIS - District Heating Optimization")
    print("=" * 70)
    print(f"\nConfig files ({len(args.configs)}):")
    for path in args.configs:
        print(f"  - {path}")

    if args.dashboard:
        print(f"\nDashboard export: ENABLED")
        if args.name:
            print(f"  Name: {args.name}")
        if args.desc:
            print(f"  Description: {args.desc}")

    print()

    try:
        # Run optimization
        workflow = rh.run_workflow(args.configs)

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
            print(f"\n" + "=" * 70)
            print(f"SUCCESS! Results saved for dashboard:")
            print(f"  {output_dir}")
            print(f"\nView in dashboard:")
            print(f"  python start_dashboard.py")
            print("=" * 70)
        else:
            # Standard export to exports/
            result = rh.export_workflow_results(workflow)
            print(f"\n" + "=" * 70)
            print(f"SUCCESS! Results exported to:")
            print(f"  {result['outdir']}")
            print(f"\nTip: Use --dashboard flag to save for dashboard visualization")
            print("=" * 70)

        sys.exit(0)

    except Exception as e:
        print(f"\n" + "=" * 70)
        print(f"ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
