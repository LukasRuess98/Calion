"""Tests for energis.run.workflow – plan parsing, step registry, sensitivity expansion."""

import pytest

from energis.run.workflow import (
    _parse_workflow_plan,
    get_registered_workflow_steps,
    register_workflow_step,
    unregister_workflow_step,
)


# ---------------------------------------------------------------------------
# Step registry
# ---------------------------------------------------------------------------

class TestStepRegistry:
    def test_register_and_list(self):
        handler = lambda ctx: None  # noqa: E731
        register_workflow_step("TEST_STEP", handler)
        assert "TEST_STEP" in get_registered_workflow_steps()
        unregister_workflow_step("TEST_STEP")

    def test_unregister(self):
        handler = lambda ctx: None  # noqa: E731
        register_workflow_step("TEMP_STEP", handler)
        unregister_workflow_step("TEMP_STEP")
        assert "TEMP_STEP" not in get_registered_workflow_steps()

    def test_unregister_nonexistent_noop(self):
        unregister_workflow_step("NONEXISTENT_STEP_XYZ")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            register_workflow_step("", lambda ctx: None)

    def test_case_normalisation(self):
        handler = lambda ctx: None  # noqa: E731
        register_workflow_step("lower_case", handler)
        assert "LOWER_CASE" in get_registered_workflow_steps()
        unregister_workflow_step("lower_case")


# ---------------------------------------------------------------------------
# _parse_workflow_plan
# ---------------------------------------------------------------------------

class TestParseWorkflowPlan:
    def test_default_pf_only(self):
        plan = _parse_workflow_plan({})
        assert plan.steps == ["PF"]

    def test_explicit_run_mode_rh(self):
        plan = _parse_workflow_plan({"run_mode": "RH_ONLY"})
        assert plan.steps == ["RH"]

    def test_pf_then_rh(self):
        plan = _parse_workflow_plan({"run_mode": "PF_THEN_RH"})
        assert plan.steps == ["PF", "RH"]
        assert plan.fix_design is True

    def test_explicit_workflow_list(self):
        plan = _parse_workflow_plan({"workflow": ["PF", "RH", "MPC"]})
        assert plan.steps == ["PF", "RH", "MPC"]

    def test_workflow_single_string(self):
        plan = _parse_workflow_plan({"workflow": "PF"})
        assert plan.steps == ["PF"]

    def test_fix_design_override(self):
        plan = _parse_workflow_plan({"run_mode": "PF_ONLY", "fix_design": True})
        assert plan.fix_design is True

    def test_mpc_only(self):
        plan = _parse_workflow_plan({"run_mode": "MPC_ONLY"})
        assert plan.steps == ["MPC"]

    def test_pf_then_mpc(self):
        plan = _parse_workflow_plan({"run_mode": "PF_THEN_MPC"})
        assert plan.steps == ["PF", "MPC"]
        assert plan.fix_design is True

    def test_empty_workflow_raises(self):
        with pytest.raises(ValueError, match="at least one step"):
            _parse_workflow_plan({"workflow": []})

    def test_unknown_run_mode_defaults_pf(self):
        plan = _parse_workflow_plan({"run_mode": "UNKNOWN"})
        assert plan.steps == ["PF"]

    def test_design_config_present(self):
        plan = _parse_workflow_plan({"run_mode": "PF_THEN_RH"})
        assert plan.design_config is not None
