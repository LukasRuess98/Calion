"""Visualization utilities for benchmark results.

This module provides plotting functions for benchmark comparisons.
Requires matplotlib, which is optional for the framework.
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Check for matplotlib
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    HAVE_MATPLOTLIB = True
except ImportError:
    HAVE_MATPLOTLIB = False
    plt = None


def plot_cost_comparison(
    results: List,
    output_path: str,
    title: str = "Method Cost Comparison",
    show_breakdown: bool = True,
):
    """Plot cost comparison across methods.

    Parameters
    ----------
    results:
        List of BenchmarkMetrics
    output_path:
        Output file path (e.g., "comparison.png")
    title:
        Plot title
    show_breakdown:
        If True, show CAPEX/OPEX breakdown
    """
    if not HAVE_MATPLOTLIB:
        logger.warning("matplotlib not available, skipping plot")
        return

    from collections import defaultdict

    # Group by method
    methods = defaultdict(list)
    for r in results:
        methods[r.method].append(r)

    # Calculate averages
    method_names = sorted(methods.keys())
    avg_total = []
    avg_capex = []
    avg_opex = []

    for name in method_names:
        runs = methods[name]
        avg_total.append(sum(r.total_cost_eur for r in runs) / len(runs))
        avg_capex.append(sum(r.capex_eur for r in runs) / len(runs))
        avg_opex.append(sum(r.opex_eur for r in runs) / len(runs))

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    if show_breakdown:
        # Stacked bar chart
        x = range(len(method_names))
        ax.bar(x, avg_capex, label='CAPEX', color='steelblue')
        ax.bar(x, avg_opex, bottom=avg_capex, label='OPEX', color='lightcoral')

        # Add total on top
        for i, total in enumerate(avg_total):
            ax.text(i, total + max(avg_total) * 0.02, f'{total/1000:.1f}k',
                   ha='center', va='bottom', fontweight='bold')
    else:
        # Simple bar chart
        ax.bar(method_names, avg_total, color='steelblue')
        for i, total in enumerate(avg_total):
            ax.text(i, total + max(avg_total) * 0.02, f'{total/1000:.1f}k',
                   ha='center', va='bottom', fontweight='bold')

    ax.set_xticks(range(len(method_names)))
    ax.set_xticklabels(method_names, rotation=45, ha='right')
    ax.set_ylabel('Cost (EUR)')
    ax.set_title(title)
    if show_breakdown:
        ax.legend()
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved cost comparison plot to {output_path}")


def plot_cost_vs_pf(
    results: List,
    output_path: str,
    title: str = "Cost vs Perfect Forecast",
):
    """Plot cost deviation from PF baseline.

    Parameters
    ----------
    results:
        List of BenchmarkMetrics
    output_path:
        Output file path
    title:
        Plot title
    """
    if not HAVE_MATPLOTLIB:
        logger.warning("matplotlib not available, skipping plot")
        return

    from collections import defaultdict

    # Group by method
    methods = defaultdict(list)
    for r in results:
        if r.cost_vs_pf_percent is not None:
            methods[r.method].append(r.cost_vs_pf_percent)

    if not methods:
        logger.warning("No cost_vs_pf data available")
        return

    # Calculate averages
    method_names = sorted(methods.keys())
    avg_deviation = [sum(methods[name]) / len(methods[name]) for name in method_names]

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ['green' if d < 5 else 'orange' if d < 10 else 'red' for d in avg_deviation]
    ax.bar(method_names, avg_deviation, color=colors, alpha=0.7)

    # Add percentage labels
    for i, (name, dev) in enumerate(zip(method_names, avg_deviation)):
        ax.text(i, dev + max(avg_deviation) * 0.02, f'+{dev:.1f}%',
               ha='center', va='bottom', fontweight='bold')

    ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_xticks(range(len(method_names)))
    ax.set_xticklabels(method_names, rotation=45, ha='right')
    ax.set_ylabel('Cost vs PF (%)')
    ax.set_title(title)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved cost vs PF plot to {output_path}")


def plot_solve_time_comparison(
    results: List,
    output_path: str,
    title: str = "Solve Time Comparison",
):
    """Plot solve time comparison.

    Parameters
    ----------
    results:
        List of BenchmarkMetrics
    output_path:
        Output file path
    title:
        Plot title
    """
    if not HAVE_MATPLOTLIB:
        logger.warning("matplotlib not available, skipping plot")
        return

    from collections import defaultdict

    # Group by method
    methods = defaultdict(list)
    for r in results:
        methods[r.method].append(r.solve_time_seconds)

    # Calculate averages
    method_names = sorted(methods.keys())
    avg_times = [sum(methods[name]) / len(methods[name]) for name in method_names]

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.bar(method_names, avg_times, color='steelblue', alpha=0.7)

    # Add time labels
    for i, (name, time) in enumerate(zip(method_names, avg_times)):
        if time < 60:
            label = f'{time:.1f}s'
        else:
            label = f'{time/60:.1f}min'
        ax.text(i, time + max(avg_times) * 0.02, label,
               ha='center', va='bottom', fontweight='bold')

    ax.set_xticks(range(len(method_names)))
    ax.set_xticklabels(method_names, rotation=45, ha='right')
    ax.set_ylabel('Solve Time (seconds)')
    ax.set_title(title)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved solve time plot to {output_path}")


def create_benchmark_plots(results: List, output_dir: str = "exports/benchmark/plots"):
    """Create all standard benchmark plots.

    Parameters
    ----------
    results:
        List of BenchmarkMetrics
    output_dir:
        Output directory for plots
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    if not HAVE_MATPLOTLIB:
        logger.warning("matplotlib not available, skipping all plots")
        logger.info("Install matplotlib to generate plots: pip install matplotlib")
        return

    logger.info(f"Creating benchmark plots in {output_dir}")

    # Cost comparison
    plot_cost_comparison(
        results,
        os.path.join(output_dir, "cost_comparison.png"),
        show_breakdown=True,
    )

    # Cost vs PF
    plot_cost_vs_pf(
        results,
        os.path.join(output_dir, "cost_vs_pf.png"),
    )

    # Solve time
    plot_solve_time_comparison(
        results,
        os.path.join(output_dir, "solve_time.png"),
    )

    logger.info(f"✅ All plots created in {output_dir}")


