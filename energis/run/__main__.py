#!/usr/bin/env python3
"""
Command-line interface for EnerGIS framework.

Usage:
    python -m energis.run configs/stadtbach.yaml
    python -m energis.run <config1.yaml> <config2.yaml> ...
"""

import sys
from pathlib import Path
from energis.run import rolling_horizon as rh


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m energis.run <config.yaml> [config2.yaml ...]")
        print()
        print("Examples:")
        print("  python -m energis.run configs/stadtbach.yaml")
        print("  python -m energis.run configs/stadtbach.yaml configs/overrides.yaml")
        sys.exit(1)

    config_paths = sys.argv[1:]

    # Validate paths
    for path in config_paths:
        if not Path(path).exists():
            print(f"Error: Config file not found: {path}")
            sys.exit(1)

    print(f"Running EnerGIS with {len(config_paths)} config files:")
    for path in config_paths:
        print(f"  - {path}")
    print()

    try:
        workflow = rh.run_workflow(config_paths)
        result = rh.export_workflow_results(workflow)
        print(f"\n✓ Success! Results exported to: {result['outdir']}")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
