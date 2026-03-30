"""Tests for calion.run.rh_engine – SOC helpers, param/cost-plan loading, series extension."""

import pytest

from calion.run.rh_engine import (
    _apply_terminal_policy,
    _extend_series,
    _initial_soc,
    _load_cost_plan,
    _load_rolling_params,
    _next_soc,
    _set_initial_soc,
    _storage_enabled,
)


# ---------------------------------------------------------------------------
# SOC helpers
# ---------------------------------------------------------------------------

class TestInitialSoc:
    def test_from_inputs(self):
        cfg = {"system": {"storage": {"enabled": True}}, "inputs": {"SOC_init": 5.0}}
        assert _initial_soc(cfg) == 5.0

    def test_from_storage_soc_init(self):
        cfg = {"system": {"storage": {"enabled": True, "SOC_init": 3.0}}}
        assert _initial_soc(cfg) == 3.0

    def test_from_soc0_mwh(self):
        cfg = {"system": {"storage": {"enabled": True, "soc0_mwh": 7.0}}}
        assert _initial_soc(cfg) == 7.0

    def test_default_zero_when_enabled(self):
        cfg = {"system": {"storage": {"enabled": True}}}
        assert _initial_soc(cfg) == 0.0

    def test_none_when_disabled(self):
        cfg = {"system": {"storage": {"enabled": False}}}
        assert _initial_soc(cfg) is None

    def test_none_when_no_storage(self):
        cfg = {"system": {}}
        assert _initial_soc(cfg) is None


class TestStorageEnabled:
    def test_enabled(self):
        assert _storage_enabled({"system": {"storage": {"enabled": True}}}) is True

    def test_disabled(self):
        assert _storage_enabled({"system": {"storage": {"enabled": False}}}) is False

    def test_missing(self):
        assert _storage_enabled({}) is False


class TestSetInitialSoc:
    def test_sets_in_all_locations(self):
        cfg = {"inputs": {}, "system": {"storage": {"terminal": {}}}}
        _set_initial_soc(cfg, 10.0)
        assert cfg["inputs"]["SOC_init"] == 10.0
        assert cfg["system"]["storage"]["soc0_mwh"] == 10.0
        assert cfg["system"]["storage"]["terminal"]["target_mwh"] == 10.0


class TestApplyTerminalPolicy:
    def test_free_policy(self):
        cfg = {"system": {"storage": {"terminal": {}}}}
        _apply_terminal_policy(cfg, "free")
        assert cfg["system"]["storage"]["terminal"]["policy"] == "free"
        assert cfg["system"]["storage"]["terminal"]["state"] == "free"

    def test_equal_policy(self):
        cfg = {"system": {"storage": {"terminal": {}}}}
        _apply_terminal_policy(cfg, "equal")
        assert cfg["system"]["storage"]["terminal"]["state"] == "cyclic"

    def test_empty_policy_noop(self):
        cfg = {"system": {"storage": {}}}
        _apply_terminal_policy(cfg, "")
        assert "terminal" not in cfg["system"]["storage"]


class TestNextSoc:
    def test_extracts_at_commit(self):
        series = {"TES_SOC_MWh": [1.0, 2.0, 3.0, 4.0]}
        assert _next_soc(series, commit_len=3, fallback=0.0) == 3.0

    def test_fallback_when_no_series(self):
        assert _next_soc({}, commit_len=3, fallback=5.0) == 5.0

    def test_fallback_when_zero_commit(self):
        series = {"TES_SOC_MWh": [1.0, 2.0]}
        assert _next_soc(series, commit_len=0, fallback=9.0) == 9.0

    def test_clamps_to_end(self):
        series = {"TES_SOC_MWh": [10.0, 20.0]}
        assert _next_soc(series, commit_len=100, fallback=0.0) == 20.0


# ---------------------------------------------------------------------------
# _extend_series
# ---------------------------------------------------------------------------

class TestExtendSeries:
    def test_basic_extend(self):
        gs = {"A": [1.0, 2.0]}
        ws = {"A": [3.0, 4.0, 5.0]}
        _extend_series(gs, ws, commit_len=2)
        assert gs["A"] == [1.0, 2.0, 3.0, 4.0]

    def test_pads_missing_columns(self):
        gs = {"A": [1.0], "B": [10.0]}
        ws = {"A": [2.0]}  # B missing in window
        _extend_series(gs, ws, commit_len=1)
        assert gs["B"] == [10.0, 0.0]

    def test_new_column_from_window(self):
        gs = {"A": [1.0]}
        ws = {"A": [2.0], "C": [99.0]}
        _extend_series(gs, ws, commit_len=1)
        assert gs["C"] == [99.0]

    def test_zero_commit_noop(self):
        gs = {"A": [1.0]}
        _extend_series(gs, {"A": [2.0]}, commit_len=0)
        assert gs["A"] == [1.0]

    def test_pads_short_window(self):
        gs = {"A": []}
        ws = {"A": [1.0]}
        _extend_series(gs, ws, commit_len=3)
        assert gs["A"] == [1.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# _load_rolling_params
# ---------------------------------------------------------------------------

class TestLoadRollingParams:
    def test_defaults(self):
        rp = _load_rolling_params({})
        assert rp.horizon_hours == 168.0
        assert rp.step_hours == 168.0
        assert rp.overlap_hours == 0.0

    def test_from_config(self):
        cfg = {"scenario": {"rolling_horizon": {
            "HEAT_HORIZON_HOURS": 48,
            "STEP_HOURS": 24,
            "OVERLAP_HOURS": 6,
            "terminal_policy": "recycle",
        }}}
        rp = _load_rolling_params(cfg)
        assert rp.horizon_hours == 48.0
        assert rp.step_hours == 24.0
        assert rp.overlap_hours == 6.0
        assert rp.terminal_policy == "recycle"

    def test_alternate_keys(self):
        cfg = {"scenario": {"rolling_horizon": {
            "window_hours": 72,
        }}}
        rp = _load_rolling_params(cfg)
        assert rp.horizon_hours == 72.0


# ---------------------------------------------------------------------------
# _load_cost_plan
# ---------------------------------------------------------------------------

class TestLoadCostPlan:
    def test_defaults_with_fix_design(self):
        plan = _load_cost_plan({}, fix_design=True)
        assert plan.include_investment is False

    def test_defaults_without_fix_design(self):
        plan = _load_cost_plan({}, fix_design=False)
        assert plan.include_investment is True

    def test_explicit_override(self):
        cfg = {"scenario": {"costs": {"include_investment_in_rh": True}}}
        plan = _load_cost_plan(cfg, fix_design=True)
        assert plan.include_investment is True

    def test_amortise_once_default(self):
        plan = _load_cost_plan({}, fix_design=False)
        assert plan.amortise_once is True
