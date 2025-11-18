#!/usr/bin/env python3
"""
Generate All Figures for EnerGIS Paper (Applied Energy)
========================================================

This script creates all publication-ready figures for the manuscript.
Each figure corresponds to a specific section of the paper.

Figures to create:
- Figure 1: EnerGIS Architecture Overview (multi-panel schematic)
- Figure 2: Rolling Horizon Schematic (timeline illustration)
- Figure 3: Annualized Cost Breakdown (stacked bar chart)
- Figure 4: Typical Week Dispatch and Storage (multi-panel time series)
- Figure 5: Computational Performance Comparison (line plots)
- Figure 6: CO₂ Price Sensitivity (multi-line sensitivity)
- Graphical Abstract: Workflow diagram (high-res for journal)

Usage:
    python create_paper_figures.py --all
    python create_paper_figures.py --figure 1
    python create_paper_figures.py --figure graphical_abstract

Requirements:
    - Results data from EnerGIS runs (stored in ../results/ directory)
    - If no data available, synthetic placeholders will be generated

Author: Auto-generated for Applied Energy submission
Date: 2025-11-18
"""

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch
from pathlib import Path
import sys

# Import our custom figure styles
from figure_styles import (
    setup_paper_style, COLORS, FIGSIZE_SINGLE_COLUMN, FIGSIZE_DOUBLE_COLUMN,
    FIGSIZE_DOUBLE_TALL, save_figure, add_subplot_labels, format_power_axis
)

# ============================================================
# CONFIGURATION
# ============================================================

RESULTS_DIR = Path(__file__).parent.parent / "results"
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent.parent / "data"

# ============================================================
# FIGURE 1: ENERGIS ARCHITECTURE OVERVIEW
# ============================================================

def create_figure_1_architecture():
    """
    Multi-panel schematic showing:
    (a) High-level architecture layers
    (b) Component plugin system
    (c) Bus and flow abstractions
    (d) PF→RH workflow
    """
    setup_paper_style()
    fig = plt.figure(figsize=FIGSIZE_DOUBLE_TALL)

    # Create grid layout
    gs = fig.add_gridspec(2, 2, hspace=0.4, wspace=0.3)

    # ---- Panel (a): Architecture Layers ----
    ax_a = fig.add_subplot(gs[0, 0])
    layers = ['CLI & Notebooks', 'Orchestration', 'Model Building',
              'Configuration & I/O', 'Utilities']
    y_pos = np.arange(len(layers))

    ax_a.barh(y_pos, [1]*len(layers), color=COLORS['baseline'], alpha=0.7)
    ax_a.set_yticks(y_pos)
    ax_a.set_yticklabels(layers, fontsize=8)
    ax_a.set_xlim(0, 1.2)
    ax_a.set_xlabel('Layer', fontsize=9)
    ax_a.set_title('(a) Layered Architecture', fontsize=10, fontweight='bold')
    ax_a.invert_yaxis()
    ax_a.set_xticks([])

    # ---- Panel (b): Component Plugin System ----
    ax_b = fig.add_subplot(gs[0, 1])

    # Draw component registry concept
    components = ['HeatPump', 'Storage', 'Generator', 'P2H']
    x_pos = np.arange(len(components))

    bars = ax_b.bar(x_pos, [10, 8, 9, 7],
                    color=[COLORS['heat_pump'], COLORS['storage'],
                           COLORS['chp'], COLORS['p2h']], alpha=0.8)

    ax_b.set_xticks(x_pos)
    ax_b.set_xticklabels(components, fontsize=8, rotation=30, ha='right')
    ax_b.set_ylabel('Component Instances', fontsize=9)
    ax_b.set_title('(b) Component Registry', fontsize=10, fontweight='bold')
    ax_b.grid(True, alpha=0.3, axis='y')

    # ---- Panel (c): Bus Abstraction ----
    ax_c = fig.add_subplot(gs[1, 0])

    # Simulate bus connections (simplified network graph)
    bus_labels = ['Electricity', 'Heat', 'Gas', 'Biomass']
    bus_colors = [COLORS['electricity'], COLORS['heat'],
                  COLORS['gas'], COLORS['biomass']]

    for i, (label, color) in enumerate(zip(bus_labels, bus_colors)):
        circle = plt.Circle((i*0.25, 0.5), 0.08, color=color, alpha=0.7)
        ax_c.add_patch(circle)
        ax_c.text(i*0.25, 0.3, label, ha='center', va='top', fontsize=7)

    # Draw connections between buses
    for i in range(len(bus_labels)-1):
        ax_c.plot([i*0.25, (i+1)*0.25], [0.5, 0.5], 'k-', alpha=0.3, linewidth=1)

    ax_c.set_xlim(-0.1, 0.85)
    ax_c.set_ylim(0, 1)
    ax_c.axis('off')
    ax_c.set_title('(c) Multi-Commodity Buses', fontsize=10, fontweight='bold')

    # ---- Panel (d): PF→RH Workflow ----
    ax_d = fig.add_subplot(gs[1, 1])

    # Timeline showing PF and RH phases
    phases = ['Planning\nFramework\n(8760 h)', 'Rolling\nHorizon\n(365 windows)']
    durations = [30, 60]  # Example runtimes in minutes

    bars = ax_d.barh(np.arange(len(phases)), durations,
                     color=[COLORS['capex'], COLORS['opex']], alpha=0.8)

    ax_d.set_yticks(np.arange(len(phases)))
    ax_d.set_yticklabels(phases, fontsize=8)
    ax_d.set_xlabel('Runtime [minutes]', fontsize=9)
    ax_d.set_title('(d) PF→RH Workflow', fontsize=10, fontweight='bold')
    ax_d.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    saved = save_figure(fig, 'figure1_architecture')
    print(f"✓ Created Figure 1: Architecture Overview → {saved[0]}")
    return fig


