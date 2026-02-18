#sensitivity.py
"""Sensitivity analysis framework for scientific publications.

This module provides tools for systematic parameter variation studies,
required for peer-reviewed publications in journals like Applied Energy.
Implements best practices for uncertainty quantification and robustness analysis.
"""

from __future__ import annotations

from typing import Dict, List, Any, Callable
from dataclasses import dataclass, field
import copy

from energis.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ParameterVariation:
    """Specification for a parameter sensitivity analysis.

    Attributes:
        param_path: Dot-notation path to parameter (e.g., "generators.p2h.el_to_th_eff")
        base_value: Baseline parameter value
        variations: List of variation factors (e.g., [0.9, 1.0, 1.1] for ±10%)
        variation_type: Type of variation ("multiplicative" or "absolute")
        description: Human-readable description
        units: Parameter units (for reporting)
    """

    param_path: str
    base_value: float
    variations: List[float]
    variation_type: str = "multiplicative"  # or "absolute"
    description: str = ""
    units: str = ""

    def __post_init__(self):
        if self.variation_type not in ["multiplicative", "absolute"]:
            raise ValueError(
                f"variation_type must be 'multiplicative' or 'absolute', "
                f"got {self.variation_type}"
            )

    def get_values(self) -> List[float]:
        """Get actual parameter values for all variations."""
        if self.variation_type == "multiplicative":
            return [self.base_value * v for v in self.variations]
        else:  # absolute
            return [self.base_value + v for v in self.variations]

    def get_labels(self) -> List[str]:
        """Get human-readable labels for variations."""
        if self.variation_type == "multiplicative":
            return [
                f"{v*100:.0f}% of baseline"
                if v != 1.0
                else "baseline"
                for v in self.variations
            ]
        else:
            return [
                f"{self.base_value + v:.4g} {self.units}"
                for v in self.variations
            ]


@dataclass
class SensitivityResult:
    """Result of a sensitivity analysis run.

    Attributes:
        param_path: Parameter that was varied
        param_value: Actual parameter value used
        variation_label: Human-readable label
        objective_value: Objective function value (e.g., total cost)
        key_metrics: Dictionary of key performance indicators
        config: Full configuration used for this run
        solve_status: Solver status (for detecting infeasibilities)
    """

    param_path: str
    param_value: float
    variation_label: str
    objective_value: float | None
    key_metrics: Dict[str, float] = field(default_factory=dict)
    config: Dict[str, Any] | None = None
    solve_status: str = "unknown"


def create_standard_sensitivity_study() -> List[ParameterVariation]:
    """Create a standard sensitivity study for heat planning publications.

    Returns list of parameter variations covering:
    - P2H efficiency: ±3%
    - Heat pump COP: ±5%
    - Storage losses: ±50%
    - Storage efficiency: ±5%
    - Fuel prices: ±20%

    Returns:
        List of ParameterVariation specifications

    Example:
        >>> variations = create_standard_sensitivity_study()
        >>> for var in variations:
        ...     logger.info(f"{var.description}: {var.get_labels()}")
        P2H efficiency: ['95% of baseline', 'baseline', '105% of baseline']
        Heat pump COP: ['90% of baseline', 'baseline', '110% of baseline']
        ...

    Note:
        These ranges are based on:
        - Manufacturer data variability (±3-5%)
        - Measurement uncertainty (±2-5%)
        - Applied Energy publication standards (±10-20% for robust analysis)
    """
    return [
        # P2H (Electrode Boiler) Efficiency
        ParameterVariation(
            param_path="generators.p2h.el_to_th_eff",
            base_value=0.99,
            variations=[0.97, 1.0, 1.03],
            variation_type="multiplicative",
            description="P2H efficiency (electrode boiler)",
            units="-",
        ),
        # Heat Pump COP
        ParameterVariation(
            param_path="heat_pumps.types.standard.eta",
            base_value=0.75,
            variations=[0.95, 1.0, 1.05],
            variation_type="multiplicative",
            description="Heat pump Carnot efficiency factor",
            units="-",
        ),
        # Storage Loss Rate
        ParameterVariation(
            param_path="storage.hourly_loss",
            base_value=0.0005,
            variations=[0.5, 1.0, 1.5],
            variation_type="multiplicative",
            description="Storage hourly loss rate",
            units="1/h",
        ),
        # Storage Charge Efficiency
        ParameterVariation(
            param_path="storage.eff_charge",
            base_value=0.98,
            variations=[0.95, 1.0, 1.03],
            variation_type="multiplicative",
            description="Storage charge efficiency",
            units="-",
        ),
        # Storage Discharge Efficiency
        ParameterVariation(
            param_path="storage.eff_discharge",
            base_value=0.98,
            variations=[0.95, 1.0, 1.03],
            variation_type="multiplicative",
            description="Storage discharge efficiency",
            units="-",
        ),
        # Gas Price
        ParameterVariation(
            param_path="fuels.gas.price_eur_mwh",
            base_value=58.6,
            variations=[0.8, 1.0, 1.2],
            variation_type="multiplicative",
            description="Natural gas price",
            units="€/MWh",
        ),
        # Electricity Price (for P2H)
        ParameterVariation(
            param_path="electricity.price_eur_mwh",
            base_value=50.0,
            variations=[0.8, 1.0, 1.2],
            variation_type="multiplicative",
            description="Electricity price",
            units="€/MWh",
        ),
    ]


