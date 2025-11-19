#!/usr/bin/env python
"""Benchmark runner for forecast methods comparison.

This script runs a comprehensive comparison of forecast methods (PF, RH, MPC)
and generates comparison tables and plots.

Usage:
    python scripts/run_forecast_benchmark.py
    python scripts/run_forecast_benchmark.py --quick  # Fast test
    python scripts/run_forecast_benchmark.py --full   # All methods + variants
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from energis.comparison.benchmark import BenchmarkSuite

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def get_base_configs():
    """Get standard base configuration files."""
    return [
        "configs/base.yaml",
        "configs/tech_catalog.yaml",
        "configs/sites/default.site.yaml",
        "configs/systems/baseline.system.yaml",
    ]


def get_quick_methods():
    """Get minimal method set for quick testing."""
    return [
        ("PF", {
            "scenario": {
                "workflow": ["PF"],
                "horizon": {"type": "week"},  # Only 1 week for quick test
            }
        }),
        ("RH", {
            "scenario": {
                "workflow": ["RH"],
                "horizon": {"type": "week"},
                "rolling_horizon": {
                    "heat_horizon_hours": 168.0,
                    "step_hours": 24.0,
                }
            }
        }),
        ("MPC-Persistence", {
            "scenario": {
                "workflow": ["MPC"],
                "horizon": {"type": "week"},
                "mpc": {
                    "forecast_method": "persistence",
                    "forecast_horizon_hours": 168.0,
                    "update_frequency_hours": 24.0,
                }
            }
        }),
    ]


def get_standard_methods():
    """Get standard method set for comparison."""
    return [
        # Baseline: Perfect Forecast
        ("PF", {
            "scenario": {
                "workflow": ["PF"],
            }
        }),

        # Rolling Horizon: Myopic
        ("RH", {
            "scenario": {
                "workflow": ["RH"],
                "rolling_horizon": {
                    "heat_horizon_hours": 168.0,
                    "step_hours": 24.0,
                }
            }
        }),

        # PF→RH: Optimal design, myopic operation
        ("PF→RH", {
            "scenario": {
                "workflow": ["PF", "RH"],
                "fix_design": True,
                "rolling_horizon": {
                    "heat_horizon_hours": 168.0,
                    "step_hours": 24.0,
                }
            }
        }),

        # MPC with Persistence: Worst MPC case
        ("MPC-Persistence", {
            "scenario": {
                "workflow": ["MPC"],
                "mpc": {
                    "forecast_method": "persistence",
                    "forecast_horizon_hours": 168.0,
                    "update_frequency_hours": 24.0,
                }
            }
        }),

        # MPC with Perfect+Noise: Realistic MPC
        ("MPC-Noise10%", {
            "scenario": {
                "workflow": ["MPC"],
                "mpc": {
                    "forecast_method": "perfect_noise",
                    "forecast_horizon_hours": 168.0,
                    "update_frequency_hours": 24.0,
                    "noise_std_dev": 0.10,
                    "random_seed": 42,
                }
            }
        }),

        # PF→MPC: Optimal design, adaptive operation
        ("PF→MPC", {
            "scenario": {
                "workflow": ["PF", "MPC"],
                "fix_design": True,
                "mpc": {
                    "forecast_method": "persistence",
                    "forecast_horizon_hours": 168.0,
                    "update_frequency_hours": 24.0,
                }
            }
        }),
    ]


def get_full_methods():
    """Get comprehensive method set including variants."""
    methods = get_standard_methods()

    # Add MPC noise variants
    for noise_level in [0.05, 0.15, 0.20]:
        methods.append(
            (f"MPC-Noise{int(noise_level*100)}%", {
                "scenario": {
                    "workflow": ["MPC"],
                    "mpc": {
                        "forecast_method": "perfect_noise",
                        "forecast_horizon_hours": 168.0,
                        "update_frequency_hours": 24.0,
                        "noise_std_dev": noise_level,
                        "random_seed": 42,
                    }
                }
            })
        )

    return methods


def main():
    """Main benchmark runner."""
    parser = argparse.ArgumentParser(
        description="Run forecast methods benchmark comparison"
    )
    parser.add_argument(
        "--mode",
        choices=["quick", "standard", "full"],
        default="standard",
        help="Benchmark mode (quick=1 week, standard=full year basic methods, full=all variants)"
    )
    parser.add_argument(
        "--output-dir",
        default="exports/benchmark",
        help="Output directory for results"
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=1,
        help="Number of runs per method (for stochastic methods)"
    )

    args = parser.parse_args()

    # Select methods based on mode
    if args.mode == "quick":
        logger.info("Running QUICK benchmark (1 week, 3 methods)")
        methods = get_quick_methods()
    elif args.mode == "standard":
        logger.info("Running STANDARD benchmark (full year, 6 methods)")
        methods = get_standard_methods()
    else:  # full
        logger.info("Running FULL benchmark (full year, all variants)")
        methods = get_full_methods()

    logger.info(f"Methods to run: {[m[0] for m in methods]}")
    logger.info(f"Output directory: {args.output_dir}")

    # Create benchmark suite
    base_configs = get_base_configs()
    suite = BenchmarkSuite(base_configs)

    # Run benchmark
    logger.info("\n" + "="*70)
    logger.info("STARTING BENCHMARK")
    logger.info("="*70 + "\n")

    try:
        results = suite.run(
            methods=methods,
            num_runs=args.num_runs,
            save_intermediate=True,
            output_dir=args.output_dir,
        )

        # Export results
        csv_path = os.path.join(args.output_dir, "benchmark_results.csv")
        suite.export_results(results, csv_path)

        # Print summary
        suite.print_summary(results)

        logger.info(f"\n✅ Benchmark complete! Results saved to {csv_path}")

        return 0

    except Exception as e:
        logger.error(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
