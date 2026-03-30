"""
Economics module for CALION.

Contains subsidy calculations, financial analysis, and regulatory compliance.
"""

from .german_subsidies import (
    BEWModule,
    BEWParameters,
    GermanSubsidyCalculator,
    KWKGParameters,
    SubsidyResult,
    calculate_subsidies_from_workflow,
)

__all__ = [
    'BEWModule',
    'BEWParameters',
    'GermanSubsidyCalculator',
    'KWKGParameters',
    'SubsidyResult',
    'calculate_subsidies_from_workflow',
]
