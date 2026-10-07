"""
Multi-network export functions.

Extracted from UnifiedExporter to give multi-network logic its own module.
All functions are standalone (no class state) and receive their data as
explicit parameters.

Public API:
  export_multi_network_data()         – JSON summaries and temperature CSV
  export_multi_network_plots()        – publication-quality plots (with fallback)
  export_multi_network_latex()        – LaTeX comparison tables
  export_multi_network_results()      – standalone convenience function
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from calion.logging_config import get_logger

logger = get_logger(__name__)


# ── Data export (JSON + CSV) ───────────────────────────────────────────────────

def export_multi_network_data(
    multi_dir: str,
    multi_data: dict[str, Any],
    timeseries_df: pd.DataFrame,
) -> dict[str, str]:
    """Export multi-network JSON summaries and temperature CSV.

    Creates:
      - networks_summary.json
      - heat_exchangers.json
      - network_temperatures.csv

    Returns dict mapping export key → file path.
    """
    os.makedirs(multi_dir, exist_ok=True)
    files: dict[str, str] = {}

    # Networks summary JSON
    networks_data = multi_data.get('networks', {})
    if networks_data:
        networks_export = {}
        for net_id, net_info in networks_data.items():
            net_export: dict[str, Any] = {
                'id': net_id,
                'name': net_info.get('name', net_id),
                'temperature_level': net_info.get('temperature_level', 'unknown'),
            }
            for key in ('supply_temp_c', 'return_temp_c',
                        'total_network_heat_loss_mwh', 'total_demand_mwh'):
                if key in net_info:
                    out_key = 'total_heat_loss_mwh' if key == 'total_network_heat_loss_mwh' else key
                    net_export[out_key] = net_info[key]
            networks_export[net_id] = net_export

        networks_path = os.path.join(multi_dir, "networks_summary.json")
        with open(networks_path, "w", encoding="utf-8") as f:
            json.dump(networks_export, f, indent=2, default=str)
        files["multi_network_summary"] = networks_path
        logger.info(f"  Exported: {networks_path}")

    # Heat exchangers JSON
    hx_data = multi_data.get('heat_exchangers', {})
    if hx_data:
        hx_export = {
            hx_id: {
                'id': hx_id,
                'primary_network': hx_info.get('primary_network'),
                'secondary_network': hx_info.get('secondary_network'),
                'effectiveness': hx_info.get('effectiveness'),
                'max_power_mw': hx_info.get('max_power_mw'),
                'total_heat_transferred_mwh': hx_info.get('total_heat_transferred_mwh'),
                'operating_hours': hx_info.get('operating_hours'),
            }
            for hx_id, hx_info in hx_data.items()
        }
        hx_path = os.path.join(multi_dir, "heat_exchangers.json")
        with open(hx_path, "w", encoding="utf-8") as f:
            json.dump(hx_export, f, indent=2, default=str)
        files["multi_network_heat_exchangers"] = hx_path
        logger.info(f"  Exported: {hx_path}")

    # Temperature/flow CSV
    temp_cols = {
        col: timeseries_df[col].values
        for col in timeseries_df.columns
        if '_T_supply' in col or '_T_return' in col or '_Q_' in col
    }
    if temp_cols:
        temp_df = pd.DataFrame(temp_cols, index=timeseries_df.index)
        temp_path = os.path.join(multi_dir, "network_temperatures.csv")
        temp_df.to_csv(temp_path, sep=";")
        files["multi_network_temperatures_csv"] = temp_path
        logger.info(f"  Exported: {temp_path}")

    return files


# ── Plot export ────────────────────────────────────────────────────────────────

def export_multi_network_plots(
    fig_dir: str,
    multi_data: dict[str, Any],
    timeseries_df: pd.DataFrame,
    table: Any,
    series: dict[str, Any],
    plot_dpi: int = 300,
) -> dict[str, str]:
    """Export multi-network plots, falling back to basic matplotlib if needed."""
    os.makedirs(fig_dir, exist_ok=True)
    files: dict[str, str] = {}

    try:
        from calion.io.publication_plotter import (
            PublicationConfig,
        )
        from calion.io.publication_plotter import (
            export_multi_network_plots as pub_plots,
        )
        PublicationConfig.apply_style()

        plot_files = pub_plots(
            outdir=fig_dir,
            table=table,
            series=series,
            multi_network_results=multi_data,
        )

        for name, paths in plot_files.items():
            if isinstance(paths, list) and paths:
                files[f"multi_network_figure_{name}"] = paths[0]
                for p in paths:
                    logger.info(f"  Exported: {p}")
            elif paths:
                files[f"multi_network_figure_{name}"] = paths
                logger.info(f"  Exported: {paths}")

    except (ImportError, Exception) as e:
        logger.warning(f"Publication plotter not available for multi-network: {e}")
        files.update(_export_basic_multi_network_plots(fig_dir, multi_data, timeseries_df, plot_dpi))

    return files


def _export_basic_multi_network_plots(
    fig_dir: str,
    multi_data: dict[str, Any],
    timeseries_df: pd.DataFrame,
    plot_dpi: int,
) -> dict[str, str]:
    """Fallback: basic multi-network plots with matplotlib."""
    files: dict[str, str] = {}

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = timeseries_df
        networks = multi_data.get('networks', {})
        colors = plt.cm.Set1.colors

        # Plot 1: Supply and return temperatures by network
        _fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        for i, net_id in enumerate(networks):
            supply_col = f"{net_id}_T_supply"
            if supply_col in df.columns:
                axes[0].plot(
                    df.index[:168], df[supply_col].values[:168],
                    label=f"{net_id} (Vorlauf)",
                    color=colors[i % len(colors)], linewidth=1.5,
                )
        axes[0].set_ylabel("Temperature [°C]")
        axes[0].set_title("Supply Temperatures by Network")
        axes[0].legend(loc="upper right")
        axes[0].grid(True, alpha=0.3)

        for i, net_id in enumerate(networks):
            return_col = f"{net_id}_T_return"
            if return_col in df.columns:
                axes[1].plot(
                    df.index[:168], df[return_col].values[:168],
                    label=f"{net_id} (Rücklauf)",
                    color=colors[i % len(colors)], linewidth=1.5, linestyle='--',
                )
        axes[1].set_xlabel("Time")
        axes[1].set_ylabel("Temperature [°C]")
        axes[1].set_title("Return Temperatures by Network")
        axes[1].legend(loc="upper right")
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        plot_path = os.path.join(fig_dir, "multi_network_temperatures.png")
        plt.savefig(plot_path, dpi=plot_dpi, bbox_inches="tight")
        plt.close()
        files["multi_network_temperatures"] = plot_path
        logger.info(f"  Exported: {plot_path}")

        # Plot 2: Heat exchanger operation
        hx_data = multi_data.get('heat_exchangers', {})
        if hx_data:
            _fig, ax = plt.subplots(figsize=(12, 5))
            for i, hx_id in enumerate(hx_data):
                Q_col = f"{hx_id.upper().replace('-', '_')}_Q_transfer"
                if Q_col in df.columns:
                    ax.fill_between(
                        df.index[:168], 0, df[Q_col].values[:168],
                        label=hx_id, alpha=0.6, color=colors[i % len(colors)],
                    )
            ax.set_xlabel("Time")
            ax.set_ylabel("Heat Transfer [MW]")
            ax.set_title("Heat Exchanger Operation")
            ax.legend(loc="upper right")
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plot_path = os.path.join(fig_dir, "heat_exchanger_operation.png")
            plt.savefig(plot_path, dpi=plot_dpi, bbox_inches="tight")
            plt.close()
            files["heat_exchanger_operation"] = plot_path
            logger.info(f"  Exported: {plot_path}")

    except ImportError:
        logger.warning("Matplotlib not available for multi-network fallback plots")
    except Exception as e:
        logger.warning(f"Basic multi-network plot generation failed: {e}")

    return files


# ── LaTeX export ───────────────────────────────────────────────────────────────

def export_multi_network_latex(
    multi_dir: str,
    multi_data: dict[str, Any],
) -> dict[str, str]:
    """Export multi-network LaTeX comparison tables."""
    latex_dir = os.path.join(multi_dir, "latex")
    os.makedirs(latex_dir, exist_ok=True)
    files: dict[str, str] = {}

    def _fmt(val: Any, fmt: str) -> str:
        return format(val, fmt) if isinstance(val, (int, float)) else str(val or '-')

    # Network comparison table
    networks = multi_data.get('networks', {})
    if networks:
        rows = []
        for net_id, info in networks.items():
            rows.append(
                f"{info.get('name', net_id)[:20]} & "
                f"{info.get('temperature_level', '-')} & "
                f"{_fmt(info.get('supply_temp_c', '-'), '.0f')} & "
                f"{_fmt(info.get('return_temp_c', '-'), '.0f')} & "
                f"{_fmt(info.get('total_network_heat_loss_mwh', '-'), '.1f')} \\\\"
            )

        latex = "\n".join([
            r"\begin{table}[htbp]", r"\centering",
            r"\caption{Multi-Temperature Network Comparison}",
            r"\label{tab:multi_network_comparison}",
            r"\begin{tabular}{lcccc}", r"\toprule",
            r"Network & Level & $T_\text{supply}$ [°C] & $T_\text{return}$ [°C] & Loss [MWh] \\",
            r"\midrule",
            *rows,
            r"\bottomrule", r"\end{tabular}", r"\end{table}",
        ])
        latex_path = os.path.join(latex_dir, "multi_network_comparison.tex")
        Path(latex_path).write_text(latex, encoding="utf-8")
        files["multi_network_latex_table"] = latex_path
        logger.info(f"  Exported: {latex_path}")

    # Heat exchanger table
    hx_data = multi_data.get('heat_exchangers', {})
    if hx_data:
        rows = []
        for hx_id, info in hx_data.items():
            coupling = (
                f"{info.get('primary_network', '-')} "
                r"$\rightarrow$ "
                f"{info.get('secondary_network', '-')}"
            )
            rows.append(
                f"{hx_id} & {coupling} & "
                f"{_fmt(info.get('effectiveness', '-'), '.2f')} & "
                f"{_fmt(info.get('max_power_mw', '-'), '.1f')} & "
                f"{_fmt(info.get('total_heat_transferred_mwh', '-'), '.1f')} & "
                f"{_fmt(info.get('operating_hours', '-'), '.0f')} \\\\"
            )

        latex = "\n".join([
            r"\begin{table}[htbp]", r"\centering",
            r"\caption{Heat Exchanger Coupling Results}",
            r"\label{tab:heat_exchangers}",
            r"\begin{tabular}{lccccc}", r"\toprule",
            r"HX ID & Primary $\rightarrow$ Secondary & $\epsilon$ & $Q_\text{max}$ [MW] & Transfer [MWh] & Hours \\",
            r"\midrule",
            *rows,
            r"\bottomrule", r"\end{tabular}", r"\end{table}",
        ])
        latex_path = os.path.join(latex_dir, "heat_exchangers.tex")
        Path(latex_path).write_text(latex, encoding="utf-8")
        files["multi_network_hx_latex_table"] = latex_path
        logger.info(f"  Exported: {latex_path}")

    return files


# ── Standalone convenience function ───────────────────────────────────────────

def export_multi_network_results(
    multi_network_results: dict[str, Any],
    output_dir: str,
    timeseries_df: pd.DataFrame | None = None,
    scenario_name: str | None = None,
) -> ExportResult:  # type: ignore[name-defined]  # noqa: F821
    """
    Standalone export function for multi-network results.

    Use this when you have multi-network results but not a full workflow.

    Parameters
    ----------
    multi_network_results : dict
        Results from MultiNetworkManager.get_results()
    output_dir : str
        Output directory path
    timeseries_df : pd.DataFrame, optional
        Timeseries data with network columns
    scenario_name : str, optional
        Scenario name for filenames

    Returns
    -------
    ExportResult
        Export summary

    Example
    -------
    >>> from calion.models.multi_network_manager import MultiNetworkManager
    >>> from calion.io.exporters.multi_network_exporter import export_multi_network_results
    >>>
    >>> manager = MultiNetworkManager(config)
    >>> results = manager.get_results(model, config, time_set)
    >>> export_result = export_multi_network_results(results, "exports/multi_net")
    """
    from calion.io.unified_exporter import ExportResult

    os.makedirs(output_dir, exist_ok=True)

    result = ExportResult(
        output_dir=output_dir,
        metadata={
            "timestamp": datetime.now().isoformat(),
            "scenario_name": scenario_name,
            "has_multi_network": True,
            "export_type": "standalone_multi_network",
        }
    )

    logger.info("=" * 60)
    logger.info("MULTI-NETWORK STANDALONE EXPORT")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)

    multi_dir = os.path.join(output_dir, "multi_network")
    os.path.join(multi_dir, "figures")

    # JSON data + temperature CSV
    _df = timeseries_df if timeseries_df is not None else pd.DataFrame()
    data_files = export_multi_network_data(multi_dir, multi_network_results, _df)
    result.generated_files.update(data_files)

    # Timeseries CSV (if provided)
    if timeseries_df is not None:
        ts_path = os.path.join(multi_dir, "timeseries.csv")
        timeseries_df.to_csv(ts_path, sep=";")
        result.generated_files["multi_network_timeseries"] = ts_path
        logger.info(f"  Exported: {ts_path}")

    # Standalone JSON sections from results
    for key in ('summary',):
        section = multi_network_results.get(key, {})
        if section:
            path = os.path.join(multi_dir, f"{key}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(section, f, indent=2, default=str)
            result.generated_files[f"multi_network_overall_{key}"] = path
            logger.info(f"  Exported: {path}")

    # LaTeX tables
    try:
        latex_files = export_multi_network_latex(multi_dir, multi_network_results)
        result.generated_files.update(latex_files)
    except Exception as e:
        logger.warning(f"Multi-network LaTeX export failed: {e}")

    # Manifest
    manifest_path = os.path.join(output_dir, "export_manifest.json")
    networks_data = multi_network_results.get('networks', {})
    hx_data = multi_network_results.get('heat_exchangers', {})
    manifest = {
        "export_timestamp": datetime.now().isoformat(),
        "output_dir": output_dir,
        "export_type": "multi_network_standalone",
        "num_networks": len(networks_data),
        "num_heat_exchangers": len(hx_data),
        "generated_files": result.generated_files,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    result.generated_files["manifest"] = manifest_path

    logger.info(result.summary())
    return result
