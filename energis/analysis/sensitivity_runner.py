"""Integrated sensitivity analysis runner for publications.

This module provides a complete workflow for running sensitivity analyses
and generating publication-ready outputs (LaTeX tables, Tornado diagrams).

Designed for Applied Energy, IEEE Transactions on Sustainable Energy, etc.

Example usage:
    >>> from energis.analysis.sensitivity_runner import run_full_sensitivity_study
    >>> results = run_full_sensitivity_study(
    ...     base_configs=["configs/base.yaml", "configs/system.yaml"],
    ...     output_dir="exports/sensitivity"
    ... )
    >>> print(f"Generated files: {results.generated_files}")
"""

from __future__ import annotations

import logging
import os
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable

from energis.analysis.sensitivity import (
    ParameterVariation,
    SensitivityResult,
    run_sensitivity_analysis,
    calculate_sensitivity_indices,
    create_standard_sensitivity_study,
    apply_parameter_variation,
)

logger = logging.getLogger(__name__)


@dataclass
class SensitivityStudyResult:
    """Complete results from a sensitivity study.

    Attributes:
        results: Dictionary mapping parameter paths to lists of results
        indices: Sensitivity indices for each parameter
        baseline_value: Objective value at baseline
        generated_files: Paths to generated report files
        metadata: Study metadata (timestamp, config, etc.)
    """

    results: Dict[str, List[SensitivityResult]]
    indices: Dict[str, float]
    baseline_value: float
    generated_files: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_top_parameters(self, n: int = 5) -> List[tuple]:
        """Get top N most sensitive parameters.

        Returns list of (param_path, sensitivity_index) tuples.
        """
        sorted_params = sorted(
            self.indices.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_params[:n]

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            "SENSITIVITY ANALYSIS SUMMARY",
            "=" * 60,
            f"Baseline objective value: {self.baseline_value:,.0f} EUR",
            f"Parameters analyzed: {len(self.results)}",
            "",
            "TOP SENSITIVE PARAMETERS:",
            "-" * 40,
        ]

        for i, (param, index) in enumerate(self.get_top_parameters(5), 1):
            lines.append(f"  {i}. {param}: {index*100:.2f}% sensitivity")

        lines.append("=" * 60)
        return "\n".join(lines)


