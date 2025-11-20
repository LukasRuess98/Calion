"""Basic tests for MPC implementation."""

import pytest
from energis.forecasting.base import ForecastGenerator
from energis.forecasting.persistence import PersistenceForecast
from energis.forecasting.perfect_noise import PerfectNoiseForecast


def test_forecast_generator_interface():
    """Test that forecast generators implement the interface correctly."""

    # Test Persistence
    gen = PersistenceForecast({})
    assert isinstance(gen, ForecastGenerator)
    assert gen.get_method_name() == "Persistence (Naive)"

    # Test Perfect+Noise
    gen = PerfectNoiseForecast({"scenario": {"mpc": {"noise_std_dev": 0.10}}})
    assert isinstance(gen, ForecastGenerator)
    assert "Noise" in gen.get_method_name()
    assert "10%" in gen.get_method_name()


def test_mpc_workflow_registration():
    """Test that MPC workflow step is registered."""
    from energis.run.rolling_horizon import get_registered_workflow_steps

    steps = get_registered_workflow_steps()
    assert "MPC" in steps
    assert "PF" in steps
    assert "RH" in steps


def test_workflow_result_has_mpc_field():
    """Ensure WorkflowResult has mpc_result field."""
    from energis.run.rolling_horizon import WorkflowResult

    result = WorkflowResult(
        config={},
        pf_result=None,
        rh_result=None,
        mpc_result=None,  # Should not raise error
        design=None,
        plan=None
    )

    assert hasattr(result, 'mpc_result')
    assert hasattr(result, 'pf_result')
    assert hasattr(result, 'rh_result')


def test_workflow_context_has_mpc_field():
    """Ensure WorkflowContext has mpc_result field."""
    from energis.run.rolling_horizon import WorkflowContext, WorkflowPlan

    context = WorkflowContext(
        cfg={},
        table=None,
        dt_h=1.0,
        solver_name="glpk",
        plan=WorkflowPlan(steps=["MPC"], fix_design=False),
        mpc_result=None,  # Should not raise error
    )

    assert hasattr(context, 'mpc_result')
    assert hasattr(context, 'pf_result')
    assert hasattr(context, 'rh_result')


def test_mpc_run_modes():
    """Test that MPC run modes are recognized."""
    from energis.run.rolling_horizon import _parse_workflow_plan

    # Test MPC_ONLY
    plan = _parse_workflow_plan({"run_mode": "MPC_ONLY"})
    assert plan.steps == ["MPC"]

    # Test PF_THEN_MPC
    plan = _parse_workflow_plan({"run_mode": "PF_THEN_MPC"})
    assert plan.steps == ["PF", "MPC"]

    # Test explicit workflow
    plan = _parse_workflow_plan({"workflow": ["MPC"]})
    assert plan.steps == ["MPC"]

    plan = _parse_workflow_plan({"workflow": ["PF", "MPC"]})
    assert plan.steps == ["PF", "MPC"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
