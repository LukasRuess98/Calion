"""
Publication-quality plotting utilities for Applied Energies and similar journals.

This module provides enhanced visualization capabilities optimized for scientific
publications with:
- High-resolution exports (300-600 DPI)
- Multiple formats (PNG, PDF, EPS)
- Publication-ready styling (colorblind-friendly, proper fonts)
- Extended analysis plots (COP, emissions, load duration curves, etc.)
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, Sequence
import numpy as np

from energis.utils.timeseries import TimeSeriesTable

try:  # pragma: no cover - optional dependency
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    import matplotlib.patches as mpatches

    HAVE_MATPLOTLIB = True
except Exception:  # pragma: no cover - matplotlib optional
    HAVE_MATPLOTLIB = False
    plt = None
    mdates = None

__all__ = ["HAVE_MATPLOTLIB", "export_publication_plots", "PublicationConfig"]


# ============================================================================
# Publication Configuration
# ============================================================================

class PublicationConfig:
    """Configuration for publication-quality plots."""

    # Figure sizes (in inches) - based on Applied Energies guidelines
    # Two-column width: ~190mm, One-column: ~90mm
    FIGSIZE_SINGLE_COLUMN = (3.5, 2.625)  # 90mm x 67.5mm (aspect 4:3)
    FIGSIZE_DOUBLE_COLUMN = (7.0, 4.5)     # 180mm x 115mm
    FIGSIZE_DOUBLE_COLUMN_TALL = (7.0, 5.5)

    # DPI settings
    DPI_SCREEN = 100
    DPI_PRINT = 300
    DPI_HIGH = 600

    # Font sizes (in points)
    FONT_SIZE_SMALL = 8
    FONT_SIZE_MEDIUM = 10
    FONT_SIZE_LARGE = 12

    # Colorblind-friendly color schemes
    # Based on Paul Tol's color schemes for scientific visualization
    COLORS_QUALITATIVE = [
        '#4477AA',  # Blue
        '#EE6677',  # Red
        '#228833',  # Green
        '#CCBB44',  # Yellow
        '#66CCEE',  # Cyan
        '#AA3377',  # Purple
        '#BBBBBB',  # Grey
    ]

    COLORS_SEQUENTIAL_BLUE = ['#F0F9FF', '#9ECAE1', '#4292C6', '#08519C', '#08306B']
    COLORS_SEQUENTIAL_RED = ['#FEE5D9', '#FCAE91', '#FB6A4A', '#CB181D', '#67000D']

    # Technology-specific colors
    COLORS_TECH = {
        'heat_pump': '#4477AA',
        'gas_boiler': '#EE6677',
        'biomass': '#228833',
        'waste_heat': '#CCBB44',
        'p2h': '#66CCEE',
        'storage_charge': '#AA3377',
        'storage_discharge': '#BBBBBB',
        'grid_import': '#CB181D',
        'grid_export': '#41AB5D',
    }

    @staticmethod
    def apply_style():
        """Apply publication-ready matplotlib style."""
        if not HAVE_MATPLOTLIB:
            return

        plt.rcParams.update({
            'font.size': PublicationConfig.FONT_SIZE_MEDIUM,
            'axes.labelsize': PublicationConfig.FONT_SIZE_MEDIUM,
            'axes.titlesize': PublicationConfig.FONT_SIZE_LARGE,
            'xtick.labelsize': PublicationConfig.FONT_SIZE_SMALL,
            'ytick.labelsize': PublicationConfig.FONT_SIZE_SMALL,
            'legend.fontsize': PublicationConfig.FONT_SIZE_SMALL,
            'figure.titlesize': PublicationConfig.FONT_SIZE_LARGE,

            # Use sans-serif fonts (better for figures)
            'font.family': 'sans-serif',
            'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],

            # Line widths
            'axes.linewidth': 0.8,
            'grid.linewidth': 0.5,
            'lines.linewidth': 1.5,

            # Grid
            'axes.grid': True,
            'grid.alpha': 0.3,
            'axes.axisbelow': True,

            # Spines
            'axes.spines.top': False,
            'axes.spines.right': False,

            # Legend
            'legend.frameon': True,
            'legend.framealpha': 0.8,
            'legend.fancybox': False,
            'legend.edgecolor': '0.8',

            # Figure
            'figure.facecolor': 'white',
            'axes.facecolor': 'white',
            'savefig.dpi': PublicationConfig.DPI_PRINT,
            'savefig.bbox': 'tight',
            'savefig.pad_inches': 0.05,
        })


# ============================================================================
# Main Export Function
# ============================================================================

def export_publication_plots(
    outdir: str,
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    summary_sections: Mapping[str, Mapping[str, object]] | None = None,
    *,
    dpi: int = 300,
    formats: Sequence[str] = ("png", "pdf"),
    plot_types: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    """
    Generate publication-quality figures for scientific journals.

    Parameters
    ----------
    outdir : str
        Output directory for plots
    table : TimeSeriesTable
        Input time series data
    series : Mapping[str, Sequence[float]]
        Result time series (component outputs, grid flows, etc.)
    summary_sections : Mapping[str, Mapping[str, object]], optional
        Summary statistics (costs, design decisions, etc.)
    dpi : int, default=300
        Resolution for raster formats (PNG)
    formats : Sequence[str], default=("png", "pdf")
        Export formats: "png", "pdf", "eps", "svg"
    plot_types : Sequence[str], optional
        Which plots to generate. If None, generates all available plots.
        Options: "heat_balance", "electric_balance", "storage", "cost_breakdown",
                 "cop_analysis", "emissions", "load_duration", "monthly_aggregate",
                 "technology_comparison", "efficiency_metrics"

    Returns
    -------
    dict[str, list[str]]
        Dictionary mapping plot type to list of generated file paths
    """

    if not HAVE_MATPLOTLIB:
        print("[EXPORT] Matplotlib not available - skipping publication plots.")
        return {}

    if not table.index:
        print("[EXPORT] No time series data - skipping publication plots.")
        return {}

    os.makedirs(outdir, exist_ok=True)
    PublicationConfig.apply_style()

    timestamps: Sequence[datetime] | Sequence[int]
    first = table.index[0]
    if isinstance(first, datetime):
        timestamps = table.index
    else:
        timestamps = list(range(len(table.index)))

    generated: dict[str, list[str]] = {}

    # Available plot functions
    plot_functions = {
        "heat_balance": lambda: _heat_balance_publication(
            outdir, timestamps, table, series, dpi, formats
        ),
        "electric_balance": lambda: _electric_balance_publication(
            outdir, timestamps, table, series, dpi, formats
        ),
        "storage": lambda: _storage_publication(
            outdir, timestamps, series, dpi, formats
        ),
        "cost_breakdown": lambda: _cost_breakdown_publication(
            outdir, summary_sections, dpi, formats
        ) if summary_sections else [],
        "cop_analysis": lambda: _cop_analysis_publication(
            outdir, timestamps, table, series, dpi, formats
        ),
        "emissions": lambda: _emissions_publication(
            outdir, timestamps, table, series, summary_sections, dpi, formats
        ),
        "load_duration": lambda: _load_duration_publication(
            outdir, timestamps, table, series, dpi, formats
        ),
        "monthly_aggregate": lambda: _monthly_aggregate_publication(
            outdir, timestamps, table, series, dpi, formats
        ),
        "technology_comparison": lambda: _technology_comparison_publication(
            outdir, summary_sections, dpi, formats
        ) if summary_sections else [],
        "capex_opex": lambda: _capex_opex_publication(
            outdir, summary_sections, dpi, formats
        ) if summary_sections else [],
    }

    # Determine which plots to generate
    if plot_types is None:
        plot_types = list(plot_functions.keys())

    # Generate plots
    for plot_type in plot_types:
        if plot_type in plot_functions:
            try:
                files = plot_functions[plot_type]()
                if files:
                    generated[plot_type] = files
            except Exception as e:
                print(f"[EXPORT] Warning: Failed to generate {plot_type}: {e}")

    return generated


# ============================================================================
# Helper Functions
# ============================================================================

def _save_figure(fig, outdir: str, basename: str, dpi: int, formats: Sequence[str]) -> list[str]:
    """Save figure in multiple formats."""
    files = []
    for fmt in formats:
        filepath = os.path.join(outdir, f"{basename}.{fmt}")
        if fmt == "png":
            fig.savefig(filepath, dpi=dpi, format='png')
        elif fmt == "pdf":
            fig.savefig(filepath, format='pdf')
        elif fmt == "eps":
            fig.savefig(filepath, format='eps')
        elif fmt == "svg":
            fig.savefig(filepath, format='svg')
        files.append(filepath)
    plt.close(fig)
    return files


def _configure_time_axis(ax, timestamps: Sequence[datetime] | Sequence[int]) -> None:
    """Configure time axis with proper formatting."""
    if isinstance(timestamps[0], datetime) and mdates is not None:
        locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        ax.set_xlabel("Time")
    else:
        ax.set_xlabel("Time step")

    # Rotate labels for better readability
    for label in ax.get_xticklabels():
        label.set_rotation(0)
        label.set_ha('center')


def _prettify_label_en(name: str) -> str:
    """Convert internal variable names to publication-ready English labels."""
    # Remove common suffixes
    label = name
    units = ""

    suffix_map = {
        "_Q_th_MW": " Heat",
        "_Pel_MW": " Power",
        "_fuel_MW": " Fuel",
        "_MW": "",
        "_MWh": "",
        "_EUR": "",
        "_t": "",
        "_SOC_MWh": " SOC",
        "_charge_MW": " Charge",
        "_discharge_MW": " Discharge",
    }

    for suffix, replacement in suffix_map.items():
        if label.endswith(suffix):
            label = label[:-len(suffix)] + replacement
            break

    # Replace component names
    replacements = {
        "HP1": "Heat Pump 1",
        "HP2": "Heat Pump 2",
        "HP3": "Heat Pump 3",
        "HP4": "Heat Pump 4",
        "HKW": "Gas Boiler",
        "GTOST": "Peak Boiler",
        "P2H": "Power-to-Heat",
        "BMHKW": "Biomass CHP",
        "HWS": "Summer Waste Heat",
        "HWW": "Winter Waste Heat",
        "AVA": "Waste Incineration",
        "TES": "Thermal Storage",
        "P_buy": "Grid Import",
        "P_sell": "Grid Export",
        "waermebedarf": "Heat Demand",
    }

    for old, new in replacements.items():
        label = label.replace(old, new)

    return label.strip()


def _has_content(values: Sequence[float]) -> bool:
    """Check if a time series has non-zero values."""
    return any(abs(float(v)) > 1e-9 for v in values)


# ============================================================================
# Publication Plots
# ============================================================================

def _heat_balance_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate publication-quality heat balance plot."""
    demand = table.data.get("waermebedarf_MWth")
    if not demand:
        return []

    supply_components: list[Sequence[float]] = []
    labels: list[str] = []
    colors: list[str] = []

    # Order components by type
    component_order = [
        ("HP1_Q_th_MW", PublicationConfig.COLORS_TECH['heat_pump']),
        ("HP2_Q_th_MW", PublicationConfig.COLORS_TECH['heat_pump']),
        ("HP3_Q_th_MW", PublicationConfig.COLORS_TECH['heat_pump']),
        ("HP4_Q_th_MW", PublicationConfig.COLORS_TECH['heat_pump']),
        ("HKW_Q_th_MW", PublicationConfig.COLORS_TECH['gas_boiler']),
        ("GTOST_Q_th_MW", PublicationConfig.COLORS_TECH['gas_boiler']),
        ("BMHKW_Q_th_MW", PublicationConfig.COLORS_TECH['biomass']),
        ("HWS_Q_th_MW", PublicationConfig.COLORS_TECH['waste_heat']),
        ("HWW_Q_th_MW", PublicationConfig.COLORS_TECH['waste_heat']),
        ("AVA_Q_th_MW", PublicationConfig.COLORS_TECH['waste_heat']),
        ("P2H_Q_th_MW", PublicationConfig.COLORS_TECH['p2h']),
        ("TES_discharge_MW", PublicationConfig.COLORS_TECH['storage_discharge']),
    ]

    for key, color in component_order:
        if key in series and _has_content(series[key]):
            supply_components.append(series[key])
            labels.append(_prettify_label_en(key))
            colors.append(color)

    if not supply_components:
        return []

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN, constrained_layout=True)

    # Stack plot with proper colors
    ax.stackplot(timestamps, *supply_components, labels=labels, colors=colors, alpha=0.8, linewidth=0)

    # Demand line
    ax.plot(timestamps, demand, color='black', linewidth=2.0, label='Heat Demand', linestyle='--')

    ax.set_ylabel("Thermal Power [MW]")
    ax.set_title("Heat Supply and Demand Balance")
    ax.grid(True, which="both", axis="y", alpha=0.3)
    _configure_time_axis(ax, timestamps)

    # Legend with multiple columns
    ax.legend(loc='upper left', frameon=True, ncol=3, bbox_to_anchor=(0, -0.15))

    return _save_figure(fig, outdir, "heat_balance_publication", dpi, formats)


