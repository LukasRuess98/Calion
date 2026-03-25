"""Tests for energis.run.result_collector – small helpers only."""

import pytest

from energis.run.result_collector import (
    _as_float,
    _extract_design_from_summary,
    _flatten_summary,
    _json_safe,
)


# ---------------------------------------------------------------------------
# _json_safe
# ---------------------------------------------------------------------------

class TestJsonSafe:
    def test_primitives_passthrough(self):
        assert _json_safe("hello") == "hello"
        assert _json_safe(42) == 42
        assert _json_safe(3.14) == 3.14
        assert _json_safe(True) is True
        assert _json_safe(None) is None

    def test_dict_recurse(self):
        assert _json_safe({"a": 1, "b": {"c": 2}}) == {"a": 1, "b": {"c": 2}}

    def test_list_recurse(self):
        assert _json_safe([1, "x", [2]]) == [1, "x", [2]]

    def test_unknown_type_to_str(self):
        result = _json_safe(object())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _flatten_summary
# ---------------------------------------------------------------------------

class TestFlattenSummary:
    def test_basic(self):
        sections = {
            "objective": {"OBJ_value_EUR": 100.0},
            "heat_pump_HP1": {"Thermal_capacity_MW": 5.0},
        }
        flat = _flatten_summary(sections)
        assert flat["objective.OBJ_value_EUR"] == 100.0
        assert flat["heat_pump_HP1.Thermal_capacity_MW"] == 5.0

    def test_empty(self):
        assert _flatten_summary({}) == {}


# ---------------------------------------------------------------------------
# _as_float
# ---------------------------------------------------------------------------

class TestAsFloat:
    def test_numeric(self):
        assert _as_float(3.14) == pytest.approx(3.14)
        assert _as_float(42) == 42.0

    def test_string_numeric(self):
        assert _as_float("2.5") == 2.5

    def test_invalid_returns_zero(self):
        assert _as_float("abc") == 0.0
        assert _as_float(None) == 0.0


# ---------------------------------------------------------------------------
# _extract_design_from_summary
# ---------------------------------------------------------------------------

class TestExtractDesignFromSummary:
    def test_extracts_hp_and_storage(self):
        summary = {
            "heat_pump_HP1": {"Thermal_capacity_MW": 5.0, "Build_binary": 1.0},
            "storage_TES": {"Capacity_MWh": 20.0, "Power_limit_MW": 5.0, "Build_binary": 1.0},
            "objective": {"OBJ_value_EUR": 999.0},
        }
        design = _extract_design_from_summary(summary)
        assert "HP1" in design["heat_pumps"]
        assert design["heat_pumps"]["HP1"]["capacity_mw"] == 5.0
        assert design["storage"] is not None
        assert design["storage"]["capacity_mwh"] == 20.0

    def test_no_design_sections(self):
        design = _extract_design_from_summary({"objective": {"x": 1}})
        assert design["heat_pumps"] == {}
        assert design["storage"] is None

    def test_non_mapping_metrics_skipped(self):
        design = _extract_design_from_summary({"heat_pump_X": "not_a_dict"})
        assert design["heat_pumps"] == {}