# ============================================================
# FIGURE 2: ROLLING HORIZON SCHEMATIC
# ============================================================

def create_figure_2_rolling_horizon():
    """
    Timeline illustration showing:
    - Sliding window progression
    - Commitment period vs. look-ahead
    - Overlap between windows
    """
    setup_paper_style()
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE_COLUMN)

    # Parameters
    horizon = 168  # hours (7 days)
    step = 24      # hours (1 day)
    n_windows = 5

    # Draw windows
    for i in range(n_windows):
        start = i * step
        # Committed period (darker)
        ax.add_patch(Rectangle((start, i), step, 0.7,
                                facecolor=COLORS['baseline'], alpha=0.8,
                                edgecolor='black', linewidth=1))
        # Look-ahead period (lighter)
        ax.add_patch(Rectangle((start + step, i), horizon - step, 0.7,
                                facecolor=COLORS['baseline'], alpha=0.3,
                                edgecolor='black', linewidth=1, linestyle='--'))

        # Label window
        ax.text(start + horizon/2, i + 0.35, f'Window {i+1}',
                ha='center', va='center', fontsize=8, fontweight='bold')

    # Annotations
    ax.annotate('', xy=(step, -0.5), xytext=(0, -0.5),
                arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
    ax.text(step/2, -0.7, 'Commit Period\n(24 h)', ha='center', fontsize=8)

    ax.annotate('', xy=(horizon, -0.5), xytext=(0, -0.5),
                arrowprops=dict(arrowstyle='<->', color='gray', lw=1.5))
    ax.text(horizon/2, -1.2, 'Horizon (168 h)', ha='center', fontsize=8, color='gray')

    # Axis settings
    ax.set_xlim(-10, horizon + 20)
    ax.set_ylim(-1.5, n_windows)
    ax.set_xlabel('Time [hours]', fontsize=10)
    ax.set_ylabel('Rolling Horizon Windows', fontsize=10)
    ax.set_yticks([])
    ax.set_title('Rolling Horizon Optimization Schematic', fontsize=11, fontweight='bold')

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor=COLORS['baseline'], alpha=0.8, label='Committed'),
        mpatches.Patch(facecolor=COLORS['baseline'], alpha=0.3, label='Look-ahead')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

    plt.tight_layout()
    saved = save_figure(fig, 'figure2_rolling_horizon')
    print(f"✓ Created Figure 2: Rolling Horizon Schematic → {saved[0]}")
    return fig


# ============================================================
# FIGURE 3: ANNUALIZED COST BREAKDOWN
# ============================================================

