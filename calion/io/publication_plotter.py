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
from typing import Mapping, Sequence
import numpy as np

from calion.utils.timeseries import TimeSeriesTable
from calion.io.plot_utils import (
    has_content,
    prettify_label_en,
    save_figure as _save_figure_util,
)
from calion.logging_config import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

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
    formats: Sequence[str] = ("pdf", "svg"),
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
        Resolution for raster formats (PNG, TIFF)
    formats : Sequence[str], default=("pdf", "svg")
        Export formats: "pdf", "svg", "eps", "png", "tiff"
        Recommended combinations:
        - ("pdf", "svg"): Modern, editable vector formats (default)
        - ("pdf", "eps"): Classic LaTeX compatibility
        - ("pdf", "svg", "png"): With raster fallback
    plot_types : Sequence[str], optional
        Which plots to generate. If None, generates all available plots.
        Options: "heat_balance", "electric_balance", "storage", "cost_breakdown",
                 "cop_analysis", "emissions", "load_duration", "monthly_aggregate",
                 "technology_comparison", "capex_opex", "electricity_cost_pie",
                 "fuel_cost_breakdown"

    Returns
    -------
    dict[str, list[str]]
        Dictionary mapping plot type to list of generated file paths
    """

    if not HAVE_MATPLOTLIB:
        logger.info("[EXPORT] Matplotlib not available - skipping publication plots.")
        return {}

    if not table.index:
        logger.info("[EXPORT] No time series data - skipping publication plots.")
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
        "input_data": lambda: _input_data_publication(
            outdir, timestamps, table, series, dpi, formats
        ),
        "results_combined": lambda: _results_combined_publication(
            outdir, timestamps, table, series, dpi, formats
        ),
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
        "electricity_cost_pie": lambda: _electricity_cost_pie_publication(
            outdir, summary_sections, dpi, formats
        ) if summary_sections else [],
        "fuel_cost_breakdown": lambda: _fuel_cost_breakdown_publication(
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
                logger.info(f"[EXPORT] Warning: Failed to generate {plot_type}: {e}")

    return generated


# ============================================================================
# Helper Functions
# ============================================================================

# Backwards compatibility: delegate to shared utilities
def _save_figure(fig, outdir: str, basename: str, dpi: int, formats: Sequence[str]) -> list[str]:
    """Save figure in multiple formats (wrapper with plt.close)."""
    files = _save_figure_util(fig, outdir, basename, dpi, formats)
    plt.close(fig)
    return files


def _configure_time_axis(ax, timestamps: Sequence[datetime] | Sequence[int]) -> None:
    """Configure time axis with proper formatting."""
    if timestamps and isinstance(timestamps[0], datetime) and mdates is not None:
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


# Delegate label and content checks to shared utilities
_prettify_label_en = prettify_label_en
_has_content = has_content


# ============================================================================
# Publication Plots
# ============================================================================

def _input_data_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate publication-quality input data overview plot.

    Shows key input data: Heat demand, Electricity price, Waste heat recovery
    temperature and thermal power.
    """
    demand = table.data.get("waermebedarf_MWth")
    if not demand:
        return []

    # Collect available input data
    electricity_price = table.data.get("strompreis_eur_per_mwh")
    wrg_temp = table.data.get("wrg_temperatur_c") or table.data.get("waste_heat_temp_c")
    wrg_q = table.data.get("wrg_q_mw") or table.data.get("waste_heat_q_mw")

    # Count how many data sources we have
    n_plots = 1  # Always have demand
    if electricity_price and _has_content(electricity_price):
        n_plots += 1
    if wrg_temp and _has_content(wrg_temp):
        n_plots += 1
    if wrg_q and _has_content(wrg_q):
        n_plots += 1

    if n_plots == 1:
        # Only demand available, skip this plot
        return []

    # Create subplots
    fig, axes = plt.subplots(n_plots, 1,
                            figsize=(PublicationConfig.FIGSIZE_DOUBLE_COLUMN[0],
                                    2.5 * n_plots),
                            constrained_layout=True)

    if n_plots == 1:
        axes = [axes]

    plot_idx = 0

    # Plot 1: Heat Demand
    ax = axes[plot_idx]
    ax.plot(timestamps, demand, color=PublicationConfig.COLORS_QUALITATIVE[0],
            linewidth=1.5, label='Heat Demand')
    ax.fill_between(timestamps, 0, demand, alpha=0.3,
                    color=PublicationConfig.COLORS_QUALITATIVE[0])
    ax.set_ylabel("Heat Demand [MW]")
    ax.set_title("Input Data Overview", fontsize=12, fontweight='bold', loc='left')
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc='upper right', frameon=True)
    plot_idx += 1

    # Plot 2: Electricity Price (if available)
    if electricity_price and _has_content(electricity_price):
        ax = axes[plot_idx]
        ax.plot(timestamps, electricity_price,
                color=PublicationConfig.COLORS_QUALITATIVE[1],
                linewidth=1.5, label='Electricity Price')
        ax.set_ylabel("Price [EUR/MWh]")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(loc='upper right', frameon=True)
        plot_idx += 1

    # Plot 3: Waste Heat Temperature (if available)
    if wrg_temp and _has_content(wrg_temp):
        ax = axes[plot_idx]
        ax.plot(timestamps, wrg_temp,
                color=PublicationConfig.COLORS_QUALITATIVE[2],
                linewidth=1.5, label='Waste Heat Temperature')
        ax.set_ylabel("Temperature [°C]")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(loc='upper right', frameon=True)
        plot_idx += 1

    # Plot 4: Waste Heat Power (if available)
    if wrg_q and _has_content(wrg_q):
        ax = axes[plot_idx]
        ax.plot(timestamps, wrg_q,
                color=PublicationConfig.COLORS_QUALITATIVE[3],
                linewidth=1.5, label='Waste Heat Recovery')
        ax.fill_between(timestamps, 0, wrg_q, alpha=0.3,
                        color=PublicationConfig.COLORS_QUALITATIVE[3])
        ax.set_ylabel("Thermal Power [MW]")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(loc='upper right', frameon=True)

    # Configure time axis for bottom plot only
    _configure_time_axis(axes[-1], timestamps)

    # Hide x-axis labels for all but bottom plot
    for ax in axes[:-1]:
        ax.set_xlabel("")
        ax.tick_params(labelbottom=False)

    return _save_figure(fig, outdir, "input_data_overview", dpi, formats)