def create_publication_sensitivity_study() -> List[ParameterVariation]:
    """Create extended parameter variation set for peer-reviewed publications.

    Returns a comprehensive set of variations covering:
    - Technology efficiency parameters
    - Economic parameters (prices, costs)
    - Operational parameters
    - Design constraints

    The variation ranges are based on:
    - Manufacturer uncertainty (±3-5%)
    - Market price volatility (±20%)
    - Applied Energy publication standards

    Returns:
        List of ParameterVariation specifications
    """
    variations = []

    # ==========================================================================
    # Technology Efficiency Parameters
    # ==========================================================================

    # Heat Pump Carnot Efficiency
    variations.append(
        ParameterVariation(
            param_path="heat_pumps.types.standard.eta",
            base_value=0.50,
            variations=[0.90, 0.95, 1.0, 1.05, 1.10],
            variation_type="multiplicative",
            description="Heat pump Carnot efficiency factor",
            units="-",
        )
    )

    # P2H Efficiency
    variations.append(
        ParameterVariation(
            param_path="generators.p2h.el_to_th_eff",
            base_value=0.99,
            variations=[0.97, 0.99, 1.0, 1.01],
            variation_type="multiplicative",
            description="Electrode boiler efficiency",
            units="-",
        )
    )

    # Storage Charge Efficiency
    variations.append(
        ParameterVariation(
            param_path="storage.eff_charge",
            base_value=0.95,
            variations=[0.95, 1.0, 1.03],
            variation_type="multiplicative",
            description="Storage charge efficiency",
            units="-",
        )
    )

    # Storage Discharge Efficiency
    variations.append(
        ParameterVariation(
            param_path="storage.eff_discharge",
            base_value=0.95,
            variations=[0.95, 1.0, 1.03],
            variation_type="multiplicative",
            description="Storage discharge efficiency",
            units="-",
        )
    )

    # Storage Hourly Loss
    variations.append(
        ParameterVariation(
            param_path="storage.hourly_loss",
            base_value=0.0005,
            variations=[0.5, 1.0, 2.0],
            variation_type="multiplicative",
            description="Storage hourly self-discharge",
            units="1/h",
        )
    )

    # ==========================================================================
    # Economic Parameters
    # ==========================================================================

    # CO2 Price
    variations.append(
        ParameterVariation(
            param_path="costs.co2_price_eur_t",
            base_value=85.0,
            variations=[0.5, 0.75, 1.0, 1.25, 1.5],
            variation_type="multiplicative",
            description="CO2 certificate price",
            units="EUR/t",
        )
    )

    # Gas Price
    variations.append(
        ParameterVariation(
            param_path="fuels.gas.price_eur_mwh",
            base_value=50.0,
            variations=[0.7, 0.85, 1.0, 1.15, 1.3],
            variation_type="multiplicative",
            description="Natural gas price",
            units="EUR/MWh",
        )
    )

    # Heat Pump CAPEX
    variations.append(
        ParameterVariation(
            param_path="costs.capex_hp_eur_kw",
            base_value=800.0,
            variations=[0.8, 0.9, 1.0, 1.1, 1.2],
            variation_type="multiplicative",
            description="Heat pump investment cost",
            units="EUR/kW",
        )
    )

    # Storage CAPEX
    variations.append(
        ParameterVariation(
            param_path="costs.capex_storage_eur_kwh",
            base_value=30.0,
            variations=[0.7, 0.85, 1.0, 1.15, 1.3],
            variation_type="multiplicative",
            description="Storage investment cost",
            units="EUR/kWh",
        )
    )

    # Demand Charge
    variations.append(
        ParameterVariation(
            param_path="grid.demand_charge_eur_kw_month",
            base_value=10.0,
            variations=[0.5, 0.75, 1.0, 1.25, 1.5],
            variation_type="multiplicative",
            description="Grid demand charge",
            units="EUR/kW/month",
        )
    )

    # ==========================================================================
    # Operational Parameters
    # ==========================================================================

    # Demand Scaling
    variations.append(
        ParameterVariation(
            param_path="scenario.demand_scaling_factor",
            base_value=1.0,
            variations=[0.9, 0.95, 1.0, 1.05, 1.1],
            variation_type="multiplicative",
            description="Heat demand scaling factor",
            units="-",
        )
    )

    return variations


