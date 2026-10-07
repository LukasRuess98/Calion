"""Analysis tools for scientific publications and validation.

This package provides tools for:
- Sensitivity analysis
- Parameter variation studies
- Robustness assessment
- Uncertainty quantification

Designed for peer-reviewed publications in journals like Applied Energy.
"""

from .co2_resolution_analysis import (
    CO2ResolutionAnalysis,
    ResolutionScenario,
    analyze_co2_resolution,
    analyze_from_result,
    create_comparison_report,
    create_monthly_breakdown,
)
from .sensitivity import (
    ParameterVariation,
    SensitivityResult,
    apply_parameter_variation,
    calculate_sensitivity_indices,
    create_standard_sensitivity_study,
    format_sensitivity_table,
    run_sensitivity_analysis,
)

__all__ = [
    "CO2ResolutionAnalysis",
    "ParameterVariation",
    # CO2 Resolution Analysis
    "ResolutionScenario",
    "SensitivityResult",
    "analyze_co2_resolution",
    "analyze_from_result",
    "apply_parameter_variation",
    "calculate_sensitivity_indices",
    "create_comparison_report",
    "create_monthly_breakdown",
    "create_standard_sensitivity_study",
    "format_sensitivity_table",
    "run_sensitivity_analysis",
]