def _results_combined_publication(
    outdir: str,
    timestamps: Sequence[datetime] | Sequence[int],
    table: TimeSeriesTable,
    series: Mapping[str, Sequence[float]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate combined results plot: Demand, Generation, and Electricity Price.

    Shows the optimization results with heat demand, total heat generation,
    and electricity prices in one comprehensive view.
    """
    demand = table.data.get("waermebedarf_MWth")
    if not demand:
        return []

    # Calculate total generation from all thermal sources
    total_generation = np.zeros(len(timestamps))
    generation_found = False

    for key, values in series.items():
        if key == "TES_charge_MW":
            continue  # Don't count storage charging as generation
        if key.endswith("_Q_th_MW") or key == "TES_discharge_MW":
            if _has_content(values):
                total_generation += np.array(values)
                generation_found = True

    if not generation_found:
        return []

    # Get electricity price if available
    electricity_price = table.data.get("strompreis_eur_per_mwh")
    has_price = electricity_price and _has_content(electricity_price)

    # Create figure with dual y-axis
    fig, ax1 = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN_TALL,
                           constrained_layout=True)

    # Primary axis: Heat demand and generation
    color_demand = PublicationConfig.COLORS_QUALITATIVE[0]
    color_generation = PublicationConfig.COLORS_QUALITATIVE[1]

    ax1.plot(timestamps, demand, color=color_demand, linewidth=2.0,
            label='Heat Demand', linestyle='--', alpha=0.9)
    ax1.plot(timestamps, total_generation, color=color_generation, linewidth=2.0,
            label='Total Heat Generation', alpha=0.8)
    ax1.fill_between(timestamps, 0, total_generation,
                     alpha=0.2, color=color_generation)

    ax1.set_ylabel("Thermal Power [MW]", fontsize=11)
    ax1.set_title("System Operation: Heat Balance and Electricity Price",
                 fontsize=12, fontweight='bold')
    ax1.grid(True, which="both", alpha=0.3)
    _configure_time_axis(ax1, timestamps)

    # Secondary axis: Electricity price
    if has_price:
        ax2 = ax1.twinx()
        color_price = PublicationConfig.COLORS_QUALITATIVE[3]

        ax2.plot(timestamps, electricity_price, color=color_price,
                linewidth=1.5, label='Electricity Price',
                linestyle=':', alpha=0.7)
        ax2.set_ylabel("Electricity Price [EUR/MWh]", fontsize=11,
                      color=color_price)
        ax2.tick_params(axis='y', labelcolor=color_price)

        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2,
                  loc='upper left', frameon=True, fontsize=9)
    else:
        ax1.legend(loc='upper left', frameon=True, fontsize=9)

    return _save_figure(fig, outdir, "results_combined", dpi, formats)


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
    """Generate publication-quality cost breakdown plot with grouped categories."""
    objective = summary_sections.get("objective")
    if not isinstance(objective, Mapping):
        return []

    # Group costs by category
    electricity_costs = []
    fuel_costs = []
    capex_costs = []
    other_costs = []
    revenue = []

    # Electricity costs (detailed breakdown)
    for key in ["Electricity_base_cost_EUR", "Electricity_energy_fee_EUR",
                "Electricity_grid_fee_EUR", "Demand_charge_cost_EUR"]:
        val = objective.get(key, 0.0)
        try:
            number = float(val)
            if abs(number) > 1e-3:
                label = key.replace("Electricity_", "").replace("_EUR", "").replace("_", " ").title()
                electricity_costs.append((label, number))
        except (TypeError, ValueError):
            pass

    # Fuel costs (total or by type)
    fuel_total = objective.get("Fuel_cost_EUR", 0.0)
    if abs(float(fuel_total)) > 1e-3:
        # Check for detailed fuel breakdown
        has_detail = False
        for key, val in objective.items():
            if key.startswith("Fuel_cost_") and key != "Fuel_cost_EUR" and key.endswith("_EUR"):
                try:
                    number = float(val)
                    if abs(number) > 1e-3:
                        fuel_type = key.replace("Fuel_cost_", "").replace("_EUR", "").title()
                        fuel_costs.append((f"{fuel_type} Fuel", number))
                        has_detail = True
                except (TypeError, ValueError):
                    pass
        if not has_detail:
            fuel_costs.append(("Fuel Cost", float(fuel_total)))

    # Investment costs (detailed breakdown)
    for key in ["Capex_heat_pumps_EUR", "Capex_storage_EUR", "Activation_cost_EUR",
                "Storage_installation_cost_EUR"]:
        val = objective.get(key, 0.0)
        try:
            number = float(val)
            if abs(number) > 1e-3:
                label = key.replace("Capex_", "").replace("_EUR", "").replace("_", " ").title()
                capex_costs.append((label, number))
        except (TypeError, ValueError):
            pass

    # Other costs
    for key in ["CO2_cost_EUR", "Dump_cost_EUR", "Tie_breaker_cost_EUR"]:
        val = objective.get(key, 0.0)
        try:
            number = float(val)
            if abs(number) > 1e-3:
                label = key.replace("_EUR", "").replace("_", " ").title()
                other_costs.append((label, number))
        except (TypeError, ValueError):
            pass

    # Revenue (negative cost)
    rev = objective.get("Grid_sell_revenue_EUR", 0.0)
    if abs(float(rev)) > 1e-3:
        revenue.append(("Grid Revenue", -float(rev)))

    # Combine all costs
    all_entries = []
    if electricity_costs:
        all_entries.append(("ELECTRICITY COSTS", None))  # Category header
        all_entries.extend(electricity_costs)
    if fuel_costs:
        all_entries.append(("FUEL COSTS", None))
        all_entries.extend(fuel_costs)
    if capex_costs:
        all_entries.append(("INVESTMENT COSTS", None))
        all_entries.extend(capex_costs)
    if other_costs:
        all_entries.append(("OTHER COSTS", None))
        all_entries.extend(other_costs)
    if revenue:
        all_entries.append(("REVENUE", None))
        all_entries.extend(revenue)

    if not all_entries:
        return []

    # Create figure
    fig, ax = plt.subplots(figsize=(8, max(6, len(all_entries) * 0.35)), constrained_layout=True)

    labels = []
    values = []
    colors = []
    y_positions = []
    y_pos = 0

    for label, value in all_entries:
        if value is None:
            # Category header - skip a position
            y_pos += 0.5
            continue
        labels.append(label)
        values.append(value)
        y_positions.append(y_pos)

        # Color based on category
        if value < 0:
            colors.append(PublicationConfig.COLORS_QUALITATIVE[2])  # Green for revenue
        else:
            colors.append(PublicationConfig.COLORS_QUALITATIVE[0])  # Blue for costs

        y_pos += 1

    # Draw bars
    bars = ax.barh(y_positions, values, color=colors, alpha=0.8, height=0.7)

    # Set labels
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Cost [EUR]", fontsize=10)
    ax.set_title("Detailed System Cost Breakdown", fontsize=12, fontweight='bold')
    ax.grid(True, axis="x", alpha=0.3)
    ax.axvline(0, color="black", linewidth=1.0)

    # Add value labels on bars
    for bar, val in zip(bars, values):
        if abs(val) > 0:
            width = bar.get_width()
            label_x = width + (max(values) - min(values)) * 0.01
            if width < 0:
                label_x = width - (max(values) - min(values)) * 0.01
                ha = 'right'
            else:
                ha = 'left'
            ax.text(label_x, bar.get_y() + bar.get_height()/2,
                   f'{val:,.0f}', va='center', ha=ha, fontsize=8)

    # Add category headers as text
    y_pos = 0
    for label, value in all_entries:
        if value is None:
            ax.text(-0.02, y_pos, label, transform=ax.get_yaxis_transform(),
                   fontsize=10, fontweight='bold', va='center', ha='right')
            y_pos += 0.5
        else:
            y_pos += 1

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
    """Generate CO2 emissions analysis plot with breakdown."""
    # Try to find emissions data in grid section and objective
    if not summary_sections or "grid" not in summary_sections:
        return []

    grid_section = summary_sections["grid"]
    objective = summary_sections.get("objective", {})

    # Use correct field name (new)
    total_emissions = grid_section.get("Total_CO2_emissions_t")
    grid_emissions = grid_section.get("Grid_CO2_emissions_t")
    fuel_emissions = objective.get("Fuel_emissions_t", 0.0)

    if not total_emissions or abs(float(total_emissions)) < 1e-3:
        return []

    # Create bar chart showing emissions breakdown
    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_SINGLE_COLUMN, constrained_layout=True)

    # Prepare data
    categories = []
    values = []

    if grid_emissions and abs(float(grid_emissions)) > 1e-3:
        categories.append("Grid\nElectricity")
        values.append(float(grid_emissions))

    if fuel_emissions and abs(float(fuel_emissions)) > 1e-3:
        categories.append("Fuel\nCombustion")
        values.append(float(fuel_emissions))

    if not values:
        # Fallback to total only
        categories = ["Total CO₂"]
        values = [float(total_emissions)]

    colors = [PublicationConfig.COLORS_QUALITATIVE[i % len(PublicationConfig.COLORS_QUALITATIVE)]
             for i in range(len(values))]

    bars = ax.bar(categories, values, color=colors, alpha=0.8)
    ax.set_ylabel("CO₂ Emissions [t]")
    ax.set_title("CO₂ Emissions Breakdown", fontsize=11, fontweight='bold')
    ax.grid(True, axis="y", alpha=0.3)

    # Add value labels on bars
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:,.1f} t', ha='center', va='bottom', fontsize=9)

    # Add total as text if we have breakdown
    if len(values) > 1:
        total = sum(values)
        ax.text(0.98, 0.98, f'Total: {total:,.1f} t',
               ha='right', va='top', fontsize=9, fontweight='bold',
               transform=ax.transAxes,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

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
    """Generate CAPEX vs OPEX breakdown with detailed subcategories."""
    objective = summary_sections.get("objective")
    if not isinstance(objective, Mapping):
        return []

    # Identify CAPEX components (using new field names)
    capex_keys = [
        "Capex_cost_EUR",
        "Activation_cost_EUR",
        "Storage_installation_cost_EUR",
    ]

    # Identify OPEX components (using new field names)
    opex_keys = [
        "Grid_energy_cost_EUR",
        "Fuel_cost_EUR",
        "CO2_cost_EUR",
        "Demand_charge_cost_EUR",
        "Dump_cost_EUR",
    ]

    capex_total = 0.0
    opex_total = 0.0

    for key in capex_keys:
        val = objective.get(key, 0.0)
        try:
            capex_total += float(val)
        except (TypeError, ValueError):
            pass

    for key in opex_keys:
        val = objective.get(key, 0.0)
        try:
            opex_total += float(val)
        except (TypeError, ValueError):
            pass

    # Subtract revenue from OPEX
    revenue = objective.get("Grid_sell_revenue_EUR", 0.0)
    try:
        opex_total -= float(revenue)
    except (TypeError, ValueError):
        pass

    if capex_total < 1e-3 and opex_total < 1e-3:
        return []

    # Create two subplots: one for totals, one for breakdown
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN,
                                   constrained_layout=True)

    # Plot 1: CAPEX vs OPEX totals
    categories = ['CAPEX', 'OPEX']
    values = [capex_total, opex_total]
    colors = [PublicationConfig.COLORS_QUALITATIVE[0], PublicationConfig.COLORS_QUALITATIVE[1]]

    bars = ax1.bar(categories, values, color=colors, alpha=0.8, width=0.6)
    ax1.set_ylabel("Cost [EUR]")
    ax1.set_title("CAPEX vs OPEX", fontsize=11, fontweight='bold')
    ax1.grid(True, axis="y", alpha=0.3)

    # Add value labels
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:,.0f}', ha='center', va='bottom', fontsize=9)

    # Add percentage labels
    total = sum(values)
    if total > 0:
        for bar, val in zip(bars, values):
            pct = (val / total) * 100
            ax1.text(bar.get_x() + bar.get_width()/2., val/2,
                    f'{pct:.1f}%', ha='center', va='center',
                    fontsize=10, fontweight='bold', color='white')

    # Plot 2: Detailed CAPEX breakdown (if available)
    capex_hp = objective.get("Capex_heat_pumps_EUR", 0.0)
    capex_sto = objective.get("Capex_storage_EUR", 0.0)
    activation = objective.get("Activation_cost_EUR", 0.0)
    storage_install = objective.get("Storage_installation_cost_EUR", 0.0)

    capex_breakdown = []
    capex_labels = []

    if abs(float(capex_hp)) > 1e-3:
        capex_breakdown.append(float(capex_hp))
        capex_labels.append("Heat Pumps")
    if abs(float(capex_sto)) > 1e-3:
        capex_breakdown.append(float(capex_sto))
        capex_labels.append("Storage")
    if abs(float(activation)) > 1e-3:
        capex_breakdown.append(float(activation))
        capex_labels.append("Activation")
    if abs(float(storage_install)) > 1e-3:
        capex_breakdown.append(float(storage_install))
        capex_labels.append("Installation")

    if capex_breakdown:
        # Pie chart for CAPEX breakdown
        wedges, texts, autotexts = ax2.pie(
            capex_breakdown,
            labels=capex_labels,
            autopct='%1.1f%%',
            colors=PublicationConfig.COLORS_QUALITATIVE[:len(capex_breakdown)],
            startangle=90,
            textprops={'fontsize': 9}
        )
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        ax2.set_title("CAPEX Breakdown", fontsize=11, fontweight='bold')
    else:
        ax2.text(0.5, 0.5, "No CAPEX breakdown\navailable",
                ha='center', va='center', transform=ax2.transAxes,
                fontsize=10, color='gray')
        ax2.axis('off')

    return _save_figure(fig, outdir, "capex_opex_publication", dpi, formats)


def _electricity_cost_pie_publication(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate pie chart for detailed electricity cost breakdown."""
    objective = summary_sections.get("objective")
    if not isinstance(objective, Mapping):
        return []

    # Collect electricity cost components
    elec_components = []
    elec_labels = []

    cost_mapping = [
        ("Electricity_base_cost_EUR", "Spot Price"),
        ("Electricity_energy_fee_EUR", "Energy Fee"),
        ("Electricity_grid_fee_EUR", "Grid Fee\n(Netzentgelte)"),
        ("Demand_charge_cost_EUR", "Demand Charge\n(Leistungspreis)"),
    ]

    for key, label in cost_mapping:
        val = objective.get(key, 0.0)
        try:
            number = float(val)
            if abs(number) > 1e-3:
                elec_components.append(number)
                elec_labels.append(label)
        except (TypeError, ValueError):
            pass

    if not elec_components:
        return []

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_SINGLE_COLUMN, constrained_layout=True)

    # Create pie chart
    wedges, texts, autotexts = ax.pie(
        elec_components,
        labels=elec_labels,
        autopct=lambda pct: f'{pct:.1f}%' if pct > 5 else '',
        colors=PublicationConfig.COLORS_QUALITATIVE[:len(elec_components)],
        startangle=90,
        textprops={'fontsize': 8}
    )

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(9)

    ax.set_title("Electricity Cost Breakdown", fontsize=11, fontweight='bold')

    # Add total as text
    total = sum(elec_components)
    ax.text(0, -1.3, f'Total: {total:,.0f} EUR',
           ha='center', va='top', fontsize=10, fontweight='bold',
           transform=ax.transData)

    return _save_figure(fig, outdir, "electricity_cost_pie_publication", dpi, formats)


def _fuel_cost_breakdown_publication(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """Generate bar chart for fuel costs by type."""
    objective = summary_sections.get("objective")
    if not isinstance(objective, Mapping):
        return []

    # Collect fuel costs by type
    fuel_costs = []
    fuel_labels = []

    for key, value in objective.items():
        if key.startswith("Fuel_cost_") and key != "Fuel_cost_EUR" and key.endswith("_EUR"):
            try:
                number = float(value)
                if abs(number) > 1e-3:
                    fuel_type = key.replace("Fuel_cost_", "").replace("_EUR", "").title()
                    fuel_costs.append(number)
                    fuel_labels.append(fuel_type)
            except (TypeError, ValueError):
                pass

    if not fuel_costs:
        return []

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_SINGLE_COLUMN, constrained_layout=True)

    # Create bar chart
    x_pos = range(len(fuel_labels))
    bars = ax.bar(x_pos, fuel_costs,
                  color=PublicationConfig.COLORS_QUALITATIVE[:len(fuel_costs)],
                  alpha=0.8)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(fuel_labels, rotation=45, ha='right')
    ax.set_ylabel("Cost [EUR]")
    ax.set_title("Fuel Costs by Energy Carrier", fontsize=11, fontweight='bold')
    ax.grid(True, axis="y", alpha=0.3)

    # Add value labels on bars
    for bar, val in zip(bars, fuel_costs):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{val:,.0f}', ha='center', va='bottom', fontsize=9)

    # Add total as text
    total = sum(fuel_costs)
    ax.text(0.98, 0.98, f'Total: {total:,.0f} EUR',
           ha='right', va='top', fontsize=9, fontweight='bold',
           transform=ax.transAxes,
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    return _save_figure(fig, outdir, "fuel_cost_breakdown_publication", dpi, formats)


# ============================================================================
# MULTI-NETWORK PLOTTING FUNCTIONS
# ============================================================================

def _multi_network_temperature_publication(
    outdir: str,
    multi_network_results: Mapping[str, Mapping[str, object]],
    timestamps: Sequence[datetime] | Sequence[int],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """
    Generate temperature comparison plot for multiple networks.

    Shows supply and return temperatures for each network with
    different temperature levels (e.g., high-temp industrial vs low-temp residential).
    """
    if not HAVE_MATPLOTLIB:
        return []

    networks = multi_network_results.get('networks', {})
    if not networks:
        return []

    n_networks = len(networks)
    if n_networks == 0:
        return []

    fig, axes = plt.subplots(n_networks, 1,
                             figsize=(PublicationConfig.FIGSIZE_DOUBLE_COLUMN[0],
                                     2.5 * n_networks),
                             constrained_layout=True,
                             sharex=True)

    if n_networks == 1:
        axes = [axes]

    colors = PublicationConfig.COLORS_QUALITATIVE

    for idx, (net_id, net_data) in enumerate(networks.items()):
        ax = axes[idx]

        # Get temperature data
        T_supply = net_data.get('supply_temperatures_c', [])
        T_return = net_data.get('return_temperatures_c', [])

        if not T_supply and not T_return:
            # Try alternative keys
            T_supply = net_data.get('avg_supply_temp_c', [])
            T_return = net_data.get('avg_return_temp_c', [])

        x_data = timestamps if len(timestamps) == len(T_supply) else range(len(T_supply))

        if T_supply:
            ax.plot(x_data, T_supply, label='Supply', color=colors[0], linewidth=1.5)
        if T_return:
            ax.plot(x_data, T_return, label='Return', color=colors[1], linewidth=1.5)

        # Add network info
        temp_level = net_data.get('temperature_level', 'unknown')
        ax.set_ylabel(f'Temperature [°C]')
        ax.set_title(f'{net_id} ({temp_level})', fontsize=10, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

        # Set y-axis limits based on temperature level
        if temp_level == 'high':
            ax.set_ylim(40, 130)
        elif temp_level == 'low':
            ax.set_ylim(20, 80)

    axes[-1].set_xlabel('Time')
    _configure_time_axis(axes[-1], timestamps)

    fig.suptitle('Multi-Network Temperature Profiles', fontsize=12, fontweight='bold')

    return _save_figure(fig, outdir, "multi_network_temperatures", dpi, formats)


def _heat_exchanger_operation_publication(
    outdir: str,
    multi_network_results: Mapping[str, Mapping[str, object]],
    timestamps: Sequence[datetime] | Sequence[int],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """
    Generate heat exchanger operation plot showing heat transfer over time.
    """
    if not HAVE_MATPLOTLIB:
        return []

    hx_data = multi_network_results.get('heat_exchangers', {})
    if not hx_data:
        return []

    n_hx = len(hx_data)
    fig, axes = plt.subplots(n_hx, 1,
                             figsize=(PublicationConfig.FIGSIZE_DOUBLE_COLUMN[0],
                                     2.5 * max(n_hx, 1)),
                             constrained_layout=True,
                             sharex=True)

    if n_hx == 1:
        axes = [axes]

    colors = PublicationConfig.COLORS_QUALITATIVE

    for idx, (hx_id, hx_result) in enumerate(hx_data.items()):
        ax = axes[idx]

        Q_transfer = hx_result.get('Q_transfer_mw', [])
        T_prim_in = hx_result.get('T_prim_in_c', [])
        T_sec_out = hx_result.get('T_sec_out_c', [])

        x_data = timestamps if len(timestamps) == len(Q_transfer) else range(len(Q_transfer))

        # Primary axis: Heat transfer
        ax.fill_between(x_data, Q_transfer, alpha=0.4, color=colors[0], label='Heat Transfer')
        ax.plot(x_data, Q_transfer, color=colors[0], linewidth=1.5)
        ax.set_ylabel('Heat Transfer [MW]', color=colors[0])
        ax.tick_params(axis='y', labelcolor=colors[0])

        # Secondary axis: Temperatures
        ax2 = ax.twinx()
        if T_prim_in:
            ax2.plot(x_data, T_prim_in, '--', color=colors[1], linewidth=1.0, label='T_prim_in')
        if T_sec_out:
            ax2.plot(x_data, T_sec_out, ':', color=colors[2], linewidth=1.0, label='T_sec_out')
        ax2.set_ylabel('Temperature [°C]', color=colors[1])
        ax2.tick_params(axis='y', labelcolor=colors[1])

        # Title with summary
        total_mwh = hx_result.get('total_heat_transferred_mwh', 0)
        ax.set_title(f'{hx_id} (Total: {total_mwh:.1f} MWh)', fontsize=10, fontweight='bold')
        ax.grid(True, alpha=0.3)

        # Combined legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=8)

    axes[-1].set_xlabel('Time')
    _configure_time_axis(axes[-1], timestamps)

    fig.suptitle('Heat Exchanger Operation', fontsize=12, fontweight='bold')

    return _save_figure(fig, outdir, "heat_exchanger_operation", dpi, formats)


def _multi_network_sankey_publication(
    outdir: str,
    multi_network_results: Mapping[str, Mapping[str, object]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """
    Generate Sankey diagram showing energy flows between networks.

    Shows heat sources, networks, heat exchangers, and sinks.
    """
    if not HAVE_MATPLOTLIB:
        return []

    try:
        from matplotlib.sankey import Sankey
    except ImportError:
        return []

    networks = multi_network_results.get('networks', {})
    hx_data = multi_network_results.get('heat_exchangers', {})
    summary = multi_network_results.get('summary', {})

    if not networks:
        return []

    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN,
                           constrained_layout=True)

    # Collect energy flows
    flows = []
    labels = []

    # Network heat demands
    total_demand = 0
    for net_id, net_data in networks.items():
        demand = net_data.get('total_heat_demand_mwh', 0)
        if demand == 0:
            demand = net_data.get('heat_delivered_mwh', 100)  # Default
        total_demand += demand
        flows.append(-demand)  # Negative = outflow
        labels.append(f'{net_id}\n({demand:.0f} MWh)')

    # Heat losses
    total_loss = summary.get('total_network_heat_loss_mwh', 0)
    if total_loss > 0:
        flows.append(-total_loss)
        labels.append(f'Losses\n({total_loss:.0f} MWh)')

    # Heat input (to balance)
    heat_input = total_demand + total_loss
    flows.insert(0, heat_input)
    labels.insert(0, f'Heat Input\n({heat_input:.0f} MWh)')

    # HX transfer (internal, doesn't affect balance but shown)
    hx_total = summary.get('total_hx_heat_transferred_mwh', 0)

    # Create simple bar representation instead of Sankey if too complex
    fig, ax = plt.subplots(figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN,
                           constrained_layout=True)

    categories = ['Heat Input'] + list(networks.keys()) + ['Losses', 'HX Transfer']
    values = [heat_input]

    for net_id, net_data in networks.items():
        demand = net_data.get('total_heat_demand_mwh', net_data.get('heat_delivered_mwh', 50))
        values.append(demand)

    values.append(total_loss)
    values.append(hx_total)

    colors = ['#228833'] + [PublicationConfig.COLORS_QUALITATIVE[i % len(PublicationConfig.COLORS_QUALITATIVE)]
                           for i in range(len(networks))] + ['#EE6677', '#CCBB44']

    bars = ax.barh(categories, values, color=colors, alpha=0.8)

    ax.set_xlabel('Energy [MWh]')
    ax.set_title('Multi-Network Energy Balance', fontsize=12, fontweight='bold')
    ax.grid(True, axis='x', alpha=0.3)

    # Add value labels
    for bar, val in zip(bars, values):
        width = bar.get_width()
        ax.text(width + max(values) * 0.02, bar.get_y() + bar.get_height()/2,
               f'{val:.0f}', ha='left', va='center', fontsize=9)

    return _save_figure(fig, outdir, "multi_network_energy_balance", dpi, formats)


def _network_comparison_publication(
    outdir: str,
    multi_network_results: Mapping[str, Mapping[str, object]],
    dpi: int,
    formats: Sequence[str],
) -> list[str]:
    """
    Generate comparison bar chart for multiple networks.

    Compares key metrics: heat delivered, losses, efficiency.
    """
    if not HAVE_MATPLOTLIB:
        return []

    networks = multi_network_results.get('networks', {})
    if not networks or len(networks) < 2:
        return []

    fig, axes = plt.subplots(1, 3, figsize=PublicationConfig.FIGSIZE_DOUBLE_COLUMN,
                             constrained_layout=True)

    net_ids = list(networks.keys())
    x_pos = range(len(net_ids))
    colors = PublicationConfig.COLORS_QUALITATIVE[:len(net_ids)]

    # Metric 1: Heat Delivered
    heat_delivered = [networks[nid].get('total_heat_delivered_mwh',
                                        networks[nid].get('heat_delivered_mwh', 0))
                     for nid in net_ids]
    axes[0].bar(x_pos, heat_delivered, color=colors, alpha=0.8)
    axes[0].set_xticks(x_pos)
    axes[0].set_xticklabels(net_ids, rotation=45, ha='right')
    axes[0].set_ylabel('Energy [MWh]')
    axes[0].set_title('Heat Delivered', fontsize=10, fontweight='bold')
    axes[0].grid(True, axis='y', alpha=0.3)

    # Metric 2: Heat Losses
    heat_losses = [networks[nid].get('total_network_heat_loss_mwh',
                                     networks[nid].get('heat_loss_mwh', 0))
                  for nid in net_ids]
    axes[1].bar(x_pos, heat_losses, color=colors, alpha=0.8)
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels(net_ids, rotation=45, ha='right')
    axes[1].set_ylabel('Energy [MWh]')
    axes[1].set_title('Heat Losses', fontsize=10, fontweight='bold')
    axes[1].grid(True, axis='y', alpha=0.3)

    # Metric 3: Network Efficiency
    efficiencies = []
    for nid in net_ids:
        delivered = networks[nid].get('total_heat_delivered_mwh', 1)
        loss = networks[nid].get('total_network_heat_loss_mwh', 0)
        if delivered > 0:
            eff = (delivered - loss) / delivered * 100
        else:
            eff = 100
        efficiencies.append(eff)

    axes[2].bar(x_pos, efficiencies, color=colors, alpha=0.8)
    axes[2].set_xticks(x_pos)
    axes[2].set_xticklabels(net_ids, rotation=45, ha='right')
    axes[2].set_ylabel('Efficiency [%]')
    axes[2].set_title('Network Efficiency', fontsize=10, fontweight='bold')
    axes[2].set_ylim(0, 105)
    axes[2].grid(True, axis='y', alpha=0.3)

    fig.suptitle('Multi-Network Comparison', fontsize=12, fontweight='bold')

    return _save_figure(fig, outdir, "multi_network_comparison", dpi, formats)


def export_multi_network_plots(
    outdir: str,
    multi_network_results: Mapping[str, Mapping[str, object]],
    timestamps: Sequence[datetime] | Sequence[int] | None = None,
    dpi: int = PublicationConfig.DPI_PRINT,
    formats: Sequence[str] = ("png", "pdf"),
) -> list[str]:
    """
    Export all multi-network publication plots.

    Args:
        outdir: Output directory for plots
        multi_network_results: Results from MultiNetworkManager.get_results()
        timestamps: Time axis data
        dpi: Output resolution
        formats: Output formats (png, pdf, eps)

    Returns:
        List of created file paths
    """
    if not HAVE_MATPLOTLIB:
        return []

    PublicationConfig.apply_style()
    os.makedirs(outdir, exist_ok=True)

    all_files = []

    if timestamps is None:
        # Generate default timestamps
        networks = multi_network_results.get('networks', {})
        if networks:
            first_net = list(networks.values())[0]
            n_steps = len(first_net.get('supply_temperatures_c', range(24)))
            timestamps = list(range(n_steps))
        else:
            timestamps = list(range(24))

    # Generate all plots
    all_files.extend(_multi_network_temperature_publication(
        outdir, multi_network_results, timestamps, dpi, formats))

    all_files.extend(_heat_exchanger_operation_publication(
        outdir, multi_network_results, timestamps, dpi, formats))

    all_files.extend(_multi_network_sankey_publication(
        outdir, multi_network_results, dpi, formats))

    all_files.extend(_network_comparison_publication(
        outdir, multi_network_results, dpi, formats))

    return all_files