def _electric_balance_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate publication-quality electric balance plot."""
    pbuy = series.get("P_buy_MW")
    psell = series.get("P_sell_MW")

    if not pbuy and not psell:
        return []

    consumption_components: list[Sequence[float]] = []
    labels: list[str] = []
    colors: list[str] = []

    # Gather consumption components
    component_order = [
        ("HP1_Pel_MW", PublicationConfig.COLORS_QUALITATIVE[0]),
        ("HP2_Pel_MW", PublicationConfig.COLORS_QUALITATIVE[1]),
        ("HP3_Pel_MW", PublicationConfig.COLORS_QUALITATIVE[2]),
        ("HP4_Pel_MW", PublicationConfig.COLORS_QUALITATIVE[3]),
        ("P2H_Pel_MW", PublicationConfig.COLORS_TECH['p2h']),
    ]

    for key, color in component_order:
        if key in series and _has_content(series[key]):
            consumption_components.append(series[key])
            labels.append(_prettify_label_en(key))
            colors.append(color)

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN, constrained_layout=True)

    if consumption_components:
        ax.stackplot(timestamps, *consumption_components, labels=labels, colors=colors, alpha=0.7, linewidth=0)

    if pbuy:
        ax.plot(timestamps, pbuy, color=PublicationConfig.COLORS_TECH['grid_import'],
                linewidth=2.0, label='Grid Import')
    if psell:
        ax.plot(timestamps, psell, color=PublicationConfig.COLORS_TECH['grid_export'],
                linewidth=2.0, label='Grid Export', linestyle='--')

    ax.set_ylabel("Electric Power [MW]")
    ax.set_title("Electric Power Balance")
    ax.grid(True, which="both", axis="y", alpha=0.3)
    _configure_time_axis(ax, timestamps)
    ax.legend(loc='upper left', frameon=True, ncol=3, bbox_to_anchor=(0, -0.15))

    return _save_figure(fig, outdir, "electric_balance_publication", dpi, formats)


def _storage_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    series: Mapping[str, Sequence[float]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate publication-quality storage operation plot."""
    soc = series.get("TES_SOC_MWh")
    if not soc or not _has_content(soc):
        return []

    charge = series.get("TES_charge_MW")
    discharge = series.get("TES_discharge_MW")

    fig, ax1 = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN, constrained_layout=True)

    # SOC on primary axis
    color1 = PublicationConfig.COLORS_QUALITATIVE[0]
    ax1.plot(timestamps, soc, color=color1, linewidth=2.0, label='State of Charge')
    ax1.set_ylabel("Energy Content [MWh]", color=color1)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True, which="both", alpha=0.3)
    _configure_time_axis(ax1, timestamps)

    # Charge/discharge on secondary axis
    if (charge and _has_content(charge)) or (discharge and _has_content(discharge)):
        ax2 = ax1.twinx()

        if charge and _has_content(charge):
            ax2.fill_between(
                timestamps, 0, charge,
                color=PublicationConfig.COLORS_TECH['storage_charge'],
                alpha=0.4, label='Charging'
            )

        if discharge and _has_content(discharge):
            discharge_neg = [-abs(v) for v in discharge]
            ax2.fill_between(
                timestamps, 0, discharge_neg,
                color=PublicationConfig.COLORS_TECH['storage_discharge'],
                alpha=0.4, label='Discharging'
            )

        ax2.set_ylabel("Charge/Discharge Power [MW]")
        ax2.axhline(y=0, color='black', linewidth=0.8)

        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True)
    else:
        ax1.legend(loc='upper left', frameon=True)

    ax1.set_title("Thermal Energy Storage Operation")

    return _save_figure(fig, outdir, "storage_operation_publication", dpi, formats)


