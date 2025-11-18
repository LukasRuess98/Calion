#!/usr/bin/env python3
"""
Automated EnerGIS vs. oemof Comparison Script
==============================================

This script runs both EnerGIS and oemof-solph on identical problems
and produces a comprehensive comparison report.

Usage:
    python run_comparison.py --scenario tiny        # 24h test
    python run_comparison.py --scenario small       # 168h (1 week)
    python run_comparison.py --all                  # All scenarios
    python run_comparison.py --parity               # Parity check only

Author: For Applied Energy benchmarking
Date: 2025-11-18
"""

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Any
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Import benchmark implementations
from oemof_implementation import run_oemof_benchmark, OemofBenchmarkConfig, generate_synthetic_timeseries

# TODO: Import EnerGIS implementation when ready
# from energis_implementation import run_energis_benchmark

# ============================================================
# CONFIGURATION
# ============================================================

SCENARIOS = {
    'tiny': {
        'hours': 24,
        'description': '24h parity check',
        'expected_runtime_s': 10,
    },
    'small': {
        'hours': 168,
        'description': '1 week',
        'expected_runtime_s': 60,
    },
    'medium': {
        'hours': 720,
        'description': '1 month',
        'expected_runtime_s': 300,
    },
    'large': {
        'hours': 2160,
        'description': '3 months',
        'expected_runtime_s': 1800,
    },
    'full_year': {
        'hours': 8760,
        'description': 'Full year',
        'expected_runtime_s': 3600,
    },
}

RESULTS_DIR = Path(__file__).parent / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# COMPARISON FUNCTIONS
# ============================================================

def compare_results(energis_results: Dict[str, Any],
                   oemof_results: Dict[str, Any],
                   tolerance: float = 0.01) -> Dict[str, Any]:
    """
    Compare results from EnerGIS and oemof.

    Parameters
    ----------
    energis_results : dict
        Results from EnerGIS benchmark
    oemof_results : dict
        Results from oemof benchmark
    tolerance : float
        Relative tolerance for parity check (default: 1%)

    Returns
    -------
    comparison : dict
        Comparison metrics and pass/fail status
    """
    comparison = {
        'scenario': energis_results.get('hours', oemof_results['hours']),
        'timestamp': pd.Timestamp.now().isoformat(),
    }

    # Objective value comparison
    obj_energis = energis_results.get('objective_value')
    obj_oemof = oemof_results['objective_value']

    if obj_energis is not None and obj_oemof is not None:
        abs_diff = abs(obj_energis - obj_oemof)
        rel_diff = abs_diff / obj_oemof

        comparison['objective'] = {
            'energis': obj_energis,
            'oemof': obj_oemof,
            'absolute_difference': abs_diff,
            'relative_difference_pct': rel_diff * 100,
            'parity_check': rel_diff <= tolerance,
        }
    else:
        comparison['objective'] = {'error': 'Missing objective values'}

    # Runtime comparison
    time_energis = energis_results.get('total_time_s')
    time_oemof = oemof_results['total_time_s']

    if time_energis and time_oemof:
        speedup = time_oemof / time_energis if time_energis > 0 else np.inf

        comparison['runtime'] = {
            'energis_s': time_energis,
            'oemof_s': time_oemof,
            'speedup_factor': speedup,  # > 1 means EnerGIS is faster
            'difference_s': time_energis - time_oemof,
        }

    # Model size comparison
    comparison['model_size'] = {
        'energis': {
            'n_variables': energis_results.get('n_variables'),
            'n_constraints': energis_results.get('n_constraints'),
        },
        'oemof': {
            'n_variables': oemof_results.get('n_variables'),
            'n_constraints': oemof_results.get('n_constraints'),
        }
    }

    # Capacity comparison
    cap_energis = energis_results.get('capacities', {})
    cap_oemof = oemof_results.get('capacities', {})

    if cap_energis and cap_oemof:
        cap_comparison = {}
        all_components = set(cap_energis.keys()) | set(cap_oemof.keys())

        for comp in all_components:
            val_energis = cap_energis.get(comp, 0)
            val_oemof = cap_oemof.get(comp, 0)

            if val_oemof > 0:
                rel_diff = abs(val_energis - val_oemof) / val_oemof
            else:
                rel_diff = 0 if val_energis == 0 else np.inf

            cap_comparison[comp] = {
                'energis_mw': val_energis,
                'oemof_mw': val_oemof,
                'rel_diff_pct': rel_diff * 100,
            }

        comparison['capacities'] = cap_comparison

    return comparison


