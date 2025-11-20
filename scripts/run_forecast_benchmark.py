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


def get_all_methods():
    """Get complete set of all 7 methods for Set A comparison."""
    return [
        # 1. Perfect Forecast (PF) - Theoretical optimum
        ("PF", {
            "scenario": {
                "workflow": ["PF"],
            }
        }),

        # 2. RH-Perfect - Rolling horizon with perfect foresight (unrealistic)
        ("RH-Perfect", {
            "scenario": {
                "workflow": ["RH"],
                "fix_design": False,
                "rolling_horizon": {
                    "heat_horizon_hours": 168.0,
                    "step_hours": 24.0,
                    "terminal_policy": "free",
                }
            }
        }),

        # 3. PF→RH-Perfect - Two-stage with perfect operation (unrealistic)
        ("PF→RH-Perfect", {
            "scenario": {
                "workflow": ["PF", "RH"],
                "fix_design": True,
                "rolling_horizon": {
                    "heat_horizon_hours": 168.0,
                    "step_hours": 24.0,
                    "terminal_policy": "free",
                }
            }
        }),

        # 4. RH-Forecast-Persistence - Fully realistic, naive baseline
        ("RH-Forecast-Pers", {
            "scenario": {
                "workflow": ["MPC"],
                "fix_design": False,
                "mpc": {
                    "forecast_method": "persistence",
                    "forecast_horizon_hours": 168.0,
                    "update_frequency_hours": 24.0,
                }
            }
        }),

        # 5. RH-Forecast-Noisy - Fully realistic, better forecast
        ("RH-Forecast-Noisy", {
            "scenario": {
                "workflow": ["MPC"],
                "fix_design": False,
                "mpc": {
                    "forecast_method": "perfect_noise",
                    "forecast_horizon_hours": 168.0,
                    "update_frequency_hours": 24.0,
                    "noise_std_dev": 0.10,
                    "random_seed": 42,
                }
            }
        }),

        # 6. PF→RH-Forecast-Persistence - Optimal design + realistic operation (naive)
        ("PF→RH-Forecast-Pers", {
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

        # 7. PF→RH-Forecast-Noisy - Optimal design + realistic operation (best-case)
        ("PF→RH-Forecast-Noisy", {
            "scenario": {
                "workflow": ["PF", "MPC"],
                "fix_design": True,
                "mpc": {
                    "forecast_method": "perfect_noise",
                    "forecast_horizon_hours": 168.0,
                    "update_frequency_hours": 24.0,
                    "noise_std_dev": 0.10,
                    "random_seed": 42,
                }
            }
        }),
    ]


def get_standard_methods():
    """Get standard method set for comparison (subset of all methods)."""
    all_methods = get_all_methods()
    # Standard set: PF, RH-Perfect, RH-Forecast-Noisy, PF→RH-Forecast-Noisy
    return [m for m in all_methods if m[0] in [
        "PF", "RH-Perfect", "RH-Forecast-Noisy", "PF→RH-Forecast-Noisy"
    ]]


def get_full_methods():
    """Get comprehensive method set including all 7 + noise sensitivity variants."""
    methods = get_all_methods()

    # Add MPC noise sensitivity variants (5%, 15%, 20%)
    for noise_level in [0.05, 0.15, 0.20]:
        methods.append(
            (f"RH-Forecast-Noise{int(noise_level*100)}%", {
                "scenario": {
                    "workflow": ["MPC"],
                    "fix_design": False,
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
        methods.append(
            (f"PF→RH-Forecast-Noise{int(noise_level*100)}%", {
                "scenario": {
                    "workflow": ["PF", "MPC"],
                    "fix_design": True,
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


def get_available_methods():
    """Get dictionary of all available methods by name."""
    return {name: config for name, config in get_all_methods()}


def main():
    """Main benchmark runner."""
    parser = argparse.ArgumentParser(
        description="Run forecast methods benchmark comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all 7 methods (Set A)
  %(prog)s --mode all

  # Run only specific methods
  %(prog)s --methods PF RH-Forecast-Noisy PF→RH-Forecast-Noisy

  # Run all methods in parallel on 4 cores
  %(prog)s --mode all --parallel --jobs 4

  # Quick test (1 week)
  %(prog)s --mode quick

  # Full benchmark with Excel export
  %(prog)s --mode all --export-excel

Available methods:
  PF, RH-Perfect, PF→RH-Perfect,
  RH-Forecast-Pers, RH-Forecast-Noisy,
  PF→RH-Forecast-Pers, PF→RH-Forecast-Noisy
        """
    )
    parser.add_argument(
        "--mode",
        choices=["quick", "standard", "all", "full"],
        default="standard",
        help="Benchmark mode: quick (1 week, 3 methods), standard (4 methods), all (7 methods), full (7 + sensitivity)"
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        metavar="METHOD",
        help="Run only specific methods (e.g., --methods PF RH-Forecast-Noisy)"
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
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run methods in parallel (experimental)"
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=None,
        help="Number of parallel jobs (default: number of CPUs)"
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Export full results to Excel (in addition to CSV)"
    )
    parser.add_argument(
        "--list-methods",
        action="store_true",
        help="List all available methods and exit"
    )

    args = parser.parse_args()

    # List methods and exit
    if args.list_methods:
        print("\nAvailable methods:")
        print("="*70)
        for i, (name, _) in enumerate(get_all_methods(), 1):
            print(f"  {i}. {name}")
        print("\nUse --methods to select specific methods")
        print("Example: python scripts/run_forecast_benchmark.py --methods PF RH-Forecast-Noisy")
        return 0

    # Select methods
    if args.methods:
        # User specified methods
        available = get_available_methods()
        methods = []
        for method_name in args.methods:
            if method_name not in available:
                logger.error(f"Unknown method: {method_name}")
                logger.info(f"Available methods: {list(available.keys())}")
                return 1
            methods.append((method_name, available[method_name]))
        logger.info(f"Running CUSTOM selection ({len(methods)} methods)")
    elif args.mode == "quick":
        logger.info("Running QUICK benchmark (1 week, 3 methods)")
        methods = get_quick_methods()
    elif args.mode == "standard":
        logger.info("Running STANDARD benchmark (full year, 4 methods)")
        methods = get_standard_methods()
    elif args.mode == "all":
        logger.info("Running ALL methods (full year, 7 methods - Set A)")
        methods = get_all_methods()
    else:  # full
        logger.info("Running FULL benchmark (full year, 7 + sensitivity variants)")
        methods = get_full_methods()

    logger.info(f"Methods to run: {[m[0] for m in methods]}")
    logger.info(f"Output directory: {args.output_dir}")
    if args.parallel:
        logger.info(f"Parallel execution: enabled (jobs={args.jobs or 'auto'})")

    # Create benchmark suite
    base_configs = get_base_configs()
    suite = BenchmarkSuite(base_configs)

    # Run benchmark
    logger.info("\n" + "="*70)
    logger.info("STARTING BENCHMARK")
    logger.info("="*70 + "\n")

    try:
        if args.parallel:
            # Parallel execution
            results = run_parallel_benchmark(
                suite,
                methods,
                num_runs=args.num_runs,
                num_jobs=args.jobs,
                output_dir=args.output_dir,
            )
        else:
            # Sequential execution
            results = suite.run(
                methods=methods,
                num_runs=args.num_runs,
                save_intermediate=True,
                output_dir=args.output_dir,
            )

        # Export results to CSV
        csv_path = os.path.join(args.output_dir, "benchmark_results.csv")
        suite.export_results(results, csv_path)

        # Export to Excel if requested
        if args.export_excel:
            excel_path = os.path.join(args.output_dir, "benchmark_results.xlsx")
            export_to_excel(results, excel_path, base_configs)
            logger.info(f"  Excel export: {excel_path}")

        # Print summary
        suite.print_summary(results)

        logger.info(f"\n✅ Benchmark complete! Results saved to {csv_path}")

        return 0

    except Exception as e:
        logger.error(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_parallel_benchmark(suite, methods, num_runs, num_jobs, output_dir):
    """Run benchmark methods in parallel using multiprocessing.

    Parameters
    ----------
    suite : BenchmarkSuite
        Benchmark suite instance
    methods : list
        List of (method_name, config_overrides) tuples
    num_runs : int
        Number of repetitions per method
    num_jobs : int or None
        Number of parallel jobs (None = use all CPUs)
    output_dir : str
        Output directory for intermediate results

    Returns
    -------
    list
        List of BenchmarkMetrics for all methods
    """
    import multiprocessing as mp
    from functools import partial

    logger.info(f"Starting parallel execution with {num_jobs or 'all'} cores...")

    # Create work items (method, run_index)
    work_items = []
    for method_name, config_overrides in methods:
        for run_idx in range(num_runs):
            work_items.append((method_name, config_overrides, run_idx))

    # Worker function
    def run_single(item, base_configs):
        method_name, config_overrides, run_idx = item
        from energis.run.rolling_horizon import run_workflow
        import time

        logger.info(f"[Worker] Running {method_name} (run {run_idx + 1})")
        start_time = time.time()

        try:
            result = run_workflow(base_configs, config_overrides)
            elapsed = time.time() - start_time
            logger.info(f"[Worker] Completed {method_name} in {elapsed:.1f}s")
            return (True, method_name, run_idx, result, elapsed)
        except Exception as e:
            logger.error(f"[Worker] Failed {method_name}: {e}")
            return (False, method_name, run_idx, str(e), 0)

    # Run in parallel
    worker_fn = partial(run_single, base_configs=suite.base_configs)

    with mp.Pool(processes=num_jobs) as pool:
        worker_results = pool.map(worker_fn, work_items)

    # Process results
    all_results = []
    pf_cost = None

    for success, method_name, run_idx, data, elapsed in worker_results:
        if not success:
            logger.error(f"Method {method_name} failed: {data}")
            continue

        result = data  # WorkflowResult

        # Extract PF baseline cost
        if method_name == "PF" and pf_cost is None and result.pf_result:
            pf_cost = sum(result.pf_result.costs.values())

        # Find config overrides
        config_overrides = next((cfg for name, cfg in methods if name == method_name), {})

        # Extract metrics
        metrics = suite._extract_metrics(
            method_name=method_name,
            run_index=run_idx,
            result=result,
            solve_time=elapsed,
            pf_baseline_cost=pf_cost,
            config_overrides=config_overrides,
        )

        all_results.append(metrics)

    return all_results


def export_to_excel(results, excel_path, base_configs):
    """Export benchmark results to Excel with detailed sheets.

    Parameters
    ----------
    results : list
        List of BenchmarkMetrics
    excel_path : str
        Output Excel file path
    base_configs : list
        Base configuration files
    """
    try:
        from energis.io.exporter import write_scenario_workbook
    except ImportError:
        logger.warning("openpyxl not available, skipping Excel export")
        return

    try:
        # Group results by method
        methods_data = {}
        for r in results:
            if r.method not in methods_data:
                methods_data[r.method] = []
            methods_data[r.method].append(r)

        # Build metadata
        meta_sections = {
            "Benchmark Info": {
                "Total Methods": len(methods_data),
                "Total Runs": len(results),
                "Base Configs": ", ".join(base_configs),
            }
        }

        # Build costs table
        cost_sections = {}
        for method, method_results in methods_data.items():
            avg_cost = sum(r.total_cost_eur for r in method_results) / len(method_results)
            avg_capex = sum(r.capex_eur for r in method_results) / len(method_results)
            avg_opex = sum(r.opex_eur for r in method_results) / len(method_results)

            cost_sections[method] = {
                "total_cost_eur": avg_cost,
                "capex_eur": avg_capex,
                "opex_eur": avg_opex,
                "num_runs": len(method_results),
            }

        # Build design table
        design_sections = {}
        for method, method_results in methods_data.items():
            r = method_results[0]  # Use first run
            design_sections[method] = {
                "total_hp_capacity_mw": r.total_hp_capacity_mw,
                "storage_capacity_mwh": r.storage_capacity_mwh,
                "storage_power_mw": r.storage_power_mw,
            }

        write_scenario_workbook(
            excel_path,
            meta_sections=meta_sections,
            cost_sections=cost_sections,
            design=design_sections,
            timeseries_sections=None,  # Too large for Excel
        )

        logger.info(f"Exported results to Excel: {excel_path}")

    except Exception as e:
        logger.error(f"Excel export failed: {e}")
        logger.warning("Continuing without Excel export...")


if __name__ == "__main__":
    sys.exit(main())