def _cost_breakdown_publication(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate publication-quality cost breakdown plot."""
    objective = summary_sections.get("objective")
    if not isinstance(objective, Mapping):
        return []

    entries: list[tuple[str, float]] = []
    for key, value in objective.items():
        if not key.endswith("_EUR") or key == "OBJ_value_EUR":
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if abs(number) < 1e-6:
            continue

        # Clean up label
        label = key.replace("_EUR", "").replace("_", " ").title()
        entries.append((label, number))

    if not entries:
        return []

    # Sort by absolute value
    entries.sort(key=lambda item: abs(item[1]), reverse=True)
    labels, values = zip(*entries)

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN, constrained_layout=True)

    positions = range(len(labels))
    colors = [PublicationConfig.COLORS_QUALITATIVE[0] if val >= 0
              else PublicationConfig.COLORS_QUALITATIVE[1] for val in values]

    bars = ax.barh(positions, values, color=colors, alpha=0.8)
    ax.set_yticks(list(positions), labels)
    ax.invert_yaxis()
    ax.set_xlabel("Cost [EUR]")
    ax.set_title("Total System Cost Breakdown")
    ax.grid(True, axis="x", alpha=0.3)
    ax.axvline(0, color="black", linewidth=1.0)

    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, values)):
        if abs(val) > 0:
            label_x = val + (max(values) - min(values)) * 0.02
            ax.text(label_x, i, f'{val:,.0f}', va='center', ha='left', fontsize=8)

    return _save_figure(fig, outdir, "cost_breakdown_publication", dpi, formats)


def _cop_analysis_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate COP (Coefficient of Performance) analysis for heat pumps."""
    # Get outdoor temperature if available
    outdoor_temp = table.data.get("Temp_Aussen") or table.data.get("T_outdoor") or table.data.get("temperature")

    cop_data = []
    hp_names = []

    # Calculate COP for each heat pump
    for hp in ["HP1", "HP2", "HP3", "HP4"]:
        q_th_key = f"{hp}_Q_th_MW"
        pel_key = f"{hp}_Pel_MW"

        if q_th_key in series and pel_key in series:
            q_th = np.array(series[q_th_key])
            pel = np.array(series[pel_key])

            # Calculate COP only when both are non-zero
            cop = np.zeros_like(q_th)
            mask = (pel > 1e-6) & (q_th > 1e-6)
            cop[mask] = q_th[mask] / pel[mask]

            if _has_content(cop):
                cop_data.append(cop)
                hp_names.append(_prettify_label_en(hp))

    if not cop_data:
        return []

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN, constrained_layout=True)

    # Plot COP time series
    for i, (cop, name) in enumerate(zip(cop_data, hp_names)):
        color = PublicationConfig.COLORS_QUALITATIVE[i % len(PublicationConfig.COLORS_QUALITATIVE)]
        # Only plot non-zero values
        cop_plot = np.where(cop > 0.1, cop, np.nan)
        ax.plot(timestamps, cop_plot, label=name, color=color, linewidth=1.5, alpha=0.8)

    ax.set_ylabel("Coefficient of Performance (COP)")
    ax.set_title("Heat Pump Efficiency Over Time")
    ax.grid(True, which="both", alpha=0.3)
    _configure_time_axis(ax, timestamps)
    ax.legend(loc='best', frameon=True)
    ax.set_ylim(bottom=0)

    return _save_figure(fig, outdir, "cop_analysis_publication", dpi, formats)


