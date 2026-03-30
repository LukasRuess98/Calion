"""Tests for calion.validation.analytical_benchmarks — pure dataclass/logic tests."""

import math
import pytest
from calion.validation.analytical_benchmarks import (
    AnalyticalTestCase,
    ValidationResult,
    ValidationSuiteResult,
    create_standard_test_suite,
    run_single_test,
    run_validation_suite,
    _extract_test_metrics,
)


# ---------------------------------------------------------------------------
# AnalyticalTestCase
# ---------------------------------------------------------------------------

class TestAnalyticalTestCase:
    def test_defaults(self):
        tc = AnalyticalTestCase(
            name="test1",
            description="A test",
            config_overrides={},
            expected_results={"metric": 1.0},
        )
        assert tc.tolerance == 0.01
        assert tc.category == "general"
        assert tc.validation_func is None


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_to_dict(self):
        vr = ValidationResult(
            test_name="test1.metric",
            passed=True,
            expected=1.0,
            actual=1.005,
            relative_error=0.005,
            absolute_error=0.005,
            details={"tolerance": 0.01},
        )
        d = vr.to_dict()
        assert d["test_name"] == "test1.metric"
        assert d["passed"] is True
        assert d["relative_error"] == 0.005


# ---------------------------------------------------------------------------
# ValidationSuiteResult
# ---------------------------------------------------------------------------

class TestValidationSuiteResult:
    def _make_suite(self, n_pass=3, n_fail=1):
        results = []
        for i in range(n_pass):
            results.append(
                ValidationResult(
                    test_name=f"pass_{i}",
                    passed=True,
                    expected=1.0,
                    actual=1.0,
                    relative_error=0.0,
                    absolute_error=0.0,
                )
            )
        for i in range(n_fail):
            results.append(
                ValidationResult(
                    test_name=f"fail_{i}",
                    passed=False,
                    expected=1.0,
                    actual=2.0,
                    relative_error=1.0,
                    absolute_error=1.0,
                )
            )
        return ValidationSuiteResult(
            results=results,
            total_tests=n_pass + n_fail,
            passed_tests=n_pass,
            failed_tests=n_fail,
        )

    def test_pass_rate(self):
        suite = self._make_suite(3, 1)
        assert suite.pass_rate == 75.0

    def test_pass_rate_zero(self):
        suite = ValidationSuiteResult(results=[], total_tests=0, passed_tests=0, failed_tests=0)
        assert suite.pass_rate == 0.0

    def test_summary(self):
        suite = self._make_suite(2, 1)
        text = suite.summary()
        assert "PASS" in text
        assert "FAIL" in text
        assert "66.7%" in text


# ---------------------------------------------------------------------------
# create_standard_test_suite
# ---------------------------------------------------------------------------

class TestCreateStandardTestSuite:
    def test_returns_list(self):
        cases = create_standard_test_suite()
        assert isinstance(cases, list)
        assert len(cases) >= 5

    def test_all_have_names(self):
        for tc in create_standard_test_suite():
            assert tc.name
            assert tc.description
            assert tc.expected_results

    def test_categories(self):
        cats = {tc.category for tc in create_standard_test_suite()}
        assert "cop" in cats
        assert "storage" in cats
        assert "merit_order" in cats


# ---------------------------------------------------------------------------
# run_single_test — with custom run_func to avoid needing solver
# ---------------------------------------------------------------------------

class TestRunSingleTest:
    def test_custom_run_func_pass(self):
        tc = AnalyticalTestCase(
            name="simple",
            description="simple test",
            config_overrides={},
            expected_results={"value": 100.0},
            tolerance=0.05,
        )

        def run_func(configs, overrides):
            return {"value": 101.0}

        results = run_single_test(tc, [], run_func=run_func)
        assert len(results) == 1
        assert results[0].passed is True
        assert abs(results[0].relative_error - 0.01) < 1e-6

    def test_custom_run_func_fail(self):
        tc = AnalyticalTestCase(
            name="failing",
            description="fails",
            config_overrides={},
            expected_results={"value": 100.0},
            tolerance=0.01,
        )

        def run_func(configs, overrides):
            return {"value": 200.0}

        results = run_single_test(tc, [], run_func=run_func)
        assert results[0].passed is False

    def test_run_func_exception(self):
        tc = AnalyticalTestCase(
            name="error",
            description="raises",
            config_overrides={},
            expected_results={"value": 1.0},
        )

        def run_func(configs, overrides):
            raise RuntimeError("boom")

        results = run_single_test(tc, [], run_func=run_func)
        assert len(results) == 1
        assert results[0].passed is False
        assert math.isnan(results[0].actual)

    def test_zero_expected(self):
        tc = AnalyticalTestCase(
            name="zero",
            description="zero expected",
            config_overrides={},
            expected_results={"balance": 0.0},
            tolerance=0.001,
        )

        def run_func(configs, overrides):
            return {"balance": 0.0005}

        results = run_single_test(tc, [], run_func=run_func)
        # For zero expected, relative_error = actual_value
        assert results[0].relative_error == 0.0005


# ---------------------------------------------------------------------------
# run_validation_suite — with custom run_func
# ---------------------------------------------------------------------------

class TestRunValidationSuite:
    def test_custom_suite(self):
        cases = [
            AnalyticalTestCase(
                name="t1", description="", config_overrides={},
                expected_results={"a": 10.0}, tolerance=0.1,
            ),
            AnalyticalTestCase(
                name="t2", description="", config_overrides={},
                expected_results={"b": 20.0}, tolerance=0.1,
            ),
        ]

        def run_func(configs, overrides):
            return {"a": 10.5, "b": 21.0}

        suite = run_validation_suite([], cases, run_func=run_func)
        assert suite.total_tests == 2
        assert suite.passed_tests == 2