def print_latex_table(results: List, output_path: Optional[str] = None):
    """Generate LaTeX table for publication.

    Parameters
    ----------
    results:
        List of BenchmarkMetrics
    output_path:
        Optional output file path
    """
    from collections import defaultdict

    # Group by method
    methods = defaultdict(list)
    for r in results:
        methods[r.method].append(r)

    # Build LaTeX table
    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(r"\caption{Forecast Methods Comparison}")
    lines.append(r"\label{tab:forecast_comparison}")
    lines.append(r"\begin{tabular}{lrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Method & Total Cost & vs PF & CAPEX & OPEX & Time (s) \\")
    lines.append(r"\midrule")

    for method_name in sorted(methods.keys()):
        runs = methods[method_name]
        n = len(runs)

        avg_cost = sum(r.total_cost_eur for r in runs) / n
        avg_capex = sum(r.capex_eur for r in runs) / n
        avg_opex = sum(r.opex_eur for r in runs) / n
        avg_time = sum(r.solve_time_seconds for r in runs) / n

        vs_pf = runs[0].cost_vs_pf_percent
        vs_pf_str = f"+{vs_pf:.1f}\\%" if vs_pf is not None else "---"

        lines.append(
            f"{method_name} & "
            f"{avg_cost:,.0f} & "
            f"{vs_pf_str} & "
            f"{avg_capex:,.0f} & "
            f"{avg_opex:,.0f} & "
            f"{avg_time:.1f} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    latex_code = "\n".join(lines)

    if output_path:
        with open(output_path, 'w') as f:
            f.write(latex_code)
        logger.info(f"Saved LaTeX table to {output_path}")
    else:
        print("\n" + latex_code + "\n")

    return latex_code