def run_full_sensitivity_study(
    base_configs: List[str],
    variations: List[ParameterVariation] = None,
    output_dir: str = "exports/sensitivity",
    generate_plots: bool = True,
    generate_latex: bool = True,
    parallel: bool = False,
    n_jobs: int = -1,
) -> SensitivityStudyResult:
    """Run a complete sensitivity study with all outputs.

    This is the main entry point for publication-ready sensitivity analysis.

    Parameters
    ----------
    base_configs : List[str]
        Base configuration file paths
    variations : List[ParameterVariation], optional
        Parameter variations to test. If None, uses publication standard set.
    output_dir : str
        Output directory for results and plots
    generate_plots : bool
        Generate tornado diagram and other visualizations
    generate_latex : bool
        Generate LaTeX tables
    parallel : bool
        Run variations in parallel (requires joblib)
    n_jobs : int
        Number of parallel jobs (-1 for all cores)

    Returns
    -------
    SensitivityStudyResult
        Complete study results including file paths

    Example:
        >>> results = run_full_sensitivity_study(
        ...     base_configs=["configs/base.yaml"],
        ...     output_dir="exports/sensitivity",
        ...     generate_plots=True,
        ... )
        >>> print(results.summary())
    """
    os.makedirs(output_dir, exist_ok=True)

    if variations is None:
        variations = create_publication_sensitivity_study()
        logger.info(f"Using publication standard sensitivity set with {len(variations)} parameters")

    logger.info("=" * 60)
    logger.info("STARTING SENSITIVITY ANALYSIS")
    logger.info(f"Parameters to analyze: {len(variations)}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)

    # Create run function for sensitivity analysis
    def run_optimization(config: Dict[str, Any]) -> SensitivityResult:
        """Run single optimization and extract results."""
        from energis.run.rolling_horizon import run_workflow

        # Merge base configs with overrides
        result = run_workflow(base_configs, config)

        # Extract objective value
        active_result = result.mpc_result or result.rh_result or result.pf_result
        if active_result:
            objective = sum(active_result.costs.values())
            key_metrics = {
                "total_cost": objective,
                "capex": sum(v for k, v in active_result.costs.items() if "Capex" in k or "Activation" in k),
                "opex": sum(v for k, v in active_result.costs.items() if "Capex" not in k and "Activation" not in k),
            }

            # Add CO2 if available
            if hasattr(active_result, 'summary'):
                grid_section = active_result.summary.get('grid', {})
                key_metrics["co2_emissions_t"] = float(grid_section.get("Total_CO2_emissions_t", 0) or 0)

            return SensitivityResult(
                param_path="",
                param_value=0,
                variation_label="",
                objective_value=objective,
                key_metrics=key_metrics,
                solve_status="optimal",
            )
        else:
            return SensitivityResult(
                param_path="",
                param_value=0,
                variation_label="",
                objective_value=None,
                solve_status="error",
            )

    # Load and merge base configuration
    from energis.config.merge import load_and_merge
    base_config = load_and_merge(base_configs)

    # Run sensitivity analysis
    results = run_sensitivity_analysis(
        base_config=base_config,
        variations=variations,
        run_optimization_func=run_optimization,
        parallel=parallel,
    )

    # Calculate sensitivity indices
    indices = calculate_sensitivity_indices(results)

    # Get baseline value
    baseline_value = 0.0
    for param_results in results.values():
        for res in param_results:
            if "baseline" in res.variation_label.lower() and res.objective_value is not None:
                baseline_value = res.objective_value
                break
        if baseline_value > 0:
            break

    # Create study result
    study_result = SensitivityStudyResult(
        results=results,
        indices=indices,
        baseline_value=baseline_value,
        metadata={
            "timestamp": datetime.now().isoformat(),
            "base_configs": base_configs,
            "num_parameters": len(variations),
            "num_runs": sum(len(r) for r in results.values()),
        },
    )

    generated_files = {}

    # Generate plots
    if generate_plots:
        try:
            from energis.comparison.visualization import plot_tornado_diagram, plot_sensitivity_spider

            # Tornado diagram
            tornado_path = os.path.join(output_dir, "tornado_diagram.pdf")
            plot_tornado_diagram(
                results,
                tornado_path,
                metric="objective_value",
                title="Parameter Sensitivity Analysis",
                top_n=min(10, len(results)),
            )
            generated_files["tornado_pdf"] = tornado_path
            logger.info(f"Generated tornado diagram: {tornado_path}")

            # Also generate PNG
            tornado_png = os.path.join(output_dir, "tornado_diagram.png")
            plot_tornado_diagram(
                results,
                tornado_png,
                metric="objective_value",
                top_n=min(10, len(results)),
            )
            generated_files["tornado_png"] = tornado_png

            # Spider plot
            spider_path = os.path.join(output_dir, "spider_plot.pdf")
            plot_sensitivity_spider(
                results,
                spider_path,
                metric="objective_value",
                title="Normalized Parameter Sensitivity",
            )
            generated_files["spider_pdf"] = spider_path

        except Exception as e:
            logger.warning(f"Could not generate plots: {e}")

    # Generate LaTeX table
    if generate_latex:
        try:
            from energis.io.publication_exporter import export_sensitivity_latex_table

            latex_path = os.path.join(output_dir, "sensitivity_table.tex")
            export_sensitivity_latex_table(
                results,
                latex_path,
                table_style="booktabs",
                caption="Sensitivity Analysis Results",
            )
            generated_files["latex_table"] = latex_path
            logger.info(f"Generated LaTeX table: {latex_path}")

        except Exception as e:
            logger.warning(f"Could not generate LaTeX table: {e}")

    # Export JSON summary
    json_path = os.path.join(output_dir, "sensitivity_results.json")
    _export_json_summary(study_result, json_path)
    generated_files["json_summary"] = json_path

    # Export CSV
    csv_path = os.path.join(output_dir, "sensitivity_results.csv")
    _export_csv_summary(study_result, csv_path)
    generated_files["csv_data"] = csv_path

    # Export parameter ranking
    ranking_path = os.path.join(output_dir, "parameter_ranking.txt")
    _export_parameter_ranking(study_result, ranking_path)
    generated_files["ranking"] = ranking_path

    study_result.generated_files = generated_files

    logger.info("\n" + study_result.summary())
    logger.info(f"\nGenerated {len(generated_files)} output files in {output_dir}")

    return study_result


def _export_json_summary(result: SensitivityStudyResult, output_path: str) -> None:
    """Export study results as JSON."""
    export_data = {
        "metadata": result.metadata,
        "baseline_value": result.baseline_value,
        "sensitivity_indices": result.indices,
        "top_parameters": [
            {"parameter": p, "index": i} for p, i in result.get_top_parameters(10)
        ],
        "detailed_results": {
            param: [
                {
                    "param_value": r.param_value,
                    "variation_label": r.variation_label,
                    "objective_value": r.objective_value,
                    "key_metrics": r.key_metrics,
                    "solve_status": r.solve_status,
                }
                for r in results
            ]
            for param, results in result.results.items()
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)


def _export_csv_summary(result: SensitivityStudyResult, output_path: str) -> None:
    """Export study results as CSV."""
    import csv

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")

        # Header
        writer.writerow([
            "Parameter",
            "Variation",
            "Param_Value",
            "Objective_EUR",
            "Delta_EUR",
            "Delta_Percent",
            "CO2_t",
        ])

        for param, results in result.results.items():
            # Find baseline
            baseline = next(
                (r.objective_value for r in results if "baseline" in r.variation_label.lower()),
                result.baseline_value
            )

            for r in results:
                if r.objective_value is not None:
                    delta = r.objective_value - baseline
                    delta_pct = (delta / baseline * 100) if baseline else 0
                    co2 = r.key_metrics.get("co2_emissions_t", "")
                else:
                    delta = ""
                    delta_pct = ""
                    co2 = ""

                writer.writerow([
                    param,
                    r.variation_label,
                    r.param_value,
                    r.objective_value,
                    delta,
                    delta_pct,
                    co2,
                ])


def _export_parameter_ranking(result: SensitivityStudyResult, output_path: str) -> None:
    """Export parameter sensitivity ranking."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("PARAMETER SENSITIVITY RANKING\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Baseline objective: {result.baseline_value:,.0f} EUR\n\n")
        f.write("Rank | Parameter | Sensitivity Index | Impact\n")
        f.write("-" * 50 + "\n")

        sorted_params = sorted(result.indices.items(), key=lambda x: x[1], reverse=True)

        for i, (param, index) in enumerate(sorted_params, 1):
            impact = "HIGH" if index > 0.05 else "MEDIUM" if index > 0.01 else "LOW"
            f.write(f"{i:4d} | {param:<25} | {index*100:6.2f}% | {impact}\n")

        f.write("\n" + "=" * 50 + "\n")
        f.write("Impact classification:\n")
        f.write("  HIGH:   >5% sensitivity (critical for results)\n")
        f.write("  MEDIUM: 1-5% sensitivity (should be monitored)\n")
        f.write("  LOW:    <1% sensitivity (robust against variation)\n")