def _emissions_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    summary_sections: Mapping[str, Mapping[str, object]] | None,
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate CO2 emissions analysis plot."""
    # Try to find emissions data in grid section
    if not summary_sections or "grid" not in summary_sections:
        return []

    grid_section = summary_sections["grid"]
    total_emissions = grid_section.get("total_co2_emissions_t")

    if not total_emissions:
        return []

    # Create a simple bar chart showing emissions breakdown
    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_SINGLE_COLUMN, constrained_layout=True)

    categories = ["Total CO₂ Emissions"]
    values = [float(total_emissions)]

    bars = ax.bar(categories, values, color=PublicationConfig.COLORS_QUALITATIVE[1], alpha=0.8)
    ax.set_ylabel("CO₂ Emissions [t]")
    ax.set_title("Annual CO₂ Emissions")
    ax.grid(True, axis="y", alpha=0.3)

    # Add value label on bar
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:,.0f} t', ha='center', va='bottom', fontsize=10)

    return _save_figure(fig, outdir, "emissions_publication", dpi, formats)


def _load_duration_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate load duration curve (sorted demand curve)."""
    demand = table.data.get("waermebedarf_MWth")
    if not demand:
        return []

    # Sort demand in descending order
    sorted_demand = np.sort(demand)[::-1]
    hours = np.arange(len(sorted_demand))

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN, constrained_layout=True)

    ax.plot(hours, sorted_demand, color=PublicationConfig.COLORS_QUALITATIVE[0], linewidth=2.0)
    ax.fill_between(hours, 0, sorted_demand, alpha=0.3, color=PublicationConfig.COLORS_QUALITATIVE[0])

    ax.set_xlabel("Hours [h]")
    ax.set_ylabel("Heat Demand [MW]")
    ax.set_title("Heat Load Duration Curve")
    ax.grid(True, which="both", alpha=0.3)

    # Add reference lines for peak and average
    peak = max(sorted_demand)
    avg = np.mean(sorted_demand)
    ax.axhline(peak, color='red', linestyle='--', linewidth=1.0, alpha=0.7, label=f'Peak: {peak:.1f} MW')
    ax.axhline(avg, color='green', linestyle='--', linewidth=1.0, alpha=0.7, label=f'Average: {avg:.1f} MW')
    ax.legend(loc='upper right', frameon=True)

    return _save_figure(fig, outdir, "load_duration_curve_publication", dpi, formats)


