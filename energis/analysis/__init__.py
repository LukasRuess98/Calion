"""Analysis tools for scientific publications and validation.

This package provides tools for:
- Sensitivity analysis
- Parameter variation studies
- Robustness assessment
- Uncertainty quantification

Designed for peer-reviewed publications in journals like Applied Energy.
"""

from .sensitivity import (
    ParameterVariation,
    SensitivityResult,
    create_standard_sensitivity_study,
    apply_parameter_variation,
    run_sensitivity_analysis,
    format_sensitivity_table,
    calculate_sensitivity_indices,
)

from .co2_resolution_analysis import (
    ResolutionScenario,
    CO2ResolutionAnalysis,
    analyze_co2_resolution,
    analyze_from_result,
    create_comparison_report,
    create_monthly_breakdown,
)

__all__ = [
    "ParameterVariation",
    "SensitivityResult",
    "create_standard_sensitivity_study",
    "apply_parameter_variation",
    "run_sensitivity_analysis",
    "format_sensitivity_table",
    "calculate_sensitivity_indices",
    # CO2 Resolution Analysis
    "ResolutionScenario",
    "CO2ResolutionAnalysis",
    "analyze_co2_resolution",
    "analyze_from_result",
    "create_comparison_report",
    "create_monthly_breakdown",
]
