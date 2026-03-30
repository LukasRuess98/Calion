"""Benchmark suite for comparing forecast methods (PF, RH, MPC, etc.)."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Any, Optional

from calion.logging_config import get_logger

logger = get_logger(__name__)

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkMetrics:
    """Standardized metrics for method comparison."""

    # Identification
    method: str
    run_index: int

    # Economic
    total_cost_eur: float
    capex_eur: float
    opex_eur: float
    cost_vs_pf_percent: float  # Optimality gap vs. PF

    # Design decisions
    total_hp_capacity_mw: float
    storage_capacity_mwh: float
    storage_power_mw: float

    # Operation
    grid_import_mwh: float
    grid_export_mwh: float
    total_demand_mwh: float

    # Computational
    solve_time_seconds: float
    num_windows: int
    avg_window_time_seconds: float

    # Cost breakdown
    cost_energy: float
    cost_demand_charge: float
    cost_co2: float
    cost_breakdown: Dict[str, float]

    # Metadata
    config_hash: str
    timestamp: str


class BenchmarkSuite:
    """Benchmark suite for systematic method comparison.

    Usage:
        suite = BenchmarkSuite(base_configs=["configs/base.yaml", ...])
        methods = [
            ("PF", {"scenario": {"workflow": ["PF"]}}),
            ("RH", {"scenario": {"workflow": ["RH"]}}),
            ("MPC", {"scenario": {"workflow": ["MPC"]}}),
        ]
        results = suite.run(methods, num_runs=1)
        suite.export_results(results, "outputs/runs/benchmark_results.csv")
    """

    def __init__(self, base_configs: List[str]):
        """Initialize benchmark suite.

        Parameters
        ----------
        base_configs:
            List of base configuration file paths (base, tech_catalog, site, system)
        """
        self.base_configs = base_configs
        self.results: List[BenchmarkMetrics] = []

    def run(
        self,
        methods: List[Tuple[str, Dict[str, Any]]],
        num_runs: int = 1,
        save_intermediate: bool = True,
        output_dir: str = "outputs/runs/benchmark",
    ) -> List[BenchmarkMetrics]:
        """Run benchmark comparison of multiple methods.

        Parameters
        ----------
        methods:
            List of (method_name, config_overrides) tuples
            Example: [("PF", {"scenario": {"workflow": ["PF"]}}), ...]
        num_runs:
            Number of repetitions for stochastic methods
        save_intermediate:
            Save results after each method completes
        output_dir:
            Directory for intermediate results

        Returns
        -------
        List of benchmark metrics for all methods and runs
        """
        from calion.run.rolling_horizon import run_workflow

        os.makedirs(output_dir, exist_ok=True)

        all_results = []

        # Run baseline PF first (for cost_vs_pf calculation)
        pf_cost = None
        for method_name, overrides in methods:
            if method_name == "PF":
                logger.info("Running PF baseline for comparison...")
                result = run_workflow(self.base_configs, overrides)
                if result.pf_result:
                    pf_cost = sum(result.pf_result.costs.values())
                    logger.info(f"PF baseline cost: {pf_cost:.2f} EUR")
                break

        if pf_cost is None:
            logger.warning("No PF baseline found, using first method as reference")

        # Run all methods
        for method_name, overrides in methods:
            logger.info(f"\n{'='*70}")
            logger.info(f"Running method: {method_name}")
            logger.info(f"{'='*70}")

            for run_idx in range(num_runs):
                logger.info(f"  Run {run_idx + 1}/{num_runs}")

                try:
                    # Start timer
                    start_time = time.time()

                    # Run workflow
                    result = run_workflow(self.base_configs, overrides)

                    # Stop timer
                    elapsed = time.time() - start_time

                    # Extract metrics
                    metrics = self._extract_metrics(
                        method_name=method_name,
                        run_index=run_idx,
                        result=result,
                        solve_time=elapsed,
                        pf_baseline_cost=pf_cost,
                        config_overrides=overrides,
                    )

                    all_results.append(metrics)

                    logger.info(f"    Total cost: {metrics.total_cost_eur:.2f} EUR")
                    logger.info(f"    Solve time: {metrics.solve_time_seconds:.1f}s")
                    if metrics.cost_vs_pf_percent is not None:
                        logger.info(f"    vs PF: +{metrics.cost_vs_pf_percent:.1f}%")

                except Exception as e:
                    logger.error(f"  Error running {method_name}: {e}")
                    import traceback
                    traceback.print_exc()

            # Save intermediate results
            if save_intermediate:
                self._save_intermediate(all_results, output_dir, method_name)

        self.results = all_results
        return all_results

    def _extract_metrics(
        self,
        method_name: str,
        run_index: int,
        result: Any,
        solve_time: float,
        pf_baseline_cost: Optional[float],
        config_overrides: Dict[str, Any],
    ) -> BenchmarkMetrics:
        """Extract standardized metrics from workflow result."""
        import hashlib
        from datetime import datetime

        # Get the active result (last executed method)
        active_result = None
        num_windows = 0

        if result.mpc_result:
            active_result = result.mpc_result
            num_windows = len(result.mpc_result.windows) if hasattr(result.mpc_result, 'windows') else 0
        elif result.rh_result:
            active_result = result.rh_result
            num_windows = len(result.rh_result.windows) if hasattr(result.rh_result, 'windows') else 0
        elif result.pf_result:
            active_result = result.pf_result
            num_windows = 1

        if active_result is None:
            raise ValueError(f"No results found for method {method_name}")

        # Extract costs
        costs = active_result.costs
        total_cost = sum(costs.values())

        # Extract CAPEX (investment costs)
        capex = sum(costs.get(k, 0) for k in [
            "objective.Capex_cost_EUR",
            "objective.Activation_cost_EUR",
            "objective.Tie_breaker_cost_EUR",
            "objective.Storage_installation_cost_EUR"
        ])
        opex = total_cost - capex

        # Calculate vs PF
        cost_vs_pf = None
        if pf_baseline_cost and pf_baseline_cost > 0:
            cost_vs_pf = ((total_cost / pf_baseline_cost) - 1) * 100

        # Extract design
        design = result.design
        total_hp_cap = 0.0
        storage_cap = 0.0
        storage_pow = 0.0

        if design:
            if hasattr(design, 'heat_pumps') and design.heat_pumps:
                for hp_data in design.heat_pumps.values():
                    total_hp_cap += hp_data.get('capacity_mw', 0)

            if hasattr(design, 'storage') and design.storage:
                storage_cap = design.storage.get('capacity_mwh', 0)
                storage_pow = design.storage.get('power_mw', 0)

        # Extract operational metrics
        series = active_result.series if hasattr(active_result, 'series') else {}
        grid_import = sum(series.get('P_buy', [0])) if 'P_buy' in series else 0
        grid_export = sum(series.get('P_sell', [0])) if 'P_sell' in series else 0
        demand = sum(series.get('demand_mw', [0])) if 'demand_mw' in series else 0

        # Config hash
        config_str = json.dumps(config_overrides, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]

        # Timing
        avg_window_time = solve_time / num_windows if num_windows > 0 else solve_time

        return BenchmarkMetrics(
            method=method_name,
            run_index=run_index,
            total_cost_eur=total_cost,
            capex_eur=capex,
            opex_eur=opex,
            cost_vs_pf_percent=cost_vs_pf,
            total_hp_capacity_mw=total_hp_cap,
            storage_capacity_mwh=storage_cap,
            storage_power_mw=storage_pow,
            grid_import_mwh=grid_import,
            grid_export_mwh=grid_export,
            total_demand_mwh=demand,
            solve_time_seconds=solve_time,
            num_windows=num_windows,
            avg_window_time_seconds=avg_window_time,
            cost_energy=costs.get('objective.Grid_energy_cost_EUR', 0),
            cost_demand_charge=costs.get('objective.Demand_charge_cost_EUR', 0),
            cost_co2=costs.get('objective.CO2_cost_EUR', 0),
            cost_breakdown=dict(costs),
            config_hash=config_hash,
            timestamp=datetime.now().isoformat(),
        )

    def _save_intermediate(self, results: List[BenchmarkMetrics], output_dir: str, method_name: str):
        """Save intermediate results to JSON."""
        filepath = os.path.join(output_dir, f"intermediate_{method_name}.json")
        with open(filepath, 'w', encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        logger.info(f"  Saved intermediate results to {filepath}")

    def export_results(self, results: List[BenchmarkMetrics], output_path: str):
        """Export benchmark results to CSV.

        Parameters
        ----------
        results:
            List of benchmark metrics
        output_path:
            Output CSV file path
        """
        import csv

        if not results:
            logger.warning("No results to export")
            return

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Write CSV
        with open(output_path, 'w', newline='', encoding="utf-8") as f:
            # Get fieldnames from first result
            fieldnames = [
                'method', 'run_index',
                'total_cost_eur', 'capex_eur', 'opex_eur', 'cost_vs_pf_percent',
                'total_hp_capacity_mw', 'storage_capacity_mwh', 'storage_power_mw',
                'grid_import_mwh', 'grid_export_mwh', 'total_demand_mwh',
                'solve_time_seconds', 'num_windows', 'avg_window_time_seconds',
                'cost_energy', 'cost_demand_charge', 'cost_co2',
                'config_hash', 'timestamp',
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                row = {k: getattr(result, k, None) for k in fieldnames}
                writer.writerow(row)

        logger.info(f"Exported {len(results)} results to {output_path}")

    def print_summary(self, results: Optional[List[BenchmarkMetrics]] = None):
        """Print summary table of results.

        Parameters
        ----------
        results:
            List of benchmark metrics (uses self.results if None)
        """
        if results is None:
            results = self.results

        if not results:
            logger.info("No results to display")
            return

        # Group by method
        methods = {}
        for r in results:
            if r.method not in methods:
                methods[r.method] = []
            methods[r.method].append(r)

        # Print header
        logger.info("="*70)
        logger.info("BENCHMARK RESULTS SUMMARY")
        logger.info("="*70)
        logger.info(f"{'Method':<15} {'Runs':>5} {'Total Cost':>15} {'vs PF':>10} {'CAPEX':>12} {'OPEX':>12} {'Time':>10}")
        logger.info("-"*70)

        # Print each method
        for method_name in sorted(methods.keys()):
            method_results = methods[method_name]
            n = len(method_results)

            # Calculate averages
            avg_cost = sum(r.total_cost_eur for r in method_results) / n
            avg_capex = sum(r.capex_eur for r in method_results) / n
            avg_opex = sum(r.opex_eur for r in method_results) / n
            avg_time = sum(r.solve_time_seconds for r in method_results) / n

            # Get vs PF (use first non-None value)
            vs_pf = next((r.cost_vs_pf_percent for r in method_results if r.cost_vs_pf_percent is not None), None)
            vs_pf_str = f"+{vs_pf:.1f}%" if vs_pf is not None else "baseline"

            print(f"{method_name:<15} {n:>5} {avg_cost:>15,.0f} {vs_pf_str:>10} "
                  f"{avg_capex:>12,.0f} {avg_opex:>12,.0f} {avg_time:>8.1f}s")

        logger.info("="*100)


def run_method_comparison(
    base_configs: List[str],
    methods: List[Tuple[str, Dict[str, Any]]],
    num_runs: int = 1,
    output_dir: str = "outputs/runs/benchmark",
) -> List[BenchmarkMetrics]:
    """Convenience function to run method comparison.

    Parameters
    ----------
    base_configs:
        List of base configuration file paths
    methods:
        List of (method_name, config_overrides) tuples
    num_runs:
        Number of repetitions
    output_dir:
        Output directory

    Returns
    -------
    List of benchmark metrics

    Example:
        results = run_method_comparison(
            base_configs=["configs/base.yaml", ...],
            methods=[
                ("PF", {"scenario": {"workflow": ["PF"]}}),
                ("RH", {"scenario": {"workflow": ["RH"]}}),
                ("MPC", {"scenario": {"workflow": ["MPC"]}}),
            ],
            num_runs=1,
        )
    """
    suite = BenchmarkSuite(base_configs)
    results = suite.run(methods, num_runs=num_runs, output_dir=output_dir)

    # Export and print summary
    csv_path = os.path.join(output_dir, "benchmark_results.csv")
    suite.export_results(results, csv_path)
    suite.print_summary(results)

    return results
