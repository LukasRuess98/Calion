"""Analytical validation benchmarks for publication-ready verification.

This module provides test cases with known analytical solutions to validate
the optimization framework's correctness. Essential for peer-reviewed
publications in Applied Energy, IEEE Transactions on Sustainable Energy, etc.

The test cases cover:
1. Energy balance verification
2. Heat pump COP calculations
3. Storage round-trip efficiency
4. Merit order dispatch logic
5. Network loss calculations

Reference:
- Applied Energy publication standards require validation against
  analytical solutions or established benchmarks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import copy

logger = logging.getLogger(__name__)


@dataclass
class AnalyticalTestCase:
    """Specification for an analytical validation test case.

    Attributes:
        name: Unique test case identifier
        description: Human-readable description for publications
        config_overrides: Configuration modifications for this test
        expected_results: Dictionary of expected metric values
        tolerance: Relative tolerance for comparison (default: 1%)
        validation_func: Optional custom validation function
    """

    name: str
    description: str
    config_overrides: Dict[str, Any]
    expected_results: Dict[str, float]
    tolerance: float = 0.01  # 1% relative tolerance
    validation_func: Optional[Callable] = None
    category: str = "general"  # For grouping: energy_balance, cop, storage, merit_order, network


@dataclass
class ValidationResult:
    """Result of a single validation test.

    Attributes:
        test_name: Name of the test case
        passed: Whether the test passed
        expected: Expected value
        actual: Actual computed value
        relative_error: Relative error (actual - expected) / expected
        absolute_error: Absolute error
        details: Additional diagnostic information
    """

    test_name: str
    passed: bool
    expected: float
    actual: float
    relative_error: float
    absolute_error: float
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "relative_error": self.relative_error,
            "absolute_error": self.absolute_error,
            "details": self.details,
        }


@dataclass
class ValidationSuiteResult:
    """Aggregate results from running a validation suite."""

    results: List[ValidationResult]
    total_tests: int
    passed_tests: int
    failed_tests: int

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        return (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0.0

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            "ANALYTICAL VALIDATION SUMMARY",
            "=" * 60,
            f"Total tests:  {self.total_tests}",
            f"Passed:       {self.passed_tests}",
            f"Failed:       {self.failed_tests}",
            f"Pass rate:    {self.pass_rate:.1f}%",
            "-" * 60,
        ]

        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(
                f"  [{status}] {result.test_name}: "
                f"expected={result.expected:.4g}, actual={result.actual:.4g}, "
                f"error={result.relative_error*100:.2f}%"
            )

        lines.append("=" * 60)
        return "\n".join(lines)


def create_standard_test_suite() -> List[AnalyticalTestCase]:
    """Create standard analytical validation test suite.

    Returns a list of test cases that verify fundamental optimizer behavior:

    1. Energy Balance Tests
       - Verify that heat supply equals demand
       - Check storage energy conservation

    2. Heat Pump COP Tests
       - Verify COP calculation under controlled conditions
       - Check Carnot efficiency factor application

    3. Storage Tests
       - Round-trip efficiency verification
       - Self-discharge loss calculation

    4. Merit Order Tests
       - Verify cheapest source dispatches first
       - Check capacity constraints

    5. Network Loss Tests (if applicable)
       - Linear loss model verification

    Returns:
        List of AnalyticalTestCase objects
    """
    test_cases = []

    # ==========================================================================
    # Test 1: Constant Demand, Single Heat Pump
    # ==========================================================================
    # Analytical solution: P_el = Q_th / COP
    # With COP = eta_carnot * (T_sink / (T_sink - T_source))
    test_cases.append(
        AnalyticalTestCase(
            name="SingleHP_ConstantDemand",
            description=(
                "Verifies heat pump electricity consumption for constant demand. "
                "Expected: P_el = Q_th / COP, where COP = eta * T_sink/(T_sink-T_source)"
            ),
            config_overrides={
                "scenario": {
                    "workflow": ["PF"],
                    "horizon": {"start": "2023-01-01", "end": "2023-01-01 23:00"},
                },
                # Simplified system: single HP, no storage, constant demand
                "test_mode": {
                    "constant_demand_mw": 5.0,
                    "constant_source_temp_c": 10.0,
                    "constant_sink_temp_c": 70.0,
                },
            },
            expected_results={
                # COP = 0.5 * (70+273)/(70-10) = 0.5 * 343/60 = 2.858
                # P_el = 5.0 / 2.858 = 1.749 MW
                # Total for 24h: 1.749 * 24 = 41.98 MWh
                "hp_electricity_mwh": 41.98,
                "total_heat_mwh": 120.0,  # 5 MW * 24h
            },
            tolerance=0.02,  # 2% tolerance for this complex calculation
            category="cop",
        )
    )

    # ==========================================================================
    # Test 2: Storage Round-Trip Efficiency
    # ==========================================================================
    # Charge 100 MWh, wait, discharge: should get eff_charge * eff_discharge * 100
    test_cases.append(
        AnalyticalTestCase(
            name="Storage_RoundTrip_Efficiency",
            description=(
                "Verifies storage round-trip efficiency. "
                "Charge 100 MWh, discharge: expect eta_charge * eta_discharge * 100 MWh"
            ),
            config_overrides={
                "scenario": {
                    "workflow": ["PF"],
                    "horizon": {"start": "2023-01-01", "end": "2023-01-02 23:00"},
                },
                "test_mode": {
                    "storage_only": True,
                    "charge_period_hours": 10,
                    "charge_power_mw": 10.0,  # 10 MW for 10h = 100 MWh
                    "wait_hours": 4,
                    "discharge_all": True,
                },
                "storage": {
                    "eff_charge": 0.95,
                    "eff_discharge": 0.95,
                    "hourly_loss": 0.0,  # No self-discharge for this test
                },
            },
            expected_results={
                # Round-trip: 100 * 0.95 * 0.95 = 90.25 MWh
                "storage_discharged_mwh": 90.25,
                "round_trip_efficiency": 0.9025,
            },
            tolerance=0.01,
            category="storage",
        )
    )

    # ==========================================================================
    # Test 3: Storage Self-Discharge
    # ==========================================================================
    # Charge storage, wait for known time, verify SOC decay
    test_cases.append(
        AnalyticalTestCase(
            name="Storage_SelfDischarge",
            description=(
                "Verifies storage self-discharge calculation. "
                "SOC(t) = SOC_0 * (1 - hourly_loss)^t"
            ),
            config_overrides={
                "scenario": {
                    "workflow": ["PF"],
                    "horizon": {"start": "2023-01-01", "end": "2023-01-03 23:00"},
                },
                "test_mode": {
                    "storage_only": True,
                    "initial_soc_mwh": 100.0,
                    "no_dispatch": True,  # Just observe self-discharge
                },
                "storage": {
                    "eff_charge": 1.0,
                    "eff_discharge": 1.0,
                    "hourly_loss": 0.001,  # 0.1% per hour
                },
            },
            expected_results={
                # After 72 hours: 100 * (1-0.001)^72 = 100 * 0.9305 = 93.05 MWh
                "final_soc_mwh": 93.05,
            },
            tolerance=0.01,
            category="storage",
        )
    )

    # ==========================================================================
    # Test 4: Merit Order - HP vs P2H
    # ==========================================================================
    # When HP is cheaper, it should dispatch before P2H
    test_cases.append(
        AnalyticalTestCase(
            name="MeritOrder_HP_vs_P2H",
            description=(
                "Verifies merit order dispatch: cheaper source dispatches first. "
                "HP with COP=3 should dispatch before P2H with eta=0.99"
            ),
            config_overrides={
                "scenario": {
                    "workflow": ["PF"],
                    "horizon": {"start": "2023-01-01", "end": "2023-01-01 23:00"},
                },
                "test_mode": {
                    "constant_demand_mw": 10.0,
                    "hp_capacity_mw": 8.0,  # HP can cover 8 MW
                    "p2h_capacity_mw": 10.0,  # P2H available for rest
                    "electricity_price_eur_mwh": 100.0,
                },
                "heat_pumps": {
                    "HP1": {"capacity_mw": 8.0, "cop_fixed": 3.0},
                },
                "generators": {
                    "p2h": {"capacity_mw": 10.0, "el_to_th_eff": 0.99},
                },
            },
            expected_results={
                # HP cost: 100/3 = 33.33 EUR/MWh_th
                # P2H cost: 100/0.99 = 101.01 EUR/MWh_th
                # HP should run at full 8 MW, P2H covers 2 MW
                "hp_output_mwh": 192.0,  # 8 MW * 24h
                "p2h_output_mwh": 48.0,   # 2 MW * 24h
            },
            tolerance=0.02,
            category="merit_order",
        )
    )

    # ==========================================================================
    # Test 5: Energy Balance Verification
    # ==========================================================================
    test_cases.append(
        AnalyticalTestCase(
            name="EnergyBalance_Conservation",
            description=(
                "Verifies energy conservation: total generation equals "
                "demand plus storage net charge plus network losses"
            ),
            config_overrides={
                "scenario": {
                    "workflow": ["PF"],
                    "horizon": {"start": "2023-01-01", "end": "2023-01-07 23:00"},
                },
            },
            expected_results={
                # Energy balance: Generation = Demand + Storage_net + Losses + Dump
                "energy_balance_error": 0.0,
            },
            tolerance=0.001,  # Very tight tolerance for energy balance
            category="energy_balance",
        )
    )

    # ==========================================================================
    # Test 6: P2H Efficiency Verification
    # ==========================================================================
    test_cases.append(
        AnalyticalTestCase(
            name="P2H_Efficiency",
            description=(
                "Verifies P2H (electrode boiler) efficiency. "
                "Q_th = P_el * eta_el_to_th"
            ),
            config_overrides={
                "scenario": {
                    "workflow": ["PF"],
                    "horizon": {"start": "2023-01-01", "end": "2023-01-01 23:00"},
                },
                "test_mode": {
                    "p2h_only": True,
                    "constant_demand_mw": 10.0,
                },
                "generators": {
                    "p2h": {"el_to_th_eff": 0.99},
                },
            },
            expected_results={
                # P_el = Q_th / eta = 10 / 0.99 = 10.101 MW
                # Total: 10.101 * 24 = 242.42 MWh_el
                "p2h_electricity_mwh": 242.42,
                "p2h_heat_mwh": 240.0,  # 10 MW * 24h
            },
            tolerance=0.01,
            category="efficiency",
        )
    )

    return test_cases


def run_single_test(
    test_case: AnalyticalTestCase,
    base_configs: List[str],
    run_func: Optional[Callable] = None,
) -> List[ValidationResult]:
    """Run a single analytical test case.

    Parameters
    ----------
    test_case : AnalyticalTestCase
        The test case specification
    base_configs : List[str]
        Base configuration file paths
    run_func : Callable, optional
        Custom function to run the optimization.
        If None, uses the default workflow runner.

    Returns
    -------
    List[ValidationResult]
        Results for each expected metric in the test case
    """
    results = []

    logger.info(f"Running test: {test_case.name}")
    logger.info(f"  Description: {test_case.description}")

    try:
        # Run optimization with test configuration
        if run_func is None:
            from energis.run.rolling_horizon import run_workflow
            workflow_result = run_workflow(base_configs, test_case.config_overrides)

            # Extract actual values based on expected results keys
            actual_values = _extract_test_metrics(workflow_result, test_case.expected_results.keys())
        else:
            actual_values = run_func(base_configs, test_case.config_overrides)

        # Compare each expected metric
        for metric_name, expected_value in test_case.expected_results.items():
            actual_value = actual_values.get(metric_name, 0.0)

            # Calculate errors
            if abs(expected_value) > 1e-10:
                relative_error = (actual_value - expected_value) / expected_value
            else:
                relative_error = actual_value  # For zero expected, use absolute

            absolute_error = actual_value - expected_value

            # Determine pass/fail
            passed = abs(relative_error) <= test_case.tolerance

            results.append(
                ValidationResult(
                    test_name=f"{test_case.name}.{metric_name}",
                    passed=passed,
                    expected=expected_value,
                    actual=actual_value,
                    relative_error=relative_error,
                    absolute_error=absolute_error,
                    details={
                        "tolerance": test_case.tolerance,
                        "category": test_case.category,
                    },
                )
            )

            status = "PASS" if passed else "FAIL"
            logger.info(
                f"  [{status}] {metric_name}: expected={expected_value:.4g}, "
                f"actual={actual_value:.4g}, error={relative_error*100:.2f}%"
            )

    except Exception as e:
        logger.error(f"  Error running test {test_case.name}: {e}")
        import traceback
        traceback.print_exc()

        # Create failure result for each expected metric
        for metric_name, expected_value in test_case.expected_results.items():
            results.append(
                ValidationResult(
                    test_name=f"{test_case.name}.{metric_name}",
                    passed=False,
                    expected=expected_value,
                    actual=float('nan'),
                    relative_error=float('nan'),
                    absolute_error=float('nan'),
                    details={"error": str(e)},
                )
            )

    return results


def run_validation_suite(
    base_configs: List[str] = None,
    test_cases: List[AnalyticalTestCase] = None,
    run_func: Optional[Callable] = None,
) -> ValidationSuiteResult:
    """Run complete analytical validation suite.

    Parameters
    ----------
    base_configs : List[str], optional
        Base configuration file paths. If None, uses default test configs.
    test_cases : List[AnalyticalTestCase], optional
        Custom test cases. If None, uses standard test suite.
    run_func : Callable, optional
        Custom optimization function.

    Returns
    -------
    ValidationSuiteResult
        Aggregate results from all tests
    """
    if test_cases is None:
        test_cases = create_standard_test_suite()

    if base_configs is None:
        # Use minimal test configuration
        base_configs = []
        logger.warning("No base configs provided, using default test configuration")

    all_results = []

    logger.info("=" * 60)
    logger.info("STARTING ANALYTICAL VALIDATION SUITE")
    logger.info(f"Number of test cases: {len(test_cases)}")
    logger.info("=" * 60)

    for test_case in test_cases:
        results = run_single_test(test_case, base_configs, run_func)
        all_results.extend(results)

    # Calculate summary statistics
    passed = sum(1 for r in all_results if r.passed)
    failed = len(all_results) - passed

    suite_result = ValidationSuiteResult(
        results=all_results,
        total_tests=len(all_results),
        passed_tests=passed,
        failed_tests=failed,
    )

    logger.info("\n" + suite_result.summary())

    return suite_result


def _extract_test_metrics(
    workflow_result: Any,
    metric_keys: List[str],
) -> Dict[str, float]:
    """Extract test metrics from workflow result.

    Parameters
    ----------
    workflow_result : WorkflowResult
        Result from run_workflow
    metric_keys : List[str]
        Names of metrics to extract

    Returns
    -------
    Dict[str, float]
        Extracted metric values
    """
    metrics = {}

    # Get the active result
    active_result = None
    if workflow_result.mpc_result:
        active_result = workflow_result.mpc_result
    elif workflow_result.rh_result:
        active_result = workflow_result.rh_result
    elif workflow_result.pf_result:
        active_result = workflow_result.pf_result

    if active_result is None:
        return metrics

    series = active_result.series if hasattr(active_result, 'series') else {}
    summary = active_result.summary if hasattr(active_result, 'summary') else {}

    # Extract based on metric name patterns
    for key in metric_keys:
        if key == "hp_electricity_mwh":
            # Sum all HP electricity consumption
            total = 0.0
            for hp_key in ["HP1_P_el_MW", "HP2_P_el_MW", "HP3_P_el_MW", "HP4_P_el_MW"]:
                if hp_key in series:
                    total += sum(series[hp_key])
            metrics[key] = total

        elif key == "total_heat_mwh":
            # Sum all heat output
            total = 0.0
            for heat_key in series:
                if heat_key.endswith("_Q_th_MW"):
                    total += sum(series[heat_key])
            metrics[key] = total

        elif key == "storage_discharged_mwh":
            if "TES_discharge_MW" in series:
                metrics[key] = sum(series["TES_discharge_MW"])

        elif key == "round_trip_efficiency":
            charged = sum(series.get("TES_charge_MW", [0]))
            discharged = sum(series.get("TES_discharge_MW", [0]))
            metrics[key] = discharged / charged if charged > 0 else 0.0

        elif key == "final_soc_mwh":
            if "TES_SOC_MWh" in series:
                metrics[key] = series["TES_SOC_MWh"][-1]

        elif key == "hp_output_mwh":
            total = 0.0
            for hp_key in ["HP1_Q_th_MW", "HP2_Q_th_MW", "HP3_Q_th_MW", "HP4_Q_th_MW"]:
                if hp_key in series:
                    total += sum(series[hp_key])
            metrics[key] = total

        elif key == "p2h_output_mwh":
            if "P2H_Q_th_MW" in series:
                metrics[key] = sum(series["P2H_Q_th_MW"])

        elif key == "p2h_electricity_mwh":
            if "P2H_P_el_MW" in series:
                metrics[key] = sum(series["P2H_P_el_MW"])

        elif key == "p2h_heat_mwh":
            if "P2H_Q_th_MW" in series:
                metrics[key] = sum(series["P2H_Q_th_MW"])

        elif key == "energy_balance_error":
            # Calculate energy balance
            demand = sum(series.get("demand_mw", [0]))
            generation = 0.0
            for gen_key in series:
                if gen_key.endswith("_Q_th_MW") or gen_key == "TES_discharge_MW":
                    generation += sum(series[gen_key])

            storage_net = sum(series.get("TES_charge_MW", [0])) - sum(series.get("TES_discharge_MW", [0]))
            dump = sum(series.get("dump_mw", [0]))

            # Energy balance: Generation = Demand + Storage_charge + Dump
            balance_error = abs(generation - demand - storage_net - dump) / max(demand, 1.0)
            metrics[key] = balance_error

    return metrics