def print_comparison_summary(comparison: Dict[str, Any]):
    """Print formatted comparison summary."""
    print(f"\n{'='*70}")
    print(f"COMPARISON SUMMARY")
    print(f"{'='*70}")

    # Objective
    if 'objective' in comparison and 'energis' in comparison['objective']:
        obj = comparison['objective']
        print(f"\nObjective Value:")
        print(f"  EnerGIS: {obj['energis']:,.2f} EUR/year")
        print(f"  oemof:   {obj['oemof']:,.2f} EUR/year")
        print(f"  Difference: {obj['absolute_difference']:,.2f} EUR/year ({obj['relative_difference_pct']:.4f}%)")

        if obj['parity_check']:
            print(f"  ✓ PARITY CHECK PASSED")
        else:
            print(f"  ✗ PARITY CHECK FAILED (exceeds 1% tolerance)")

    # Runtime
    if 'runtime' in comparison:
        rt = comparison['runtime']
        print(f"\nRuntime:")
        print(f"  EnerGIS: {rt['energis_s']:.2f} s")
        print(f"  oemof:   {rt['oemof_s']:.2f} s")
        print(f"  Speedup: {rt['speedup_factor']:.2f}x", end='')

        if rt['speedup_factor'] > 1:
            print(f" (EnerGIS is FASTER)")
        elif rt['speedup_factor'] < 1:
            print(f" (oemof is FASTER)")
        else:
            print(f" (EQUAL)")

    # Model size
    if 'model_size' in comparison:
        ms = comparison['model_size']
        print(f"\nModel Size:")
        print(f"  EnerGIS: {ms['energis']['n_variables']:,} vars, {ms['energis']['n_constraints']:,} constraints")
        print(f"  oemof:   {ms['oemof']['n_variables']:,} vars, {ms['oemof']['n_constraints']:,} constraints")

    # Capacities
    if 'capacities' in comparison:
        print(f"\nInstalled Capacities:")
        for comp, vals in comparison['capacities'].items():
            print(f"  {comp:20s}: EnerGIS={vals['energis_mw']:6.2f} MW, "
                  f"oemof={vals['oemof_mw']:6.2f} MW, "
                  f"diff={vals['rel_diff_pct']:5.2f}%")


def export_comparison_table(comparisons: list, output_file: Path):
    """Export comparison results as a table for the paper."""
    rows = []

    for comp in comparisons:
        row = {
            'Scenario': f"{comp['scenario']}h",
        }

        # Objective values
        if 'objective' in comp and 'energis' in comp['objective']:
            obj = comp['objective']
            row['Obj_EnerGIS'] = obj['energis']
            row['Obj_oemof'] = obj['oemof']
            row['Obj_Diff_%'] = obj['relative_difference_pct']
            row['Parity'] = 'PASS' if obj['parity_check'] else 'FAIL'

        # Runtime
        if 'runtime' in comp:
            rt = comp['runtime']
            row['Time_EnerGIS_s'] = rt['energis_s']
            row['Time_oemof_s'] = rt['oemof_s']
            row['Speedup'] = rt['speedup_factor']

        # Model size
        if 'model_size' in comp:
            ms = comp['model_size']
            row['Vars_EnerGIS'] = ms['energis']['n_variables']
            row['Vars_oemof'] = ms['oemof']['n_variables']
            row['Constrs_EnerGIS'] = ms['energis']['n_constraints']
            row['Constrs_oemof'] = ms['oemof']['n_constraints']

        rows.append(row)

    df = pd.DataFrame(rows)

    # Save as CSV
    df.to_csv(output_file, index=False, float_format='%.2f')
    print(f"\n✓ Comparison table saved to: {output_file}")

    # Also save as formatted LaTeX table
    latex_file = output_file.with_suffix('.tex')
    with open(latex_file, 'w') as f:
        f.write(df.to_latex(index=False, float_format='%.2f', escape=False))
    print(f"✓ LaTeX table saved to: {latex_file}")

    return df


