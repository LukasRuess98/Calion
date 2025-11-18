#!/usr/bin/env python3
"""
Publication-Ready Figure Styles for Applied Energy Submission
==============================================================

This module provides consistent styling for all figures in the EnerGIS paper.
All figures follow Applied Energy journal requirements:
- High resolution (300 DPI minimum)
- Vector format (PDF/EPS) preferred
- Readable at journal column width (8.5 cm single column, 17.5 cm double column)
- Consistent fonts, colors, and layout

Usage:
    import matplotlib.pyplot as plt
    from figure_styles import setup_paper_style, COLORS, save_figure

    setup_paper_style()
    fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE_COLUMN)
    # ... create plot ...
    save_figure(fig, "figure1_architecture.pdf")
"""

import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path
import numpy as np

# ============================================================
# JOURNAL SPECIFICATIONS (Applied Energy)
# ============================================================

# Column widths in cm (converted to inches for matplotlib)
COLUMN_WIDTH_CM = 8.5  # Single column
FULL_WIDTH_CM = 17.5   # Double column (full page width)

CM_TO_INCH = 1 / 2.54

COLUMN_WIDTH_INCH = COLUMN_WIDTH_CM * CM_TO_INCH  # ≈ 3.35 inches
FULL_WIDTH_INCH = FULL_WIDTH_CM * CM_TO_INCH      # ≈ 6.89 inches

# Figure sizes (width, height) in inches
FIGSIZE_SINGLE_COLUMN = (COLUMN_WIDTH_INCH, COLUMN_WIDTH_INCH * 0.75)  # 3.35 x 2.51
FIGSIZE_SINGLE_TALL = (COLUMN_WIDTH_INCH, COLUMN_WIDTH_INCH * 1.2)     # 3.35 x 4.02
FIGSIZE_DOUBLE_COLUMN = (FULL_WIDTH_INCH, FULL_WIDTH_INCH * 0.6)       # 6.89 x 4.13
FIGSIZE_DOUBLE_TALL = (FULL_WIDTH_INCH, FULL_WIDTH_INCH * 0.8)         # 6.89 x 5.51

# Resolution
DPI = 300  # Minimum for publication
DPI_SCREEN = 100  # For on-screen preview

# ============================================================
# COLOR SCHEMES
# ============================================================

# Energy system component colors (colorblind-friendly palette)
COLORS = {
    # Components
    'heat_pump': '#1f77b4',      # Blue
    'storage': '#ff7f0e',        # Orange
    'chp': '#2ca02c',            # Green
    'boiler': '#d62728',         # Red
    'p2h': '#9467bd',            # Purple
    'waste_heat': '#8c564b',     # Brown
    'grid': '#e377c2',           # Pink
    'demand': '#7f7f7f',         # Gray

    # Energy carriers
    'electricity': '#1f77b4',
    'heat': '#d62728',
    'gas': '#ff7f0e',
    'biomass': '#2ca02c',

    # Cost categories
    'capex': '#17becf',          # Cyan
    'opex': '#bcbd22',           # Yellow-green
    'fuel': '#ff9896',           # Light red
    'co2': '#c5b0d5',            # Light purple

    # Results
    'baseline': '#1f77b4',
    'optimal': '#2ca02c',
    'comparison': '#ff7f0e',
}

# Sequential colormap for heatmaps
CMAP_SEQUENTIAL = 'YlOrRd'  # Yellow-Orange-Red

# Diverging colormap for differences
CMAP_DIVERGING = 'RdBu_r'  # Red-Blue reversed

# ============================================================
# FONT SETTINGS
# ============================================================

FONT_FAMILY = 'serif'  # Better for academic publications
FONT_SERIF = ['Times New Roman', 'DejaVu Serif', 'serif']

FONT_SIZES = {
    'title': 11,
    'label': 10,
    'tick': 9,
    'legend': 9,
    'annotation': 8,
}

# ============================================================
# LINE AND MARKER STYLES
# ============================================================

LINE_STYLES = ['-', '--', '-.', ':']
MARKERS = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
LINE_WIDTH = 1.5
MARKER_SIZE = 6

# ============================================================
# SETUP FUNCTION
# ============================================================

