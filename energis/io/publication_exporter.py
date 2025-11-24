"""
Publication export utilities for scientific papers.

This module provides export functions for:
- LaTeX tables (KPIs, cost breakdown, design decisions)
- Formatted CSV files with statistical summaries
- JSON exports with complete metadata
- Publication-ready summary statistics
"""

from __future__ import annotations

import os
import json
import csv
from typing import Mapping, Sequence, Any
from datetime import datetime
import numpy as np

__all__ = [
    "export_latex_tables",
    "export_kpi_summary",
    "export_publication_bundle",
    "format_number",
]


# ============================================================================
# Formatting Utilities
# ============================================================================

def format_number(value: float, precision: int = 2, use_si: bool = False) -> str:
    """
    Format number for publication (with thousand separators).

    Parameters
    ----------
    value : float
        Number to format
    precision : int, default=2
        Decimal places
    use_si : bool, default=False
        Use SI prefixes (k, M, G)

    Returns
    -------
    str
        Formatted number string
    """
    if abs(value) < 1e-9:
        return "0"

    if use_si:
        abs_val = abs(value)
        sign = "-" if value < 0 else ""

        if abs_val >= 1e9:
            return f"{sign}{abs_val/1e9:.{precision}f}\\,G"
        elif abs_val >= 1e6:
            return f"{sign}{abs_val/1e6:.{precision}f}\\,M"
        elif abs_val >= 1e3:
            return f"{sign}{abs_val/1e3:.{precision}f}\\,k"
        else:
            return f"{sign}{abs_val:.{precision}f}"
    else:
        # Use comma as thousand separator for readability
        return f"{value:,.{precision}f}"


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters."""
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
    }

    result = text
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)

    return result


# ============================================================================
# LaTeX Table Export
# ============================================================================

def export_latex_tables(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    *,
    table_style: str = "booktabs",
) -> dict[str, str]:
    """
    Export publication-ready LaTeX tables.

    Parameters
    ----------
    outdir : str
        Output directory
    summary_sections : Mapping[str, Mapping[str, object]]
        Summary data sections
    table_style : str, default="booktabs"
        LaTeX table style: "booktabs", "simple", "ieee", or "applied_energies"

    Returns
    -------
    dict[str, str]
        Dictionary mapping table name to file path
    """
    os.makedirs(outdir, exist_ok=True)
    generated = {}

    # Generate KPI summary table
    kpi_path = _export_kpi_latex_table(outdir, summary_sections, table_style)
    if kpi_path:
        generated["kpi_summary"] = kpi_path

    # Generate cost breakdown table
    cost_path = _export_cost_latex_table(outdir, summary_sections, table_style)
    if cost_path:
        generated["cost_breakdown"] = cost_path

    # Generate detailed cost breakdown table
    detailed_cost_path = _export_detailed_cost_latex_table(outdir, summary_sections, table_style)
    if detailed_cost_path:
        generated["cost_breakdown_detailed"] = detailed_cost_path

    # Generate design decisions table
    design_path = _export_design_latex_table(outdir, summary_sections, table_style)
    if design_path:
        generated["design_decisions"] = design_path

    return generated


def _get_table_preamble(table_style: str) -> str:
    """Get LaTeX table preamble based on style."""
    if table_style == "booktabs":
        return "\\usepackage{booktabs}\n\\usepackage{siunitx}\n"
    elif table_style == "applied_energies":
        # Applied Energies: horizontal lines only, clean style
        return "\\usepackage{siunitx}\n% Applied Energy style: horizontal lines only\n"
    elif table_style == "ieee":
        return "% IEEE style tables\n"
    else:
        return "% Simple table style\n"


def _get_table_rules(table_style: str) -> tuple[str, str, str]:
    """Get LaTeX table rules (top, mid, bottom) based on style."""
    if table_style == "booktabs":
        return "\\toprule", "\\midrule", "\\bottomrule"
    elif table_style == "applied_energies":
        # Applied Energies uses horizontal lines only
        return "\\hline", "\\hline", "\\hline"
    else:
        return "\\hline", "\\hline", "\\hline"


def _export_kpi_latex_table(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    table_style: str,
) -> str | None:
    """Export KPI summary as LaTeX table."""
    objective = summary_sections.get("objective")
    grid = summary_sections.get("grid")

    if not objective:
        return None

    top_rule, mid_rule, bottom_rule = _get_table_rules(table_style)

    # Collect KPIs
    kpis = []

    # Total cost
    total_cost = objective.get("OBJ_value_EUR")
    if total_cost:
        kpis.append(("Total System Cost", format_number(float(total_cost), 0), "EUR"))

    # Energy costs (using new field names)
    energy_cost = objective.get("Grid_energy_cost_EUR")
    if energy_cost and abs(float(energy_cost)) > 1e-3:
        kpis.append(("Energy Cost", format_number(float(energy_cost), 0), "EUR"))

    # Investment costs (using new field names)
    invest_cost = objective.get("Capex_cost_EUR")
    if invest_cost and abs(float(invest_cost)) > 1e-3:
        kpis.append(("Investment Cost", format_number(float(invest_cost), 0), "EUR"))

    # CO2 emissions (using correct field names)
    if grid:
        co2_emissions = grid.get("Total_CO2_emissions_t")
        if co2_emissions and abs(float(co2_emissions)) > 1e-3:
            kpis.append(("CO$_2$ Emissions", format_number(float(co2_emissions), 1), "t"))

        # Grid import (using correct field names)
        grid_import = grid.get("Energy_from_grid_MWh")
        if grid_import and abs(float(grid_import)) > 1e-3:
            kpis.append(("Grid Import", format_number(float(grid_import), 1), "MWh"))

    # Peak demand (from objective section)
    peak_demand = objective.get("P_buy_peak_MW")
    if peak_demand and abs(float(peak_demand)) > 1e-3:
        kpis.append(("Peak Demand", format_number(float(peak_demand), 2), "MW"))

    if not kpis:
        return None

    # Generate LaTeX table
    filepath = os.path.join(outdir, "kpi_summary.tex")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("% KPI Summary Table for Publication\n")
        f.write("% Compile with: pdflatex\n")
        f.write(f"{_get_table_preamble(table_style)}\n")
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{Key Performance Indicators of the Optimized Heat System}\n")
        f.write("\\label{tab:kpi_summary}\n")

        if table_style == "booktabs":
            f.write("\\begin{tabular}{lS[table-format=8.2]l}\n")
        else:
            f.write("\\begin{tabular}{lrl}\n")

        f.write(f"{top_rule}\n")
        f.write("Metric & {Value} & {Unit} \\\\\n")
        f.write(f"{mid_rule}\n")

        for metric, value, unit in kpis:
            if table_style == "booktabs":
                # Remove commas for siunitx
                value_clean = value.replace(",", "")
                f.write(f"{metric} & {value_clean} & {unit} \\\\\n")
            else:
                f.write(f"{metric} & {value} & {unit} \\\\\n")

        f.write(f"{bottom_rule}\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    return filepath


def _export_cost_latex_table(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    table_style: str,
) -> str | None:
    """Export cost breakdown as LaTeX table."""
    objective = summary_sections.get("objective")
    if not objective:
        return None

    top_rule, mid_rule, bottom_rule = _get_table_rules(table_style)

    # Collect cost components (using new field names)
    costs = []
    cost_keys = [
        ("Grid_energy_cost_EUR", "Electricity Cost"),
        ("Fuel_cost_EUR", "Fuel Cost"),
        ("Capex_cost_EUR", "Investment Cost"),
        ("Storage_installation_cost_EUR", "Storage Installation"),
        ("Activation_cost_EUR", "Activation Cost"),
        ("CO2_cost_EUR", "CO$_2$ Cost"),
        ("Demand_charge_cost_EUR", "Demand Charge"),
        ("Dump_cost_EUR", "Heat Dump Cost"),
    ]

    total = 0.0
    for key, label in cost_keys:
        value = objective.get(key)
        if value and abs(float(value)) > 1e-3:
            val_float = float(value)
            costs.append((label, val_float))
            total += val_float

    # Also subtract revenue if present
    revenue = objective.get("Grid_sell_revenue_EUR", 0.0)
    if revenue and abs(float(revenue)) > 1e-3:
        costs.append(("Grid Revenue (negative)", -float(revenue)))
        total -= float(revenue)

    if not costs:
        return None

    # Add total
    costs.append(("\\textbf{Total}", total))

    # Generate LaTeX table
    filepath = os.path.join(outdir, "cost_breakdown.tex")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("% Cost Breakdown Table for Publication\n")
        f.write(f"{_get_table_preamble(table_style)}\n")
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{System Cost Breakdown}\n")
        f.write("\\label{tab:cost_breakdown}\n")

        if table_style == "booktabs":
            f.write("\\begin{tabular}{lS[table-format=10.0]S[table-format=3.1]}\n")
        else:
            f.write("\\begin{tabular}{lrr}\n")

        f.write(f"{top_rule}\n")
        f.write("Cost Component & {Value [EUR]} & {Share [\\%]} \\\\\n")
        f.write(f"{mid_rule}\n")

        for label, value in costs:
            share = (value / total * 100) if total > 0 and label != "\\textbf{Total}" else 100.0

            if label == "\\textbf{Total}":
                if table_style != "booktabs":
                    f.write(f"{mid_rule}\n")

                if table_style == "booktabs":
                    value_str = format_number(value, 0).replace(",", "")
                    share_str = format_number(share, 1).replace(",", "")
                else:
                    value_str = format_number(value, 0)
                    share_str = format_number(share, 1)

                f.write(f"{label} & {value_str} & {share_str} \\\\\n")
            else:
                if table_style == "booktabs":
                    value_str = format_number(value, 0).replace(",", "")
                    share_str = format_number(share, 1).replace(",", "")
                else:
                    value_str = format_number(value, 0)
                    share_str = format_number(share, 1)

                f.write(f"{label} & {value_str} & {share_str} \\\\\n")

        f.write(f"{bottom_rule}\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    return filepath


def _export_detailed_cost_latex_table(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    table_style: str,
) -> str | None:
    """Export detailed cost breakdown with subcategories as LaTeX table."""
    objective = summary_sections.get("objective")
    if not objective:
        return None

    top_rule, mid_rule, bottom_rule = _get_table_rules(table_style)

    # Collect detailed cost components
    cost_items = []

    # Electricity costs (detailed)
    elec_base = objective.get("Electricity_base_cost_EUR", 0.0)
    elec_fee = objective.get("Electricity_energy_fee_EUR", 0.0)
    elec_grid = objective.get("Electricity_grid_fee_EUR", 0.0)
    demand_charge = objective.get("Demand_charge_cost_EUR", 0.0)

    if abs(float(elec_base)) > 1e-3:
        cost_items.append(("\\quad Spot Price", float(elec_base)))
    if abs(float(elec_fee)) > 1e-3:
        cost_items.append(("\\quad Energy Fee", float(elec_fee)))
    if abs(float(elec_grid)) > 1e-3:
        cost_items.append(("\\quad Grid Fee", float(elec_grid)))
    if abs(float(demand_charge)) > 1e-3:
        cost_items.append(("\\quad Demand Charge", float(demand_charge)))

    # Fuel costs (by type)
    fuel_total = objective.get("Fuel_cost_EUR", 0.0)
    if abs(float(fuel_total)) > 1e-3:
        cost_items.append(("\\textbf{Fuel Costs}", None))  # Category header
        # Check for fuel types
        for key, value in objective.items():
            if key.startswith("Fuel_cost_") and key != "Fuel_cost_EUR" and key.endswith("_EUR"):
                fuel_type = key.replace("Fuel_cost_", "").replace("_EUR", "").title()
                if abs(float(value)) > 1e-3:
                    cost_items.append((f"\\quad {fuel_type}", float(value)))

    # Investment costs (detailed)
    capex_hp = objective.get("Capex_heat_pumps_EUR", 0.0)
    capex_sto = objective.get("Capex_storage_EUR", 0.0)
    activation = objective.get("Activation_cost_EUR", 0.0)
    storage_install = objective.get("Storage_installation_cost_EUR", 0.0)

    if abs(float(capex_hp)) > 1e-3 or abs(float(capex_sto)) > 1e-3:
        cost_items.append(("\\textbf{Investment Costs}", None))  # Category header
        if abs(float(capex_hp)) > 1e-3:
            cost_items.append(("\\quad Heat Pumps CAPEX", float(capex_hp)))
        if abs(float(capex_sto)) > 1e-3:
            cost_items.append(("\\quad Storage CAPEX", float(capex_sto)))
        if abs(float(activation)) > 1e-3:
            cost_items.append(("\\quad Activation", float(activation)))
        if abs(float(storage_install)) > 1e-3:
            cost_items.append(("\\quad Storage Installation", float(storage_install)))

    # Other costs
    co2_cost = objective.get("CO2_cost_EUR", 0.0)
    dump_cost = objective.get("Dump_cost_EUR", 0.0)

    if abs(float(co2_cost)) > 1e-3:
        cost_items.append(("CO$_2$ Cost", float(co2_cost)))
    if abs(float(dump_cost)) > 1e-3:
        cost_items.append(("Heat Dump Cost", float(dump_cost)))

    # Revenue
    revenue = objective.get("Grid_sell_revenue_EUR", 0.0)
    if abs(float(revenue)) > 1e-3:
        cost_items.append(("Grid Revenue", -float(revenue)))

    if not cost_items:
        return None

    # Calculate total
    total = sum(val for _, val in cost_items if val is not None)

    # Generate LaTeX table
    filepath = os.path.join(outdir, "cost_breakdown_detailed.tex")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("% Detailed Cost Breakdown Table for Publication\n")
        f.write("% Compile with: pdflatex\n")
        f.write(f"{_get_table_preamble(table_style)}\n")
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{Detailed System Cost Breakdown}\n")
        f.write("\\label{tab:cost_breakdown_detailed}\n")

        if table_style == "booktabs":
            f.write("\\begin{tabular}{lS[table-format=10.0]S[table-format=3.1]}\n")
        else:
            f.write("\\begin{tabular}{lrr}\n")

        f.write(f"{top_rule}\n")
        f.write("Cost Component & {Value [EUR]} & {Share [\\%]} \\\\\n")
        f.write(f"{mid_rule}\n")

        for label, value in cost_items:
            if value is None:
                # Category header
                f.write(f"{label} & & \\\\\n")
            else:
                share = (value / total * 100) if total > 0 else 0.0

                if table_style == "booktabs":
                    value_str = format_number(value, 0).replace(",", "")
                    share_str = format_number(share, 1).replace(",", "")
                else:
                    value_str = format_number(value, 0)
                    share_str = format_number(share, 1)

                f.write(f"{label} & {value_str} & {share_str} \\\\\n")

        # Add total
        f.write(f"{mid_rule}\n")
        if table_style == "booktabs":
            total_str = format_number(total, 0).replace(",", "")
        else:
            total_str = format_number(total, 0)
        f.write(f"\\textbf{{Total}} & {total_str} & 100.0 \\\\\n")

        f.write(f"{bottom_rule}\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    return filepath


def _export_design_latex_table(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    table_style: str,
) -> str | None:
    """Export design decisions as LaTeX table."""
    # Collect heat pump capacities
    heat_pumps = []

    for hp in ["HP1", "HP2", "HP3", "HP4"]:
        key = f"heat_pump_{hp}"
        if key in summary_sections:
            hp_data = summary_sections[key]
            capacity = hp_data.get("capacity_MW")
            build = hp_data.get("build_binary")

            if capacity and build:
                heat_pumps.append((hp.replace("_", " "), float(capacity), int(build)))

    # Get storage info
    storage_capacity = None
    storage_power = None

    if "storage_TES" in summary_sections:
        storage_data = summary_sections["storage_TES"]
        storage_capacity = storage_data.get("capacity_MWh")
        storage_power = storage_data.get("power_MW")

    if not heat_pumps and not storage_capacity:
        return None

    top_rule, mid_rule, bottom_rule = _get_table_rules(table_style)

    # Generate LaTeX table
    filepath = os.path.join(outdir, "design_decisions.tex")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("% Design Decisions Table for Publication\n")
        f.write(f"{_get_table_preamble(table_style)}\n")
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{Optimal System Design}\n")
        f.write("\\label{tab:design_decisions}\n")

        if table_style == "booktabs":
            f.write("\\begin{tabular}{lS[table-format=3.2]c}\n")
        else:
            f.write("\\begin{tabular}{lrc}\n")

        f.write(f"{top_rule}\n")
        f.write("Component & {Capacity} & {Built} \\\\\n")
        f.write(f"{mid_rule}\n")

        # Heat pumps
        if heat_pumps:
            for hp_name, capacity, build in heat_pumps:
                build_str = "Yes" if build == 1 else "No"
                if table_style == "booktabs":
                    cap_str = format_number(capacity, 2).replace(",", "")
                else:
                    cap_str = format_number(capacity, 2)

                f.write(f"{hp_name} [MW] & {cap_str} & {build_str} \\\\\n")

        # Storage
        if storage_capacity and storage_power:
            if heat_pumps:
                f.write(f"{mid_rule}\n")

            if table_style == "booktabs":
                cap_str = format_number(float(storage_capacity), 2).replace(",", "")
                pow_str = format_number(float(storage_power), 2).replace(",", "")
            else:
                cap_str = format_number(float(storage_capacity), 2)
                pow_str = format_number(float(storage_power), 2)

            f.write(f"Storage Capacity [MWh] & {cap_str} & Yes \\\\\n")
            f.write(f"Storage Power [MW] & {pow_str} & Yes \\\\\n")

        f.write(f"{bottom_rule}\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    return filepath


# ============================================================================
# KPI Summary Export
# ============================================================================

def export_kpi_summary(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    table: Any = None,
    series: Mapping[str, Sequence[float]] | None = None,
) -> str:
    """
    Export comprehensive KPI summary as JSON and CSV.

    Parameters
    ----------
    outdir : str
        Output directory
    summary_sections : Mapping[str, Mapping[str, object]]
        Summary data from optimization
    table : TimeSeriesTable, optional
        Input time series
    series : Mapping[str, Sequence[float]], optional
        Result time series

    Returns
    -------
    str
        Path to KPI summary JSON file
    """
    os.makedirs(outdir, exist_ok=True)

    kpis = {}

    # Economic metrics
    objective = summary_sections.get("objective")
    if objective:
        kpis["economic"] = {
            "total_cost_EUR": _safe_float(objective.get("OBJ_value_EUR")),
            "energy_cost_EUR": _safe_float(objective.get("Energy_EUR")),
            "fuel_cost_EUR": _safe_float(objective.get("Fuel_EUR")),
            "investment_cost_EUR": _safe_float(objective.get("Invest_EUR")),
            "installation_cost_EUR": _safe_float(objective.get("Install_EUR")),
            "co2_cost_EUR": _safe_float(objective.get("CO2_EUR")),
            "demand_charge_EUR": _safe_float(objective.get("Demand_charge_EUR")),
        }

    # Environmental metrics
    grid = summary_sections.get("grid")
    if grid:
        kpis["environmental"] = {
            "total_co2_emissions_t": _safe_float(grid.get("total_co2_emissions_t")),
            "grid_co2_emissions_t": _safe_float(grid.get("grid_co2_t")),
            "fuel_co2_emissions_t": _safe_float(grid.get("fuel_co2_t")),
        }

    # Grid metrics
    if grid:
        kpis["grid"] = {
            "total_import_MWh": _safe_float(grid.get("total_import_MWh")),
            "total_export_MWh": _safe_float(grid.get("total_export_MWh")),
            "peak_import_MW": _safe_float(grid.get("peak_import_MW")),
            "peak_export_MW": _safe_float(grid.get("peak_export_MW")),
            "net_import_MWh": _safe_float(grid.get("net_import_MWh")),
        }

    # Heat pump metrics
    hp_metrics = {}
    for hp in ["HP1", "HP2", "HP3", "HP4"]:
        key = f"heat_pump_{hp}"
        if key in summary_sections:
            hp_data = summary_sections[key]
            hp_metrics[hp] = {
                "capacity_MW": _safe_float(hp_data.get("capacity_MW")),
                "build_binary": _safe_int(hp_data.get("build_binary")),
                "total_heat_output_MWh": _safe_float(hp_data.get("total_heat_output_MWh")),
                "total_power_consumed_MWh": _safe_float(hp_data.get("total_power_consumed_MWh")),
                "average_cop": _calculate_average_cop(hp_data),
            }

    if hp_metrics:
        kpis["heat_pumps"] = hp_metrics

    # Storage metrics
    if "storage_TES" in summary_sections:
        storage_data = summary_sections["storage_TES"]
        kpis["storage"] = {
            "capacity_MWh": _safe_float(storage_data.get("capacity_MWh")),
            "power_MW": _safe_float(storage_data.get("power_MW")),
            "build_binary": _safe_int(storage_data.get("build_binary")),
            "total_charged_MWh": _safe_float(storage_data.get("total_charged_MWh")),
            "total_discharged_MWh": _safe_float(storage_data.get("total_discharged_MWh")),
            "round_trip_efficiency": _calculate_storage_efficiency(storage_data),
        }

    # System-level metrics
    if series and table:
        kpis["system"] = _calculate_system_metrics(table, series)

    # Add metadata
    kpis["metadata"] = {
        "export_timestamp": datetime.now().isoformat(),
        "framework_version": "2.0",
    }

    # Export as JSON
    json_path = os.path.join(outdir, "kpi_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(kpis, f, indent=2, ensure_ascii=False)

    # Export as flattened CSV
    csv_path = os.path.join(outdir, "kpi_summary.csv")
    _export_kpi_csv(csv_path, kpis)

    return json_path


def _export_kpi_csv(filepath: str, kpis: dict) -> None:
    """Export KPIs as flat CSV file."""
    rows = []

    def flatten_dict(d: dict, prefix: str = ""):
        for key, value in d.items():
            new_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                flatten_dict(value, new_key)
            else:
                rows.append([new_key, value])

    flatten_dict(kpis)

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Metric", "Value"])
        writer.writerows(rows)


def _safe_float(value: Any) -> float | None:
    """Safely convert to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    """Safely convert to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _calculate_average_cop(hp_data: Mapping[str, object]) -> float | None:
    """Calculate average COP for heat pump."""
    heat_output = _safe_float(hp_data.get("total_heat_output_MWh"))
    power_consumed = _safe_float(hp_data.get("total_power_consumed_MWh"))

    if heat_output and power_consumed and power_consumed > 1e-6:
        return heat_output / power_consumed

    return None


def _calculate_storage_efficiency(storage_data: Mapping[str, object]) -> float | None:
    """Calculate round-trip efficiency of storage."""
    charged = _safe_float(storage_data.get("total_charged_MWh"))
    discharged = _safe_float(storage_data.get("total_discharged_MWh"))

    if charged and discharged and charged > 1e-6:
        return discharged / charged

    return None


def _calculate_system_metrics(table: Any, series: Mapping[str, Sequence[float]]) -> dict:
    """Calculate system-level performance metrics."""
    metrics = {}

    # Total heat demand
    demand = table.data.get("waermebedarf_MWth")
    if demand:
        metrics["total_heat_demand_MWh"] = float(np.sum(demand))
        metrics["peak_heat_demand_MW"] = float(np.max(demand))
        metrics["average_heat_demand_MW"] = float(np.mean(demand))

    # Renewable share (if available)
    # This would need to be calculated based on which sources are renewable

    return metrics


# ============================================================================
# Publication Bundle Export
# ============================================================================

def export_publication_bundle(
    outdir: str,
    summary_sections: Mapping[str, Mapping[str, object]],
    table: Any = None,
    series: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    """
    Export complete publication bundle with all tables and summaries.

    Parameters
    ----------
    outdir : str
        Output directory
    summary_sections : Mapping[str, Mapping[str, object]]
        Summary data
    table : TimeSeriesTable, optional
        Input time series
    series : Mapping[str, Sequence[float]], optional
        Result time series

    Returns
    -------
    dict[str, Any]
        Dictionary with paths to all generated files
    """
    os.makedirs(outdir, exist_ok=True)

    bundle = {}

    # Export LaTeX tables
    latex_dir = os.path.join(outdir, "latex")
    latex_tables = export_latex_tables(latex_dir, summary_sections, table_style="booktabs")
    bundle["latex_tables"] = latex_tables

    # Export KPI summary
    kpi_path = export_kpi_summary(outdir, summary_sections, table, series)
    bundle["kpi_summary_json"] = kpi_path

    # Create README
    readme_path = os.path.join(outdir, "README_publication.md")
    _create_publication_readme(readme_path, bundle)
    bundle["readme"] = readme_path

    return bundle


def _create_publication_readme(filepath: str, bundle: dict) -> None:
    """Create README for publication exports."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Publication Export Bundle\n\n")
        f.write("This directory contains publication-ready outputs from the heat planning optimization.\n\n")

        f.write("## Contents\n\n")

        f.write("### LaTeX Tables\n")
        f.write("Ready-to-use LaTeX tables for insertion into your paper:\n\n")
        latex_tables = bundle.get("latex_tables", {})
        for table_name, table_path in latex_tables.items():
            f.write(f"- `{os.path.basename(table_path)}` - {table_name.replace('_', ' ').title()}\n")

        f.write("\n### Data Files\n\n")
        f.write(f"- `kpi_summary.json` - Complete KPI metrics in JSON format\n")
        f.write(f"- `kpi_summary.csv` - Flattened KPI metrics for spreadsheet analysis\n")

        f.write("\n### Plots\n")
        f.write("See the main exports directory for publication-quality figures in PNG, PDF, and EPS formats.\n\n")

        f.write("## Usage\n\n")
        f.write("### Including LaTeX Tables\n\n")
        f.write("To include a table in your paper:\n\n")
        f.write("```latex\n")
        f.write("\\input{latex/kpi_summary.tex}\n")
        f.write("```\n\n")

        f.write("Make sure to include the required packages in your preamble:\n\n")
        f.write("```latex\n")
        f.write("\\usepackage{booktabs}\n")
        f.write("\\usepackage{siunitx}\n")
        f.write("```\n\n")

        f.write("## Citation\n\n")
        f.write("If you use these results in your publication, please cite:\n\n")
        f.write("[Your paper citation here]\n")