def create_comparison_plots(comparisons: list, output_dir: Path):
    """Create comparison plots for the paper."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract data
    scenarios = [c['scenario'] for c in comparisons]
    runtimes_energis = [c['runtime']['energis_s'] for c in comparisons if 'runtime' in c]
    runtimes_oemof = [c['runtime']['oemof_s'] for c in comparisons if 'runtime' in c]

    # Plot 1: Runtime comparison
    fig, ax = plt.subplots(figsize=(8, 5))

    x = np.arange(len(scenarios))
    width = 0.35

    ax.bar(x - width/2, runtimes_energis, width, label='EnerGIS', alpha=0.8)
    ax.bar(x + width/2, runtimes_oemof, width, label='oemof', alpha=0.8)

    ax.set_xlabel('Scenario (hours)')
    ax.set_ylabel('Runtime (seconds)')
    ax.set_title('Computational Performance Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels([f'{s}h' for s in scenarios])
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_dir / 'runtime_comparison.pdf', dpi=300)
    plt.savefig(output_dir / 'runtime_comparison.png', dpi=300)
    print(f"✓ Runtime plot saved to: {output_dir / 'runtime_comparison.pdf'}")

    plt.close()

    # Plot 2: Speedup factor vs. problem size
    fig, ax = plt.subplots(figsize=(8, 5))

    speedups = [c['runtime']['speedup_factor'] for c in comparisons if 'runtime' in c]

    ax.plot(scenarios, speedups, 'o-', linewidth=2, markersize=8)
    ax.axhline(y=1.0, color='r', linestyle='--', label='Equal performance')

    ax.set_xlabel('Problem Size (hours)')
    ax.set_ylabel('Speedup Factor (oemof time / EnerGIS time)')
    ax.set_title('Performance Scaling')
    ax.set_xscale('log')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'speedup_scaling.pdf', dpi=300)
    plt.savefig(output_dir / 'speedup_scaling.png', dpi=300)
    print(f"✓ Speedup plot saved to: {output_dir / 'speedup_scaling.pdf'}")

    plt.close()


# ============================================================
# PLACEHOLDER: ENERGIS IMPLEMENTATION
# ============================================================

def run_energis_benchmark_placeholder(hours=168, solver='cbc', output_dir=None):
    """
    Placeholder for EnerGIS benchmark.

    TODO: Replace with actual EnerGIS implementation
    """
    print(f"\n{'#'*70}")
    print(f"# EnerGIS Benchmark (PLACEHOLDER)")
    print(f"{'#'*70}")
    print(f"  Horizon: {hours} hours")
    print(f"  Solver: {solver}")
    print(f"\n⚠️  WARNING: Using placeholder implementation")
    print(f"   Real EnerGIS integration pending")

    # Return dummy results for testing
    return {
        'framework': 'energis',
        'hours': hours,
        'solver': solver,
        'build_time_s': 5.0,
        'solve_time_s': 10.0,
        'total_time_s': 15.0,
        'objective_value': 2500000.0,  # Placeholder
        'n_variables': 10000,
        'n_constraints': 8000,
        'capacities': {
            'hp_hp1': 15.0,
            'hp_hp2': 10.0,
            'hp_hp3': 5.0,
            'chp_hkw': 20.0,
            'boiler_gtost': 10.0,
            'storage_tes': 80.0,
        },
        'termination_condition': 'optimal',
        'note': 'PLACEHOLDER DATA - Replace with real EnerGIS run'
    }


# ============================================================
# MAIN EXECUTION
# ============================================================

def run_single_comparison(scenario_name: str, solver: str = 'cbc') -> Dict[str, Any]:
    """Run comparison for a single scenario."""
    scenario = SCENARIOS[scenario_name]
    hours = scenario['hours']

    print(f"\n{'#'*70}")
    print(f"# BENCHMARK COMPARISON: {scenario_name.upper()}")
    print(f"# {scenario['description']}")
    print(f"{'#'*70}")

    # Run oemof benchmark
    print(f"\n[1/2] Running oemof-solph...")
    oemof_results = run_oemof_benchmark(
        hours=hours,
        solver=solver,
        output_dir=RESULTS_DIR / 'oemof'
    )

    # Run EnerGIS benchmark
    print(f"\n[2/2] Running EnerGIS...")
    energis_results = run_energis_benchmark_placeholder(
        hours=hours,
        solver=solver,
        output_dir=RESULTS_DIR / 'energis'
    )

    # Compare results
    print(f"\n[3/3] Comparing results...")
    comparison = compare_results(energis_results, oemof_results, tolerance=0.01)

    # Print summary
    print_comparison_summary(comparison)

    # Save comparison
    comparison_file = RESULTS_DIR / f'comparison_{scenario_name}.json'
    with open(comparison_file, 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    print(f"\n✓ Comparison saved to: {comparison_file}")

    return comparison


def run_all_comparisons(scenarios=None, solver='cbc'):
    """Run comparisons for all specified scenarios."""
    if scenarios is None:
        scenarios = list(SCENARIOS.keys())

    comparisons = []

    for scenario_name in scenarios:
        try:
            comparison = run_single_comparison(scenario_name, solver=solver)
            comparisons.append(comparison)
        except Exception as e:
            print(f"\n✗ Failed to run scenario {scenario_name}: {e}")
            import traceback
            traceback.print_exc()

    # Export summary table
    if comparisons:
        table_file = RESULTS_DIR / 'comparison_summary.csv'
        df = export_comparison_table(comparisons, table_file)

        # Create plots
        create_comparison_plots(comparisons, RESULTS_DIR / 'plots')

        print(f"\n{'='*70}")
        print(f"ALL COMPARISONS COMPLETE")
        print(f"{'='*70}")
        print(f"\nResults saved to: {RESULTS_DIR}")
        print(f"  - Individual JSON files: comparison_*.json")
        print(f"  - Summary table: comparison_summary.csv")
        print(f"  - Plots: plots/*.pdf")

    return comparisons


def main():
    parser = argparse.ArgumentParser(
        description='Run EnerGIS vs. oemof benchmark comparison'
    )
    parser.add_argument(
        '--scenario',
        type=str,
        choices=list(SCENARIOS.keys()),
        help='Run specific scenario'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all scenarios'
    )
    parser.add_argument(
        '--parity',
        action='store_true',
        help='Run parity check only (tiny scenario)'
    )
    parser.add_argument(
        '--solver',
        type=str,
        default='cbc',
        choices=['gurobi', 'cbc', 'glpk'],
        help='Solver to use'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=str(RESULTS_DIR),
        help='Output directory'
    )

    args = parser.parse_args()

    # Set output directory
    global RESULTS_DIR
    RESULTS_DIR = Path(args.output)

    if args.parity:
        # Run parity check
        print("\n" + "="*70)
        print("PARITY CHECK (24h tiny scenario)")
        print("="*70)
        comparison = run_single_comparison('tiny', solver=args.solver)

        if 'objective' in comparison and comparison['objective'].get('parity_check'):
            print("\n✓✓✓ PARITY CHECK PASSED ✓✓✓")
            print(f"   Relative difference: {comparison['objective']['relative_difference_pct']:.4f}% (< 1% tolerance)")
        else:
            print("\n✗✗✗ PARITY CHECK FAILED ✗✗✗")
            if 'objective' in comparison:
                print(f"   Relative difference: {comparison['objective']['relative_difference_pct']:.4f}% (> 1% tolerance)")

    elif args.all:
        # Run all scenarios
        comparisons = run_all_comparisons(solver=args.solver)

    elif args.scenario:
        # Run specific scenario
        comparison = run_single_comparison(args.scenario, solver=args.solver)

    else:
        print("Please specify --scenario, --all, or --parity")
        parser.print_help()


if __name__ == '__main__':
    main()
