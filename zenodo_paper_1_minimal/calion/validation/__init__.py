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
    create_standard_test_suite,
    run_single_test,
    run_validation_suite,
)
from calion.validation.validation_report import (
    export_validation_summary,
    generate_validation_report,
)

__all__ = [
    "AnalyticalTestCase",
    "ValidationResult",
    "create_standard_test_suite",
    "export_validation_summary",
    "generate_validation_report",
    "run_single_test",
    "run_validation_suite",
]