def apply_parameter_variation(
    config: Dict[str, Any],
    param_path: str,
    value: float,
) -> Dict[str, Any]:
    """Apply a parameter variation to a configuration dictionary.

    Uses dot-notation to navigate nested dictionaries and update values.

    Args:
        config: Configuration dictionary (will be deep-copied)
        param_path: Dot-separated path (e.g., "fuels.gas.price_eur_mwh")
        value: New parameter value

    Returns:
        Modified configuration (deep copy of original)

    Examples:
        >>> config = {"fuels": {"gas": {"price_eur_mwh": 50.0}}}
        >>> new_config = apply_parameter_variation(config, "fuels.gas.price_eur_mwh", 60.0)
        >>> new_config["fuels"]["gas"]["price_eur_mwh"]
        60.0
        >>> config["fuels"]["gas"]["price_eur_mwh"]  # Original unchanged
        50.0

    Raises:
        KeyError: If parameter path does not exist in configuration
    """
    # Deep copy to avoid modifying original
    modified_config = copy.deepcopy(config)

    # Navigate to parent and update
    keys = param_path.split(".")
    current = modified_config

    # Navigate to parent
    for key in keys[:-1]:
        if key not in current:
            raise KeyError(f"Path component '{key}' not found in configuration at {param_path}")
        current = current[key]

    # Update final key
    final_key = keys[-1]
    if final_key not in current:
        raise KeyError(f"Parameter '{final_key}' not found in configuration at {param_path}")

    current[final_key] = value

    return modified_config


def run_sensitivity_analysis(
    base_config: Dict[str, Any],
    variations: List[ParameterVariation],
    run_optimization_func: Callable[[Dict[str, Any]], SensitivityResult],
    parallel: bool = False,
) -> Dict[str, List[SensitivityResult]]:
    """Run systematic sensitivity analysis with parameter variations.

    Executes optimization for each parameter variation and collects results.
    Suitable for generating publication-ready sensitivity tables and plots.

    Args:
        base_config: Baseline configuration dictionary
        variations: List of parameter variations to test
        run_optimization_func: Function that takes config dict and returns SensitivityResult
        parallel: Whether to run variations in parallel (requires dask or similar)

    Returns:
        Dictionary mapping parameter paths to lists of results

    Example:
        >>> def run_opt(config):
        ...     # Your optimization logic here
        ...     result = optimize_system(config)
        ...     return SensitivityResult(
        ...         param_path="test.param",
        ...         param_value=config["test"]["param"],
        ...         variation_label="baseline",
        ...         objective_value=result.objective,
        ...         key_metrics={"total_cost": result.objective}
        ...     )
        >>>
        >>> variations = create_standard_sensitivity_study()
        >>> results = run_sensitivity_analysis(base_config, variations, run_opt)
        >>>
        >>> # Analyze results
        >>> for param_path, result_list in results.items():
        ...     logger.info(f"Parameter: {param_path}")
        ...     for res in result_list:
        ...         logger.info(f"  {res.variation_label}: {res.objective_value:.2f}")

    Note:
        Results are suitable for:
        - Tornado diagrams (one-at-a-time sensitivity)
        - Sensitivity tables for publications
        - Robustness assessment
        - Uncertainty quantification
    """
    results_by_param: Dict[str, List[SensitivityResult]] = {}

    for variation in variations:
        param_results = []
        param_values = variation.get_values()
        param_labels = variation.get_labels()

        for value, label in zip(param_values, param_labels):
            # Create modified configuration
            try:
                modified_config = apply_parameter_variation(
                    base_config, variation.param_path, value
                )

                # Run optimization
                result = run_optimization_func(modified_config)

                # Ensure metadata is populated
                result.param_path = variation.param_path
                result.param_value = value
                result.variation_label = label

                param_results.append(result)

            except Exception as e:
                # Record failed run
                param_results.append(
                    SensitivityResult(
                        param_path=variation.param_path,
                        param_value=value,
                        variation_label=label,
                        objective_value=None,
                        solve_status=f"error: {str(e)}",
                    )
                )

        results_by_param[variation.param_path] = param_results

    return results_by_param