def setup_paper_style():
    """
    Apply publication-ready style to all matplotlib figures.
    Call this once at the beginning of your script.
    """
    # Set style
    plt.style.use('seaborn-v0_8-paper')  # Clean, minimal style

    # Font settings
    mpl.rcParams['font.family'] = FONT_FAMILY
    mpl.rcParams['font.serif'] = FONT_SERIF
    mpl.rcParams['font.size'] = FONT_SIZES['label']

    # Figure settings
    mpl.rcParams['figure.dpi'] = DPI_SCREEN
    mpl.rcParams['savefig.dpi'] = DPI
    mpl.rcParams['savefig.bbox'] = 'tight'
    mpl.rcParams['savefig.pad_inches'] = 0.05

    # Axes settings
    mpl.rcParams['axes.labelsize'] = FONT_SIZES['label']
    mpl.rcParams['axes.titlesize'] = FONT_SIZES['title']
    mpl.rcParams['axes.linewidth'] = 0.8
    mpl.rcParams['axes.grid'] = True
    mpl.rcParams['axes.grid.which'] = 'major'
    mpl.rcParams['axes.axisbelow'] = True  # Grid below plot elements

    # Tick settings
    mpl.rcParams['xtick.labelsize'] = FONT_SIZES['tick']
    mpl.rcParams['ytick.labelsize'] = FONT_SIZES['tick']
    mpl.rcParams['xtick.major.width'] = 0.8
    mpl.rcParams['ytick.major.width'] = 0.8

    # Legend settings
    mpl.rcParams['legend.fontsize'] = FONT_SIZES['legend']
    mpl.rcParams['legend.frameon'] = True
    mpl.rcParams['legend.framealpha'] = 0.9
    mpl.rcParams['legend.edgecolor'] = 'gray'

    # Line settings
    mpl.rcParams['lines.linewidth'] = LINE_WIDTH
    mpl.rcParams['lines.markersize'] = MARKER_SIZE

    # Grid settings
    mpl.rcParams['grid.alpha'] = 0.3
    mpl.rcParams['grid.linestyle'] = '--'
    mpl.rcParams['grid.linewidth'] = 0.5

    # Save settings
    mpl.rcParams['pdf.fonttype'] = 42  # TrueType fonts (editable in Adobe)
    mpl.rcParams['ps.fonttype'] = 42

    print("✓ Publication-ready matplotlib style applied")
    print(f"  - Single column width: {FIGSIZE_SINGLE_COLUMN}")
    print(f"  - Double column width: {FIGSIZE_DOUBLE_COLUMN}")
    print(f"  - DPI for saving: {DPI}")


def save_figure(fig, filename, dpi=None, formats=None, output_dir=None):
    """
    Save figure in publication-ready format(s).

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        Figure to save
    filename : str
        Base filename (without extension)
    dpi : int, optional
        Resolution (default: 300 DPI)
    formats : list of str, optional
        File formats (default: ['pdf', 'png'])
    output_dir : str or Path, optional
        Output directory (default: current paper/figures/)

    Returns
    -------
    saved_paths : list of Path
        Paths to saved files
    """
    if dpi is None:
        dpi = DPI

    if formats is None:
        formats = ['pdf', 'png']  # PDF for paper, PNG for preview

    if output_dir is None:
        output_dir = Path(__file__).parent
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Remove extension from filename if present
    base_name = Path(filename).stem

    saved_paths = []
    for fmt in formats:
        filepath = output_dir / f"{base_name}.{fmt}"
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight', pad_inches=0.05)
        saved_paths.append(filepath)
        print(f"✓ Saved: {filepath}")

    return saved_paths


# ============================================================
# HELPER FUNCTIONS FOR COMMON PLOT TYPES
# ============================================================

def format_timeseries_axis(ax, rotate_labels=True):
    """Format x-axis for time series plots."""
    if rotate_labels:
        ax.tick_params(axis='x', rotation=45)
    ax.set_xlabel('Time', fontsize=FONT_SIZES['label'])
    ax.grid(True, alpha=0.3)


def format_cost_axis(ax, currency='€'):
    """Format y-axis for cost plots."""
    ax.set_ylabel(f'Cost [{currency}/year]', fontsize=FONT_SIZES['label'])

    # Use thousand separators
    from matplotlib.ticker import FuncFormatter
    def thousands(x, pos):
        return f'{x/1000:.0f}k'
    ax.yaxis.set_major_formatter(FuncFormatter(thousands))


