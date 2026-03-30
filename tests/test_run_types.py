"""Tests for calion.run.types – _RollingParams and _CostAggregationPlan."""

import pytest

from calion.run.types import _CostAggregationPlan, _RollingParams


# ---------------------------------------------------------------------------
# _RollingParams.as_steps
# ---------------------------------------------------------------------------

class TestRollingParamsAsSteps:
    def test_basic_conversion(self):
        rp = _RollingParams(horizon_hours=24, step_hours=6, overlap_hours=2, terminal_policy="recycle")
        h, s, o = rp.as_steps(dt_h=1.0)
        assert (h, s, o) == (24, 6, 2)

    def test_fractional_dt(self):
        rp = _RollingParams(horizon_hours=12, step_hours=6, overlap_hours=3, terminal_policy="recycle")
        h, s, o = rp.as_steps(dt_h=0.25)
        assert (h, s, o) == (48, 24, 12)

    def test_zero_overlap(self):
        rp = _RollingParams(horizon_hours=24, step_hours=12, overlap_hours=0, terminal_policy="recycle")
        h, s, o = rp.as_steps(dt_h=1.0)
        assert o == 0

    def test_dt_zero_raises(self):
        rp = _RollingParams(horizon_hours=24, step_hours=6, overlap_hours=0, terminal_policy="recycle")
        with pytest.raises(ValueError, match="dt_h must be positive"):
            rp.as_steps(dt_h=0)

    def test_dt_negative_raises(self):
        rp = _RollingParams(horizon_hours=24, step_hours=6, overlap_hours=0, terminal_policy="recycle")
        with pytest.raises(ValueError, match="dt_h must be positive"):
            rp.as_steps(dt_h=-1)

    def test_step_exceeds_horizon_raises(self):
        rp = _RollingParams(horizon_hours=6, step_hours=24, overlap_hours=0, terminal_policy="recycle")
        with pytest.raises(ValueError, match="STEP_HOURS must not exceed"):
            rp.as_steps(dt_h=1.0)

    def test_overlap_ge_step_raises(self):
        rp = _RollingParams(horizon_hours=24, step_hours=6, overlap_hours=6, terminal_policy="recycle")
        with pytest.raises(ValueError, match="OVERLAP_HOURS must be smaller"):
            rp.as_steps(dt_h=1.0)


# ---------------------------------------------------------------------------
# _CostAggregationPlan.investment_active
# ---------------------------------------------------------------------------

class TestCostAggregationPlan:
    def _make(self, include_investment=True, amortise_once=True):
        return _CostAggregationPlan(
            include_investment=include_investment,
            amortise_once=amortise_once,
            include_tie_breaker=True,
            include_installation=True,
            include_activation=True,
        )

    def test_investment_active_first_window(self):
        plan = self._make(include_investment=True, amortise_once=True)
        assert plan.investment_active(0) is True

    def test_investment_not_included(self):
        plan = self._make(include_investment=False)
        assert plan.investment_active(0) is False
        assert plan.investment_active(1) is False

    def test_amortise_once_blocks_later_windows(self):
        plan = self._make(include_investment=True, amortise_once=True)
        assert plan.investment_active(0) is True
        assert plan.investment_active(1) is False
        assert plan.investment_active(5) is False

    def test_amortise_every_window(self):
        plan = self._make(include_investment=True, amortise_once=False)
        assert plan.investment_active(0) is True
        assert plan.investment_active(1) is True
        assert plan.investment_active(5) is True