def format_sensitivity_table(
    results: Dict[str, List[SensitivityResult]],
    metric_name: str = "objective_value",
    format_spec: str = ".2f",
) -> str:
    """Format sensitivity results as publication-ready Markdown table.

    Args:
        results: Results from run_sensitivity_analysis()
        metric_name: Name of metric to display ("objective_value" or key from key_metrics)
        format_spec: Format specification for numbers (e.g., ".2f", ".2e")

    Returns:
        Markdown-formatted table string

    Example:
        >>> table = format_sensitivity_table(results, "objective_value", ".2f")
        >>> print(table)
        | Parameter | Variation | Value | Δ from baseline | Δ % |
        |-----------|-----------|-------|-----------------|-----|
        | P2H efficiency | 95% | 1234.56 | +12.34 | +1.0% |
        | P2H efficiency | baseline | 1222.22 | 0.00 | 0.0% |
        | P2H efficiency | 105% | 1210.10 | -12.12 | -1.0% |
        ...

    Note:
        Output is suitable for direct inclusion in LaTeX/Markdown documents
        for Applied Energy or similar journals.
    """
    lines = []
    lines.append("| Parameter | Variation | Value | Δ from baseline | Δ % |")
    lines.append("|-----------|-----------|-------|-----------------|-----|")

    for param_path, result_list in results.items():
        # Find baseline value
        baseline_value = None
        for res in result_list:
            if "baseline" in res.variation_label.lower():
                if metric_name == "objective_value":
                    baseline_value = res.objective_value
                else:
                    baseline_value = res.key_metrics.get(metric_name)
                break

        for res in result_list:
            # Get metric value
            if metric_name == "objective_value":
                value = res.objective_value
            else:
                value = res.key_metrics.get(metric_name)

            # Format value
            if value is None:
                value_str = "N/A"
                delta_str = "N/A"
                delta_pct_str = "N/A"
            else:
                value_str = f"{value:{format_spec}}"

                if baseline_value is not None:
                    delta = value - baseline_value
                    delta_str = f"{delta:+{format_spec}}"
                    if baseline_value != 0:
                        delta_pct = (delta / baseline_value) * 100
                        delta_pct_str = f"{delta_pct:+.1f}%"
                    else:
                        delta_pct_str = "N/A"
                else:
                    delta_str = "N/A"
                    delta_pct_str = "N/A"

            # Shorten parameter path for display
            param_display = param_path.split(".")[-1]

            lines.append(
                f"| {param_display} | {res.variation_label} | {value_str} | "
                f"{delta_str} | {delta_pct_str} |"
            )

    return "\n".join(lines)


def calculate_sensitivity_indices(
    results: Dict[str, List[SensitivityResult]],
    metric_name: str = "objective_value",
) -> Dict[str, float]:
    """Calculate normalized sensitivity indices for parameter ranking.

    Computes the relative impact of each parameter on the objective,
    useful for identifying critical parameters in publications.

    Sensitivity index = |max_value - min_value| / baseline_value

    Args:
        results: Results from run_sensitivity_analysis()
        metric_name: Metric to analyze

    Returns:
        Dictionary mapping parameter paths to sensitivity indices

    Example:
        >>> indices = calculate_sensitivity_indices(results)
        >>> for param, index in sorted(indices.items(), key=lambda x: x[1], reverse=True):
        ...     logger.info(f"{param}: {index:.3f}")
        fuels.gas.price_eur_mwh: 0.156
        storage.hourly_loss: 0.023
        generators.p2h.el_to_th_eff: 0.012
        ...

    Note:
        Higher indices indicate parameters with greater impact on results.
        Use for:
        - Prioritizing data collection efforts
        - Identifying critical assumptions
        - Tornado diagram ordering
    """
    indices = {}

    for param_path, result_list in results.items():
        # Extract metric values
        values = []
        baseline = None

        for res in result_list:
            if metric_name == "objective_value":
                value = res.objective_value
            else:
                value = res.key_metrics.get(metric_name)

            if value is not None:
                values.append(value)
                if "baseline" in res.variation_label.lower():
                    baseline = value

        # Calculate sensitivity index
        if values and baseline is not None and baseline != 0:
            value_range = max(values) - min(values)
            sensitivity = abs(value_range / baseline)
            indices[param_path] = sensitivity

    return indices