def _monthly_aggregate_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate monthly aggregated energy flows."""
    if not isinstance(timestamps[0], datetime):
        return []  # Need datetime for monthly aggregation

    demand = table.data.get("waermebedarf_MWth")
    if not demand:
        return []

    # Convert to numpy arrays
    ts_array = np.array(timestamps)
    demand_array = np.array(demand)

    # Extract months
    months = np.array([dt.month for dt in timestamps])
    unique_months = sorted(set(months))

    # Aggregate by month
    monthly_demand = []
    month_labels = []

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    for month in unique_months:
        mask = months == month
        monthly_energy = np.sum(demand_array[mask])  # MWh (assuming hourly data)
        monthly_demand.append(monthly_energy)
        month_labels.append(month_names[month - 1])

    if not monthly_demand:
        return []

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN, constrained_layout=True)

    bars = ax.bar(month_labels, monthly_demand, color=PublicationConfig.COLORS_QUALITATIVE[0], alpha=0.8)
    ax.set_ylabel("Heat Energy [MWh]")
    ax.set_xlabel("Month")
    ax.set_title("Monthly Heat Demand")
    ax.grid(True, axis="y", alpha=0.3)

    # Add value labels on bars
    for bar, val in zip(bars, monthly_demand):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:,.0f}', ha='center', va='bottom', fontsize=8, rotation=0)

    return _save_figure(fig, outdir, "monthly_demand_publication", dpi, formats)


def _technology_comparison_publication(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate technology contribution comparison."""
    # Extract energy contributions from different technologies
    tech_contributions = {}

    # Look for heat pump data
    for hp in ["HP1", "HP2", "HP3", "HP4"]:
        key = f"heat_pump_{hp}"
        if key in summary_sections:
            hp_data = summary_sections[key]
            energy = hp_data.get("total_heat_output_MWh")
            if energy and float(energy) > 1e-3:
                tech_contributions[_prettify_label_en(hp)] = float(energy)

    # Look for other generators
    for gen in ["HKW", "GTOST", "BMHKW", "P2H", "HWS", "HWW", "AVA"]:
        # Try multiple possible keys
        for prefix in ["generator_", "thermal_generator_", ""]:
            key = f"{prefix}{gen}"
            if key in summary_sections:
                gen_data = summary_sections[key]
                energy = gen_data.get("total_heat_output_MWh") or gen_data.get("total_thermal_output_MWh")
                if energy and float(energy) > 1e-3:
                    tech_contributions[_prettify_label_en(gen)] = float(energy)
                    break

    if not tech_contributions:
        return []

    # Sort by contribution
    sorted_items = sorted(tech_contributions.items(), key=lambda x: x[1], reverse=True)
    labels, values = zip(*sorted_items)

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN, constrained_layout=True)

    colors = [PublicationConfig.COLORS_QUALITATIVE[i % len(PublicationConfig.COLORS_QUALITATIVE)]
              for i in range(len(labels))]

    bars = ax.barh(range(len(labels)), values, color=colors, alpha=0.8)
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.set_xlabel("Heat Production [MWh]")
    ax.set_title("Heat Production by Technology")
    ax.grid(True, axis="x", alpha=0.3)

    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, values)):
        label_x = val + max(values) * 0.02
        ax.text(label_x, i, f'{val:,.0f}', va='center', ha='left', fontsize=8)

    return _save_figure(fig, outdir, "technology_comparison_publication", dpi, formats)


