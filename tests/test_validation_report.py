"""Tests for energis.validation.validation_report — report generation."""

import json
import os
import pytest

from energis.validation.analytical_benchmarks import ValidationResult, ValidationSuiteResult
from energis.validation.validation_report import (
    generate_validation_report,
    export_validation_summary,
    format_for_publication,
    _summarize_by_category,
)


def _make_suite():
    results = [
        ValidationResult(
            test_name="test1.metric_a",
            passed=True,
            expected=100.0,
            actual=100.5,
            relative_error=0.005,
            absolute_error=0.5,
            details={"category": "cop", "tolerance": 0.01},
        ),
        ValidationResult(
            test_name="test2.metric_b",
            passed=False,
            expected=50.0,
            actual=55.0,
            relative_error=0.10,
            absolute_error=5.0,
            details={"category": "storage", "tolerance": 0.01},
        ),
        ValidationResult(
            test_name="test3.metric_c",
            passed=True,
            expected=0.0,
            actual=0.0001,
            relative_error=0.0001,
            absolute_error=0.0001,
            details={"category": "energy_balance", "tolerance": 0.001},
        ),
    ]
    return ValidationSuiteResult(
        results=results,
        total_tests=3,
        passed_tests=2,
        failed_tests=1,
    )


# ---------------------------------------------------------------------------
# generate_validation_report
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_all_formats(self, tmp_path):
        suite = _make_suite()
        files = generate_validation_report(suite, str(tmp_path))
        assert "latex" in files
        assert "json" in files
        assert "csv" in files
        assert "summary" in files

        # Check files exist
        for path in files.values():
            assert os.path.exists(path)

    def test_latex_content(self, tmp_path):
        suite = _make_suite()
        files = generate_validation_report(suite, str(tmp_path))
        content = open(files["latex"], encoding="utf-8").read()
        assert "\\begin{table}" in content
        assert "checkmark" in content  # for passing tests
        assert "texttimes" in content  # for failing tests

    def test_json_content(self, tmp_path):
        suite = _make_suite()
        files = generate_validation_report(suite, str(tmp_path))
        with open(files["json"], encoding="utf-8") as f:
            data = json.load(f)
        assert data["metadata"]["total_tests"] == 3
        assert data["metadata"]["passed_tests"] == 2
        assert len(data["results"]) == 3

    def test_csv_content(self, tmp_path):
        suite = _make_suite()
        files = generate_validation_report(suite, str(tmp_path))
        lines = open(files["csv"], encoding="utf-8").readlines()
        assert len(lines) == 4  # header + 3 data rows

    def test_selective_formats(self, tmp_path):
        suite = _make_suite()
        files = generate_validation_report(
            suite, str(tmp_path), include_latex=False, include_csv=False
        )
        assert "latex" not in files
        assert "csv" not in files
        assert "json" in files


# ---------------------------------------------------------------------------
# _summarize_by_category
# ---------------------------------------------------------------------------

class TestSummarizeByCategory:
    def test_groups_correctly(self):
        suite = _make_suite()
        cats = _summarize_by_category(suite)
        assert "cop" in cats
        assert "storage" in cats
        assert cats["cop"]["passed_tests"] == 1
        assert cats["storage"]["failed_tests"] == 1


# ---------------------------------------------------------------------------
# export_validation_summary
# ---------------------------------------------------------------------------

class TestExportSummary:
    def test_returns_string(self):
        suite = _make_suite()
        text = export_validation_summary(suite)
        assert "VALIDATION SUMMARY" in text
        assert "66.7%" in text


# ---------------------------------------------------------------------------
# format_for_publication
# ---------------------------------------------------------------------------

class TestFormatForPublication:
    def test_applied_energy(self):
        suite = _make_suite()
        text = format_for_publication(suite, "applied_energy")
        assert "analytical benchmark" in text
        assert "66.7%" in text

    def test_ieee(self):
        suite = _make_suite()
        text = format_for_publication(suite, "ieee")
        assert "Total tests: 3" in text

    def test_unknown_style(self):
        suite = _make_suite()
        text = format_for_publication(suite, "unknown_journal")
        assert "VALIDATION SUMMARY" in text
