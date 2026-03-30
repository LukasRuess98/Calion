"""Analytical validation module for scientific publications.

This module provides tools for validating the optimization framework
using analytically solvable test cases. Required for peer-reviewed
publications in journals like Applied Energy or IEEE Transactions.

Example usage:
    >>> from calion.validation import run_validation_suite
    >>> results = run_validation_suite()
    >>> print(results.summary())
"""

from calion.validation.analytical_benchmarks import (
    AnalyticalTestCase,
    ValidationResult,
    run_validation_suite,
    run_single_test,
    create_standard_test_suite,
)
from calion.validation.validation_report import (
    generate_validation_report,
    export_validation_summary,
)

__all__ = [
    "AnalyticalTestCase",
    "ValidationResult",
    "run_validation_suite",
    "run_single_test",
    "create_standard_test_suite",
    "generate_validation_report",
    "export_validation_summary",
]
