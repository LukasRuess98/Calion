"""Tests for energis.models.results — structured result containers."""

import pytest
from energis.models.results import (
    HeatPumpInvestment,
    StorageInvestment,
    InvestmentDecisions,
    ComponentSummary,
    _safe_float,
)


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

class TestSafeFloat:
    def test_none_returns_default(self):
        assert _safe_float(None) == 0.0

    def test_none_custom_default(self):
        assert _safe_float(None, 42.0) == 42.0

    def test_valid_int(self):
        assert _safe_float(5) == 5.0

    def test_valid_float(self):
        assert _safe_float(3.14) == 3.14

    def test_valid_string(self):
        assert _safe_float("2.5") == 2.5

    def test_invalid_string(self):
        assert _safe_float("abc") == 0.0

    def test_invalid_type(self):
        assert _safe_float([1, 2]) == 0.0


# ---------------------------------------------------------------------------
# HeatPumpInvestment
# ---------------------------------------------------------------------------

class TestHeatPumpInvestment:
    def test_creation(self):
        hp = HeatPumpInvestment(id="HP1", capacity_mw=10.0, build=True, build_binary=0.95)
        assert hp.id == "HP1"
        assert hp.capacity_mw == 10.0
        assert hp.build is True
        assert hp.build_binary == 0.95

    def test_enabled_property(self):
        hp_on = HeatPumpInvestment(id="HP1", capacity_mw=5.0, build=True, build_binary=1.0)
        hp_off = HeatPumpInvestment(id="HP2", capacity_mw=5.0, build=False, build_binary=0.0)
        assert hp_on.enabled is True
        assert hp_off.enabled is False


# ---------------------------------------------------------------------------
# StorageInvestment
# ---------------------------------------------------------------------------

class TestStorageInvestment:
    def test_creation(self):
        sto = StorageInvestment(name="TES", energy_mwh=100.0, power_mw=20.0, build=True, build_binary=1.0)
        assert sto.name == "TES"
        assert sto.energy_mwh == 100.0

    def test_enabled_property(self):
        sto = StorageInvestment(name="TES", energy_mwh=50.0, power_mw=10.0, build=False, build_binary=0.3)
        assert sto.enabled is False


# ---------------------------------------------------------------------------
# InvestmentDecisions
# ---------------------------------------------------------------------------

class TestInvestmentDecisions:
    def _make_decisions(self):
        hp = HeatPumpInvestment(id="HP1", capacity_mw=8.0, build=True, build_binary=0.9)
        sto = StorageInvestment(name="TES", energy_mwh=200.0, power_mw=40.0, build=True, build_binary=1.0)
        return InvestmentDecisions(heat_pumps={"HP1": hp}, storage=sto)

    def test_has_decisions_empty(self):
        dec = InvestmentDecisions()
        assert dec.has_decisions() is False

    def test_has_decisions_hp_only(self):
        hp = HeatPumpInvestment(id="HP1", capacity_mw=5.0, build=True, build_binary=1.0)
        dec = InvestmentDecisions(heat_pumps={"HP1": hp})
        assert dec.has_decisions() is True

    def test_has_decisions_storage_only(self):
        sto = StorageInvestment(name="TES", energy_mwh=50.0, power_mw=10.0, build=True, build_binary=1.0)
        dec = InvestmentDecisions(storage=sto)
        assert dec.has_decisions() is True

    def test_to_fixed_values(self):
        dec = self._make_decisions()
        fv = dec.to_fixed_values()
        assert "heat_pumps" in fv
        assert "HP1" in fv["heat_pumps"]
        assert fv["heat_pumps"]["HP1"]["capacity_mw"] == 8.0
        assert fv["heat_pumps"]["HP1"]["build"] is True
        assert fv["storage"]["energy_mwh"] == 200.0
        assert fv["storage"]["power_mw"] == 40.0

    def test_to_fixed_values_no_storage(self):
        hp = HeatPumpInvestment(id="HP1", capacity_mw=5.0, build=True, build_binary=1.0)
        dec = InvestmentDecisions(heat_pumps={"HP1": hp})
        fv = dec.to_fixed_values()
        assert fv["storage"] == {}

    def test_from_summary_heat_pumps(self):
        summary = {
            "heat_pump_HP1": {
                "Thermal_capacity_MW": 10.0,
                "Build_binary": 0.8,
            },
            "heat_pump_HP2": {
                "Thermal_capacity_MW": 5.0,
                "Build_binary": 0.3,
            },
        }
        dec = InvestmentDecisions.from_summary(summary)
        assert "HP1" in dec.heat_pumps
        assert "HP2" in dec.heat_pumps
        assert dec.heat_pumps["HP1"].build is True  # 0.8 >= 0.5
        assert dec.heat_pumps["HP2"].build is False  # 0.3 < 0.5
        assert dec.heat_pumps["HP1"].capacity_mw == 10.0

    def test_from_summary_storage(self):
        summary = {
            "storage_TES": {
                "Capacity_MWh": 200.0,
                "Power_limit_MW": 40.0,
                "Build_binary": 1.0,
            },
        }
        dec = InvestmentDecisions.from_summary(summary)
        assert dec.storage is not None
        assert dec.storage.name == "TES"
        assert dec.storage.energy_mwh == 200.0
        assert dec.storage.power_mw == 40.0

    def test_from_summary_fallback_build_key(self):
        summary = {
            "heat_pump_HP1": {
                "Thermal_capacity_MW": 10.0,
                "Build": 0.9,  # fallback key
            },
        }
        dec = InvestmentDecisions.from_summary(summary)
        assert dec.heat_pumps["HP1"].build_binary == 0.9

    def test_from_summary_skips_non_dict(self):
        summary = {
            "heat_pump_HP1": {"Thermal_capacity_MW": 10.0, "Build_binary": 1.0},
            "some_string": "not a dict",
        }
        dec = InvestmentDecisions.from_summary(summary)
        assert len(dec.heat_pumps) == 1

    def test_from_summary_empty(self):
        dec = InvestmentDecisions.from_summary({})
        assert dec.has_decisions() is False

    def test_to_design_spec(self):
        dec = self._make_decisions()
        spec = dec.to_design_spec()
        # Just verify it returns something with heat_pumps and storage
        assert hasattr(spec, "heat_pumps")
        assert hasattr(spec, "storage")


# ---------------------------------------------------------------------------
# ComponentSummary
# ---------------------------------------------------------------------------

class TestComponentSummary:
    def test_creation(self):
        cs = ComponentSummary(name="HP1", metrics={"COP": 3.5, "hours": 8760})
        assert cs.name == "HP1"

    def test_get(self):
        cs = ComponentSummary(name="HP1", metrics={"COP": 3.5})
        assert cs.get("COP") == 3.5
        assert cs.get("missing") is None
        assert cs.get("missing", 0.0) == 0.0

    def test_getitem(self):
        cs = ComponentSummary(name="HP1", metrics={"COP": 3.5})
        assert cs["COP"] == 3.5
        with pytest.raises(KeyError):
            _ = cs["missing"]
