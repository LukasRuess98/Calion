"""
Economics module for CALION.

Contains subsidy calculations, financial analysis, and regulatory compliance.
"""

from .german_subsidies import (
    GermanSubsidyCalculator,
    BEWParameters,
    KWKGParameters,
    SubsidyResult,
    BEWModule,
    calculate_subsidies_from_workflow,
)

__all__ = [
    'GermanSubsidyCalculator',
    'BEWParameters',
    'KWKGParameters',
    'SubsidyResult',
    'BEWModule',
    'calculate_subsidies_from_workflow',
]
