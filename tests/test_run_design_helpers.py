"""Tests for calion.run.design_helpers."""

import json
import pytest

from calion.run.design_helpers import (
    _apply_design_fix,
    _design_from_mapping,
    _extract_design_data,
    _load_design_override,
)
from calion.run.types import DesignData


# ---------------------------------------------------------------------------
# _extract_design_data
# ---------------------------------------------------------------------------

class TestExtractDesignData:
    def test_extracts_heat_pump(self):
        summary = {
            "heat_pump_HP1": {"Thermal_capacity_MW": 5.0, "Build_binary": 1.0},
        }
        dd = _extract_design_data(summary)
        assert "HP1" in dd.heat_pumps
        assert dd.heat_pumps["HP1"]["capacity_mw"] == 5.0
        assert dd.heat_pumps["HP1"]["build_binary"] == 1.0

    def test_extracts_storage(self):
        summary = {
            "storage_TES": {"Capacity_MWh": 10.0, "Power_limit_MW": 2.0, "Build_binary": 1.0},
        }
        dd = _extract_design_data(summary)
        assert dd.storage is not None
        assert dd.storage["capacity_mwh"] == 10.0

    def test_no_design_sections(self):
        summary = {"objective": {"OBJ_value_EUR": 100.0}}
        dd = _extract_design_data(summary)
        assert dd.heat_pumps == {}
        assert dd.storage is None

    def test_multiple_heat_pumps(self):
        summary = {
            "heat_pump_A": {"Thermal_capacity_MW": 2.0, "Build_binary": 1.0},
            "heat_pump_B": {"Thermal_capacity_MW": 3.0, "Build_binary": 0.0},
        }
        dd = _extract_design_data(summary)
        assert len(dd.heat_pumps) == 2

    def test_fallback_to_build_key(self):
        summary = {
            "heat_pump_HP1": {"Thermal_capacity_MW": 1.0, "Build": 1.0},
        }
        dd = _extract_design_data(summary)
        assert dd.heat_pumps["HP1"]["build_binary"] == 1.0


# ---------------------------------------------------------------------------
# _design_from_mapping
# ---------------------------------------------------------------------------

class TestDesignFromMapping:
    def test_basic_roundtrip(self):
        data = {
            "heat_pumps": {"HP1": {"capacity_mw": 5.0, "build_binary": 1.0}},
            "storage": {"name": "TES", "capacity_mwh": 10.0, "power_mw": 2.0, "build_binary": 1.0},
        }
        dd = _design_from_mapping(data)
        assert dd.heat_pumps["HP1"]["capacity_mw"] == 5.0
        assert dd.storage["capacity_mwh"] == 10.0

    def test_empty_mapping(self):
        dd = _design_from_mapping({})
        assert dd.heat_pumps == {}
        assert dd.storage is None


# ---------------------------------------------------------------------------
# _load_design_override
# ---------------------------------------------------------------------------

class TestLoadDesignOverride:
    def test_no_path_returns_none(self):
        assert _load_design_override({}) is None

    def test_missing_file_returns_none(self):
        result = _load_design_override({"pf_design_json": "/nonexistent/file.json"})
        assert result is None

    def test_valid_file(self, tmp_path):
        data = {"heat_pumps": {"HP1": {"capacity_mw": 3.0, "build_binary": 1.0}}, "storage": None}
        p = tmp_path / "design.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = _load_design_override({"pf_design_json": str(p)})
        assert result is not None
        assert "HP1" in result.heat_pumps

    def test_non_mapping_file_returns_none(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("[1,2,3]", encoding="utf-8")
        result = _load_design_override({"pf_design_json": str(p)})
        assert result is None


# ---------------------------------------------------------------------------
# _apply_design_fix
# ---------------------------------------------------------------------------

class TestApplyDesignFix:
    def _base_cfg(self):
        return {
            "system": {
                "heat_pumps": [
                    {"id": "HP1", "max_th_mw": 10.0, "min_th_mw": 0.0, "enabled": True,
                     "investment": {"enabled": True}},
                ],
                "storage": {
                    "enabled": True,
                    "max_energy_mwh": 50.0,
                    "max_power_mw": 10.0,
                    "investment": {"enabled": True},
                },
            }
        }

    def test_fixes_hp_capacity(self):
        design = DesignData(
            heat_pumps={"HP1": {"capacity_mw": 5.0, "build_binary": 1.0}},
            storage=None,
        )
        result = _apply_design_fix(self._base_cfg(), design)
        hp = result["system"]["heat_pumps"][0]
        assert hp["max_th_mw"] == 5.0
        assert hp["min_th_mw"] == 5.0
        assert hp["enabled"] is True
        assert hp["investment"]["enabled"] is False

    def test_disables_hp_below_threshold(self):
        design = DesignData(
            heat_pumps={"HP1": {"capacity_mw": 0.0, "build_binary": 0.0}},
            storage=None,
        )
        result = _apply_design_fix(self._base_cfg(), design)
        assert result["system"]["heat_pumps"][0]["enabled"] is False

    def test_fixes_storage(self):
        design = DesignData(
            heat_pumps={},
            storage={"name": "TES", "capacity_mwh": 20.0, "power_mw": 5.0, "build_binary": 1.0},
        )
        result = _apply_design_fix(self._base_cfg(), design)
        sto = result["system"]["storage"]
        assert sto["max_energy_mwh"] == 20.0
        assert sto["max_power_mw"] == 5.0
        assert sto["investment"]["enabled"] is False

    def test_does_not_mutate_original(self):
        cfg = self._base_cfg()
        design = DesignData(
            heat_pumps={"HP1": {"capacity_mw": 3.0, "build_binary": 1.0}},
            storage=None,
        )
        _apply_design_fix(cfg, design)
        assert cfg["system"]["heat_pumps"][0]["max_th_mw"] == 10.0  # unchanged

    def test_storage_power_fallback(self):
        design = DesignData(
            heat_pumps={},
            storage={"name": "TES", "capacity_mwh": 20.0, "power_mw": 0.0, "build_binary": 1.0},
        )
        result = _apply_design_fix(self._base_cfg(), design)
        assert result["system"]["storage"]["max_power_mw"] == 5.0  # 20 * 0.25
