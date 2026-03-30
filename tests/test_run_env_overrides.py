"""Tests for energis.run.utilities.env_overrides."""

import argparse

import pytest

from energis.run.utilities.env_overrides import (
    _env_bool,
    _env_float,
    _env_str,
    _gather_env_overrides,
    _normalise_run_mode,
    _parse_float_list,
    _parse_run_mode,
)


# ---------------------------------------------------------------------------
# _env_str
# ---------------------------------------------------------------------------

class TestEnvStr:
    def test_reads_value(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert _env_str("TEST_VAR") == "hello"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "  value  ")
        assert _env_str("TEST_VAR") == "value"

    def test_unset_returns_none(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        assert _env_str("TEST_VAR") is None

    def test_empty_returns_none(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "")
        assert _env_str("TEST_VAR") is None


# ---------------------------------------------------------------------------
# _env_float
# ---------------------------------------------------------------------------

class TestEnvFloat:
    def test_parses_float(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "3.14")
        assert _env_float("TEST_VAR") == pytest.approx(3.14)

    def test_unset_returns_none(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        assert _env_float("TEST_VAR") is None

    def test_invalid_raises(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "abc")
        with pytest.raises(ValueError, match="Invalid float"):
            _env_float("TEST_VAR")


# ---------------------------------------------------------------------------
# _env_bool
# ---------------------------------------------------------------------------

class TestEnvBool:
    @pytest.mark.parametrize("raw,expected", [
        ("1", True), ("true", True), ("yes", True), ("on", True),
        ("0", False), ("false", False), ("no", False), ("off", False),
        ("TRUE", True), ("FALSE", False),
    ])
    def test_valid_values(self, monkeypatch, raw, expected):
        monkeypatch.setenv("TEST_VAR", raw)
        assert _env_bool("TEST_VAR") is expected

    def test_unset_returns_none(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        assert _env_bool("TEST_VAR") is None

    def test_invalid_raises(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "maybe")
        with pytest.raises(ValueError, match="Invalid boolean"):
            _env_bool("TEST_VAR")


# ---------------------------------------------------------------------------
# _parse_float_list
# ---------------------------------------------------------------------------

class TestParseFloatList:
    def test_comma_separated(self):
        assert _parse_float_list("24.0,48.0,72.0") == [24.0, 48.0, 72.0]

    def test_semicolon_separated(self):
        assert _parse_float_list("1.0;2.5;3.0") == [1.0, 2.5, 3.0]

    def test_single_value(self):
        assert _parse_float_list("42") == [42.0]


# ---------------------------------------------------------------------------
# _normalise_run_mode
# ---------------------------------------------------------------------------

class TestNormaliseRunMode:
    def test_pf_alias(self):
        assert _normalise_run_mode("PF") == "PF_ONLY"

    def test_rh_alias(self):
        assert _normalise_run_mode("RH") == "RH_ONLY"

    def test_pf_and_rh_alias(self):
        assert _normalise_run_mode("PF_AND_RH") == "PF_THEN_RH"

    def test_case_insensitive(self):
        assert _normalise_run_mode("pf") == "PF_ONLY"

    def test_none_returns_none(self):
        assert _normalise_run_mode(None) is None

    def test_empty_returns_none(self):
        assert _normalise_run_mode("") is None

    def test_unknown_returns_none(self):
        assert _normalise_run_mode("INVALID") is None


# ---------------------------------------------------------------------------
# _parse_run_mode (argparse type handler)
# ---------------------------------------------------------------------------

class TestParseRunMode:
    def test_valid(self):
        assert _parse_run_mode("PF") == "PF_ONLY"

    def test_invalid_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Unknown run mode"):
            _parse_run_mode("INVALID")


# ---------------------------------------------------------------------------
# _gather_env_overrides
# ---------------------------------------------------------------------------

class TestGatherEnvOverrides:
    def test_clean_environment(self, monkeypatch):
        for var in ["RUN_MODE", "HEAT_HORIZON_HOURS", "STEP_HOURS", "OVERLAP_HOURS",
                     "TERMINAL_POLICY", "FIX_DESIGN", "INCLUDE_GRIDCOST_IN_ENERGY",
                     "INCLUDE_DEMAND_CHARGE_IN_RH", "INCLUDE_CO2_COST_IN_OBJECTIVE",
                     "PF_DESIGN_JSON"]:
            monkeypatch.delenv(var, raising=False)
        ov = _gather_env_overrides()
        assert ov.run_mode is None
        assert ov.horizon_hours is None

    def test_picks_up_values(self, monkeypatch):
        monkeypatch.setenv("RUN_MODE", "PF")
        monkeypatch.setenv("HEAT_HORIZON_HOURS", "48")
        monkeypatch.setenv("FIX_DESIGN", "true")
        for var in ["STEP_HOURS", "OVERLAP_HOURS", "TERMINAL_POLICY",
                     "INCLUDE_GRIDCOST_IN_ENERGY", "INCLUDE_DEMAND_CHARGE_IN_RH",
                     "INCLUDE_CO2_COST_IN_OBJECTIVE", "PF_DESIGN_JSON"]:
            monkeypatch.delenv(var, raising=False)
        ov = _gather_env_overrides()
        assert ov.run_mode == "PF_ONLY"
        assert ov.horizon_hours == 48.0
        assert ov.fix_design is True