def _capex_opex_publication(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate CAPEX vs OPEX breakdown."""
    objective = summary_sections.get("objective")
    if not isinstance(objective, Mapping):
        return []

    # Identify CAPEX and OPEX components
    capex_keys = ["Invest_EUR", "Install_EUR", "Fixed_OM_EUR"]
    opex_keys = ["Energy_EUR", "Fuel_EUR", "CO2_EUR", "Demand_charge_EUR"]

    capex_total = 0.0
    opex_total = 0.0

    for key in capex_keys:
        val = objective.get(key)
        if val:
            try:
                capex_total += float(val)
            except (TypeError, ValueError):
                pass

    for key in opex_keys:
        val = objective.get(key)
        if val:
            try:
                opex_total += float(val)
            except (TypeError, ValueError):
                pass

    if capex_total < 1e-3 and opex_total < 1e-3:
        return []

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_SINGLE_COLUMN, constrained_layout=True)

    categories = ['CAPEX', 'OPEX']
    values = [capex_total, opex_total]
    colors = [PublicationConfig.COLORS_QUALITATIVE[0], PublicationConfig.COLORS_QUALITATIVE[1]]

    bars = ax.bar(categories, values, color=colors, alpha=0.8)
    ax.set_ylabel("Cost [EUR]")
    ax.set_title("Capital vs Operational Expenditure")
    ax.grid(True, axis="y", alpha=0.3)

    # Add value labels
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:,.0f}', ha='center', va='bottom', fontsize=9)

    # Add percentage labels
    total = sum(values)
    if total > 0:
        for bar, val in zip(bars, values):
            pct = (val / total) * 100
            ax.text(bar.get_x() + bar.get_width()/2., val/2,
                    f'{pct:.1f}%', ha='center', va='center',
                    fontsize=10, fontweight='bold', color='white')

    return _save_figure(fig, outdir, "capex_opex_publication", dpi, formats)