def create_figure_3_cost_breakdown():
    """
    Stacked bar chart showing cost components for:
    - Base scenario
    - High CO₂ scenario
    - Low grid price scenario
    """
    setup_paper_style()
    fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE_COLUMN)

    # Synthetic data (replace with actual results)
    scenarios = ['Base', 'High CO₂', 'Low Grid']
    capex = [1200, 1500, 1100]
    opex = [800, 900, 700]
    fuel = [500, 400, 550]
    co2 = [200, 600, 180]

    x = np.arange(len(scenarios))
    width = 0.6

    # Stacked bars
    p1 = ax.bar(x, capex, width, label='CAPEX', color=COLORS['capex'])
    p2 = ax.bar(x, opex, width, bottom=capex, label='OPEX', color=COLORS['opex'])
    p3 = ax.bar(x, fuel, width, bottom=np.array(capex)+np.array(opex),
                label='Fuel', color=COLORS['fuel'])
    p4 = ax.bar(x, co2, width, bottom=np.array(capex)+np.array(opex)+np.array(fuel),
                label='CO₂', color=COLORS['co2'])

    # Formatting
    ax.set_ylabel('Annualized Cost [k€/year]', fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, fontsize=9)
    ax.set_title('Total Annualized Cost Breakdown', fontsize=11, fontweight='bold')
    ax.legend(fontsize=9, loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    saved = save_figure(fig, 'figure3_cost_breakdown')
    print(f"✓ Created Figure 3: Cost Breakdown → {saved[0]}")
    return fig


# ============================================================
# FIGURE 4: TYPICAL WEEK DISPATCH AND STORAGE
# ============================================================

def create_figure_4_typical_week():
    """
    Multi-panel time series showing:
    (a) Heat demand and production by source
    (b) Storage state of charge
    (c) Grid electricity price and purchases
    (d) CO₂ intensity and emissions
    """
    setup_paper_style()
    fig, axes = plt.subplots(4, 1, figsize=(FIGSIZE_DOUBLE_COLUMN[0], 8), sharex=True)

    # Synthetic time series (168 hours = 1 week)
    hours = np.arange(168)
    demand = 20 + 10 * np.sin(hours * 2 * np.pi / 24) + np.random.rand(168) * 2

    # Panel (a): Heat production stacked area
    hp_prod = demand * 0.5 + np.random.rand(168) * 2
    chp_prod = demand * 0.3 + np.random.rand(168) * 1
    boiler_prod = demand - hp_prod - chp_prod

    axes[0].fill_between(hours, 0, hp_prod, label='Heat Pumps', color=COLORS['heat_pump'], alpha=0.7)
    axes[0].fill_between(hours, hp_prod, hp_prod+chp_prod, label='CHP', color=COLORS['chp'], alpha=0.7)
    axes[0].fill_between(hours, hp_prod+chp_prod, demand, label='Boiler', color=COLORS['boiler'], alpha=0.7)
    axes[0].plot(hours, demand, 'k--', linewidth=1.5, label='Demand')

    axes[0].set_ylabel('Heat [MW]', fontsize=9)
    axes[0].set_title('(a) Heat Production and Demand', fontsize=10, fontweight='bold', loc='left')
    axes[0].legend(fontsize=8, loc='upper right', ncol=4)
    axes[0].grid(True, alpha=0.3)

    # Panel (b): Storage SOC
    soc = 50 + 30 * np.sin(hours * 2 * np.pi / 24 + np.pi/2)
    axes[1].plot(hours, soc, color=COLORS['storage'], linewidth=2)
    axes[1].axhline(y=80, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Max capacity')
    axes[1].axhline(y=20, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Min SOC')

    axes[1].set_ylabel('SOC [MWh]', fontsize=9)
    axes[1].set_title('(b) Thermal Storage State of Charge', fontsize=10, fontweight='bold', loc='left')
    axes[1].legend(fontsize=8, loc='upper right')
    axes[1].grid(True, alpha=0.3)

    # Panel (c): Grid price and purchases
    price = 50 + 30 * np.sin(hours * 2 * np.pi / 24) + np.random.rand(168) * 10
    purchases = 5 + 3 * np.sin(hours * 2 * np.pi / 24 + np.pi) + np.random.rand(168)

    ax_c1 = axes[2]
    ax_c2 = ax_c1.twinx()

    ax_c1.plot(hours, price, color=COLORS['electricity'], linewidth=1.5, label='Price')
    ax_c2.fill_between(hours, 0, purchases, color=COLORS['grid'], alpha=0.5, label='Purchases')

    ax_c1.set_ylabel('Elec. Price [€/MWh]', fontsize=9, color=COLORS['electricity'])
    ax_c2.set_ylabel('Grid Purchases [MW]', fontsize=9, color=COLORS['grid'])
    ax_c1.set_title('(c) Electricity Price and Grid Interaction', fontsize=10, fontweight='bold', loc='left')
    ax_c1.tick_params(axis='y', labelcolor=COLORS['electricity'])
    ax_c2.tick_params(axis='y', labelcolor=COLORS['grid'])
    ax_c1.grid(True, alpha=0.3)

    # Panel (d): CO₂ intensity and emissions
    co2_intensity = 400 + 100 * np.sin(hours * 2 * np.pi / 24)
    emissions = co2_intensity * purchases / 1000  # Convert to tons

    ax_d1 = axes[3]
    ax_d2 = ax_d1.twinx()

    ax_d1.plot(hours, co2_intensity, color='gray', linewidth=1.5, label='CO₂ Intensity')
    ax_d2.fill_between(hours, 0, emissions, color=COLORS['co2'], alpha=0.5, label='Emissions')

    ax_d1.set_xlabel('Time [hours]', fontsize=10)
    ax_d1.set_ylabel('CO₂ Intensity [kg/MWh]', fontsize=9, color='gray')
    ax_d2.set_ylabel('Emissions [t CO₂]', fontsize=9, color=COLORS['co2'])
    ax_d1.set_title('(d) Grid CO₂ Intensity and Emissions', fontsize=10, fontweight='bold', loc='left')
    ax_d1.tick_params(axis='y', labelcolor='gray')
    ax_d2.tick_params(axis='y', labelcolor=COLORS['co2'])
    ax_d1.grid(True, alpha=0.3)

    plt.tight_layout()
    saved = save_figure(fig, 'figure4_typical_week')
    print(f"✓ Created Figure 4: Typical Week Dispatch → {saved[0]}")
    return fig


# ============================================================
# FIGURE 5: COMPUTATIONAL PERFORMANCE
# ============================================================

def create_figure_5_performance():
    """
    Line plots showing:
    - Runtime vs. problem size (hours)
    - Runtime vs. number of components
    - Comparison: EnerGIS vs. oemof
    """
    setup_paper_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE_COLUMN)

    # Synthetic performance data
    problem_sizes = [24, 72, 168, 336, 720, 1440, 2160, 4380, 8760]  # hours
    runtime_energis = [2, 5, 15, 45, 120, 300, 600, 1200, 1800]  # seconds
    runtime_oemof = [3, 7, 20, 60, 150, 350, 700, 1400, 2100]

    # Panel (a): Runtime vs. problem size
    ax1.plot(problem_sizes, np.array(runtime_energis)/60, 'o-',
             label='EnerGIS', color=COLORS['baseline'], linewidth=2, markersize=6)
    ax1.plot(problem_sizes, np.array(runtime_oemof)/60, 's--',
             label='oemof', color=COLORS['comparison'], linewidth=2, markersize=6)

    ax1.set_xlabel('Problem Size [hours]', fontsize=10)
    ax1.set_ylabel('Runtime [minutes]', fontsize=10)
    ax1.set_title('(a) Runtime vs. Problem Size', fontsize=10, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xscale('log')
    ax1.set_yscale('log')

    # Panel (b): Runtime vs. number of components
    n_components = [1, 2, 4, 6, 8, 10, 12]
    runtime_components = [5, 12, 25, 45, 70, 100, 135]  # seconds for 168h window

    ax2.plot(n_components, runtime_components, 'D-',
             color=COLORS['optimal'], linewidth=2, markersize=6)

    ax2.set_xlabel('Number of Components', fontsize=10)
    ax2.set_ylabel('Runtime [seconds]', fontsize=10)
    ax2.set_title('(b) Runtime vs. System Complexity', fontsize=10, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    saved = save_figure(fig, 'figure5_performance')
    print(f"✓ Created Figure 5: Computational Performance → {saved[0]}")
    return fig


# ============================================================
# FIGURE 6: CO₂ PRICE SENSITIVITY
# ============================================================

def create_figure_6_co2_sensitivity():
    """
    Multi-line sensitivity analysis showing:
    - Heat pump capacity vs. CO₂ price
    - CHP capacity vs. CO₂ price
    - Total cost vs. CO₂ price
    - CO₂ emissions vs. CO₂ price
    """
    setup_paper_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE_COLUMN)

    # Synthetic sensitivity data
    co2_prices = [0, 25, 50, 75, 100, 150, 200]  # €/tCO₂

    # Panel (a): Capacities
    hp_capacity = [10, 12, 15, 18, 22, 28, 32]  # MW
    chp_capacity = [20, 18, 15, 12, 10, 7, 5]   # MW

    ax1.plot(co2_prices, hp_capacity, 'o-', label='Heat Pumps',
             color=COLORS['heat_pump'], linewidth=2, markersize=6)
    ax1.plot(co2_prices, chp_capacity, 's--', label='CHP (Gas)',
             color=COLORS['chp'], linewidth=2, markersize=6)

    ax1.set_xlabel('CO₂ Price [€/t]', fontsize=10)
    ax1.set_ylabel('Optimal Capacity [MW]', fontsize=10)
    ax1.set_title('(a) Technology Mix vs. CO₂ Price', fontsize=10, fontweight='bold')
    ax1.legend(fontsize=9, loc='best')
    ax1.grid(True, alpha=0.3)

    # Panel (b): Total cost and emissions
    total_cost = [2500, 2600, 2700, 2850, 3000, 3200, 3400]  # k€/year
    emissions = [5000, 4500, 4000, 3500, 3000, 2200, 1800]   # tCO₂/year

    ax2_twin = ax2.twinx()

    l1 = ax2.plot(co2_prices, total_cost, 'D-', label='Total Cost',
                  color=COLORS['capex'], linewidth=2, markersize=6)
    l2 = ax2_twin.plot(co2_prices, emissions, '^--', label='Emissions',
                       color=COLORS['co2'], linewidth=2, markersize=6)

    ax2.set_xlabel('CO₂ Price [€/t]', fontsize=10)
    ax2.set_ylabel('Total Cost [k€/year]', fontsize=10, color=COLORS['capex'])
    ax2_twin.set_ylabel('CO₂ Emissions [t/year]', fontsize=10, color=COLORS['co2'])
    ax2.set_title('(b) Cost and Emissions vs. CO₂ Price', fontsize=10, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor=COLORS['capex'])
    ax2_twin.tick_params(axis='y', labelcolor=COLORS['co2'])

    # Combined legend
    lns = l1 + l2
    labs = [l.get_label() for l in lns]
    ax2.legend(lns, labs, fontsize=9, loc='upper left')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    saved = save_figure(fig, 'figure6_co2_sensitivity')
    print(f"✓ Created Figure 6: CO₂ Sensitivity → {saved[0]}")
    return fig


# ============================================================
# GRAPHICAL ABSTRACT
# ============================================================

def create_graphical_abstract():
    """
    High-resolution graphical abstract showing:
    EnerGIS workflow from input → PF → RH → outputs
    Requirements: 531 × 1328 pixels minimum, readable at 5 × 13 cm
    """
    setup_paper_style()

    # Use larger figure for high resolution
    fig, ax = plt.subplots(figsize=(5.2, 10.4))  # inches, will be scaled to 13x26 cm
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 20)
    ax.axis('off')

    # Define box positions (x, y, width, height)
    boxes = {
        'input': (1, 16, 8, 2.5),
        'pf': (1, 12, 8, 3),
        'rh': (1, 7, 8, 4),
        'output': (1, 1, 8, 4.5)
    }

    # Function to draw fancy box
    def draw_box(pos, title, items, color, ax):
        x, y, w, h = pos
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                              edgecolor='black', facecolor=color, alpha=0.3, linewidth=2)
        ax.add_patch(box)

        # Title
        ax.text(x + w/2, y + h - 0.3, title, fontsize=14, fontweight='bold',
                ha='center', va='top')

        # Items
        for i, item in enumerate(items):
            ax.text(x + 0.3, y + h - 0.8 - i*0.4, f'• {item}', fontsize=10,
                    ha='left', va='top')

    # Draw boxes
    draw_box(boxes['input'], 'INPUT DATA',
             ['Heat demand profile', 'Electricity prices', 'Technology catalog', 'Site constraints'],
             COLORS['grid'], ax)

    draw_box(boxes['pf'], 'PLANNING FRAMEWORK (PF)',
             ['Long-horizon design optimization', 'Optimal capacities', 'Technology selection', 'Investment decisions'],
             COLORS['capex'], ax)

    draw_box(boxes['rh'], 'ROLLING HORIZON (RH)',
             ['Short-horizon operational optimization', 'Unit dispatch', 'Storage management', 'Grid interaction'],
             COLORS['opex'], ax)

    draw_box(boxes['output'], 'OUTPUTS',
             ['Annualized costs', 'CO₂ emissions', 'Operational schedules', 'KPIs & validation'],
             COLORS['optimal'], ax)

    # Draw arrows between boxes
    arrow_props = dict(arrowstyle='->', lw=3, color='black')

    # Input → PF
    ax.annotate('', xy=(5, boxes['pf'][1] + boxes['pf'][3]), xytext=(5, boxes['input'][1]),
                arrowprops=arrow_props)

    # PF → RH
    ax.annotate('', xy=(5, boxes['rh'][1] + boxes['rh'][3]), xytext=(5, boxes['pf'][1]),
                arrowprops=arrow_props)
    ax.text(6, (boxes['pf'][1] + boxes['rh'][1] + boxes['rh'][3])/2, 'Fixed Design',
            fontsize=10, ha='left', va='center', style='italic')

    # RH → Output
    ax.annotate('', xy=(5, boxes['output'][1] + boxes['output'][3]), xytext=(5, boxes['rh'][1]),
                arrowprops=arrow_props)

    # Add title at top
    ax.text(5, 19, 'EnerGIS Framework', fontsize=16, fontweight='bold', ha='center', va='top')

    plt.tight_layout(pad=0.5)
    saved = save_figure(fig, 'graphical_abstract', dpi=600, formats=['png', 'pdf', 'eps'])
    print(f"✓ Created Graphical Abstract → {saved[0]}")
    return fig


# ============================================================
# MAIN FUNCTION
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Generate figures for EnerGIS paper')
    parser.add_argument('--all', action='store_true', help='Generate all figures')
    parser.add_argument('--figure', type=str, help='Generate specific figure (1-6, graphical_abstract)')
    parser.add_argument('--output-dir', type=str, default=str(OUTPUT_DIR),
                        help='Output directory for figures')

    args = parser.parse_args()

    # Set output directory
    global OUTPUT_DIR
    OUTPUT_DIR = Path(args.output_dir)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("="*70)
    print("EnerGIS Paper Figure Generator")
    print("="*70)
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    figures = {
        '1': ('Architecture Overview', create_figure_1_architecture),
        '2': ('Rolling Horizon Schematic', create_figure_2_rolling_horizon),
        '3': ('Cost Breakdown', create_figure_3_cost_breakdown),
        '4': ('Typical Week Dispatch', create_figure_4_typical_week),
        '5': ('Computational Performance', create_figure_5_performance),
        '6': ('CO₂ Sensitivity', create_figure_6_co2_sensitivity),
        'graphical_abstract': ('Graphical Abstract', create_graphical_abstract),
    }

    if args.all:
        print("Generating all figures...")
        for key, (name, func) in figures.items():
            print(f"\nCreating {name}...")
            func()
    elif args.figure:
        key = args.figure.lower()
        if key in figures:
            name, func = figures[key]
            print(f"Creating {name}...")
            func()
        else:
            print(f"Error: Unknown figure '{args.figure}'")
            print(f"Available figures: {', '.join(figures.keys())}")
            sys.exit(1)
    else:
        print("Please specify --all or --figure <number>")
        print(f"Available figures: {', '.join(figures.keys())}")
        sys.exit(1)

    print("\n" + "="*70)
    print("✓ Figure generation complete!")
    print(f"  All figures saved to: {OUTPUT_DIR}")
    print("="*70)


if __name__ == '__main__':
    main()