def format_power_axis(ax, unit='MW'):
    """Format y-axis for power/energy plots."""
    ax.set_ylabel(f'Power [{unit}]', fontsize=FONT_SIZES['label'])
    ax.grid(True, alpha=0.3)


def add_legend_below(ax, ncol=3):
    """Add legend below the plot (useful for multi-panel figures)."""
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15),
              ncol=ncol, frameon=True)


def add_subplot_labels(axes, labels=None, loc='upper left', fontsize=None):
    """
    Add (a), (b), (c) labels to subplot panels.

    Parameters
    ----------
    axes : array of Axes
        Subplot axes
    labels : list of str, optional
        Custom labels (default: ['(a)', '(b)', ...])
    loc : str
        Location of labels
    fontsize : int, optional
        Font size (default: FONT_SIZES['label'] + 1)
    """
    if fontsize is None:
        fontsize = FONT_SIZES['label'] + 1

    if labels is None:
        labels = [f'({chr(97+i)})' for i in range(len(axes))]

    for ax, label in zip(axes, labels):
        ax.text(0.02, 0.98, label, transform=ax.transAxes,
                fontsize=fontsize, fontweight='bold',
                verticalalignment='top', horizontalalignment='left',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))


# ============================================================
# DEMONSTRATION / TEST
# ============================================================

def create_demo_figure():
    """Create a demonstration figure showing the style."""
    setup_paper_style()

    fig, axes = plt.subplots(2, 2, figsize=FIGSIZE_DOUBLE_COLUMN)
    fig.suptitle('EnerGIS Figure Style Demonstration', fontsize=FONT_SIZES['title'])

    # Panel (a): Line plot
    ax = axes[0, 0]
    x = np.linspace(0, 10, 100)
    for i, (name, color) in enumerate([('HP1', COLORS['heat_pump']),
                                        ('HP2', COLORS['chp']),
                                        ('Storage', COLORS['storage'])]):
        ax.plot(x, np.sin(x + i) + i, label=name, color=color, linewidth=LINE_WIDTH)
    ax.set_xlabel('Time [h]')
    ax.set_ylabel('Power [MW]')
    ax.legend(fontsize=FONT_SIZES['legend'])
    ax.grid(True, alpha=0.3)

    # Panel (b): Bar plot
    ax = axes[0, 1]
    categories = ['CAPEX', 'OPEX', 'Fuel', 'CO₂']
    values = [1200, 800, 500, 200]
    colors = [COLORS['capex'], COLORS['opex'], COLORS['fuel'], COLORS['co2']]
    ax.bar(categories, values, color=colors)
    ax.set_ylabel('Cost [k€/year]')
    ax.tick_params(axis='x', rotation=45)

    # Panel (c): Stacked area
    ax = axes[1, 0]
    x = np.arange(24)
    y1 = np.random.rand(24) * 10
    y2 = np.random.rand(24) * 5
    y3 = np.random.rand(24) * 3
    ax.stackplot(x, y1, y2, y3,
                 labels=['Heat Pump', 'CHP', 'Boiler'],
                 colors=[COLORS['heat_pump'], COLORS['chp'], COLORS['boiler']],
                 alpha=0.8)
    ax.set_xlabel('Hour of day')
    ax.set_ylabel('Heat generation [MW]')
    ax.legend(loc='upper left', fontsize=FONT_SIZES['legend'])
    ax.grid(True, alpha=0.3)

    # Panel (d): Scatter plot
    ax = axes[1, 1]
    x = np.random.randn(50)
    y = np.random.randn(50)
    ax.scatter(x, y, c=COLORS['baseline'], s=50, alpha=0.6, edgecolors='black', linewidths=0.5)
    ax.set_xlabel('CO₂ emissions [t/year]')
    ax.set_ylabel('Total cost [k€/year]')
    ax.grid(True, alpha=0.3)

    # Add subplot labels
    add_subplot_labels(axes.flatten(), loc='upper left')

    plt.tight_layout()

    saved = save_figure(fig, 'demo_figure_style', formats=['pdf', 'png'])
    print(f"\n✓ Demo figure created: {saved}")

    return fig


if __name__ == '__main__':
    # Run demonstration
    fig = create_demo_figure()
    print("\n" + "="*60)
    print("Figure style demonstration complete!")
    print("Use this module in your plotting scripts:")
    print("  from figure_styles import setup_paper_style, COLORS, save_figure")
    print("="*60)
