"""Tests for calion.utils.config_utils — config normalization helpers."""

import pytest
from calion.utils.config_utils import (
    apply_heat_pump_defaults,
    _normalize_heat_pump_config,
    normalize_storage_config,
    normalize_thermal_network_config,
    resolve_heating_curve_profile,
    _DEFAULT_HEATING_CURVES,
)


# ---------------------------------------------------------------------------
# apply_heat_pump_defaults
# ---------------------------------------------------------------------------

class TestApplyHeatPumpDefaults:
    def test_empty_list(self):
        assert apply_heat_pump_defaults({"heat_pumps": []}) == []

    def test_no_heat_pumps_key(self):
        assert apply_heat_pump_defaults({}) == []

    def test_non_list(self):
        assert apply_heat_pump_defaults({"heat_pumps": "not_a_list"}) == []

    def test_no_defaults(self):
        cfg = {"heat_pumps": [{"id": "HP1", "capacity_mw": 10.0}]}
        result = apply_heat_pump_defaults(cfg)
        assert len(result) == 1
        assert result[0]["id"] == "HP1"

    def test_defaults_applied(self):
        cfg = {
            "heat_pump_defaults": {"cop_default": 3.5, "enabled": True},
            "heat_pumps": [{"id": "HP1", "capacity_mw": 10.0}],
        }
        result = apply_heat_pump_defaults(cfg)
        assert result[0]["cop_default"] == 3.5
        assert result[0]["capacity_mw"] == 10.0

    def test_entry_overrides_default(self):
        cfg = {
            "heat_pump_defaults": {"cop_default": 3.5},
            "heat_pumps": [{"id": "HP1", "cop_default": 4.0}],
        }
        result = apply_heat_pump_defaults(cfg)
        assert result[0]["cop_default"] == 4.0

    def test_skips_non_mapping_entries(self):
        cfg = {"heat_pumps": [{"id": "HP1"}, "not_a_dict", 42]}
        result = apply_heat_pump_defaults(cfg)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _normalize_heat_pump_config
# ---------------------------------------------------------------------------

class TestNormalizeHeatPumpConfig:
    def test_old_format_passthrough(self):
        cfg = {"id": "HP1", "max_th_mw": 10.0}
        result = _normalize_heat_pump_config(cfg)
        assert result["max_th_mw"] == 10.0

    def test_new_format_technical_limits(self):
        cfg = {
            "id": "HP1",
            "technical_limits": {"capacity_min_mw": 1.0, "capacity_max_mw": 10.0},
        }
        result = _normalize_heat_pump_config(cfg)
        assert result["min_th_mw"] == 1.0
        assert result["max_th_mw"] == 10.0
        assert result["investment"]["capacity_min_mw"] == 1.0
        assert result["investment"]["capacity_max_mw"] == 10.0

    def test_new_format_defaults(self):
        cfg = {
            "id": "HP1",
            "defaults": {"capacity_mw": 5.0, "build": True},
        }
        result = _normalize_heat_pump_config(cfg)
        assert result["max_th_mw"] == 5.0
        assert result["investment"]["initial_capacity_mw"] == 5.0

    def test_new_format_costs(self):
        cfg = {
            "id": "HP1",
            "costs": {
                "capex_eur_per_mw": 500000,
                "activation_cost_eur": 10000,
                "lifetime_years": 25,
            },
        }
        result = _normalize_heat_pump_config(cfg)
        assert result["investment"]["capex_eur_per_mw"] == 500000
        assert result["investment"]["activation_cost_eur"] == 10000
        assert result["investment"]["lifetime_years"] == 25


# ---------------------------------------------------------------------------
# normalize_storage_config
# ---------------------------------------------------------------------------

class TestNormalizeStorageConfig:
    def test_old_format_passthrough(self):
        cfg = {"energy_mwh": 100.0, "power_mw": 20.0}
        result = normalize_storage_config(cfg)
        assert result["energy_mwh"] == 100.0

    def test_new_format_tech_limits(self):
        cfg = {
            "technical_limits": {
                "energy_min_mwh": 10.0,
                "energy_max_mwh": 500.0,
                "power_min_mw": 5.0,
                "power_max_mw": 100.0,
            },
        }
        result = normalize_storage_config(cfg)
        assert result["min_energy_mwh"] == 10.0
        assert result["max_energy_mwh"] == 500.0
        assert result["investment"]["energy_capacity_min_mwh"] == 10.0

    def test_new_format_defaults(self):
        cfg = {
            "defaults": {"energy_mwh": 200.0, "power_mw": 40.0},
        }
        result = normalize_storage_config(cfg)
        assert result["max_energy_mwh"] == 200.0
        assert result["max_power_mw"] == 40.0

    def test_new_format_costs(self):
        cfg = {
            "costs": {
                "energy_capex_eur_per_mwh": 30000,
                "power_capex_eur_per_mw": 100000,
                "activation_cost_eur": 5000,
                "lifetime_years": 30,
            },
        }
        result = normalize_storage_config(cfg)
        inv = result["investment"]
        assert inv["energy_capex_eur_per_mwh"] == 30000
        assert inv["power_capex_eur_per_mw"] == 100000


# ---------------------------------------------------------------------------
# normalize_thermal_network_config
# ---------------------------------------------------------------------------

class TestNormalizeThermalNetworkConfig:
    def test_empty_config(self):
        result = normalize_thermal_network_config({})
        assert result["enabled"] is False

    def test_old_format(self):
        cfg = {"thermal_network": {"enabled": True, "topology_file": "net.yaml"}}
        result = normalize_thermal_network_config(cfg)
        assert result["enabled"] is True
        assert result["topology_file"] == "net.yaml"

    def test_new_format_defaults(self):
        cfg = {
            "system": {
                "thermal_network": {
                    "enabled": True,
                    "defaults": {
                        "supply_temp_c": 90.0,
                        "return_temp_c": 50.0,
                        "ground_temp_c": 10.0,
                    },
                }
            }
        }
        result = normalize_thermal_network_config(cfg)
        assert result["parameters"]["supply_temp_nominal_c"] == 90.0
        assert result["parameters"]["return_temp_nominal_c"] == 50.0

    def test_new_format_tech_limits(self):
        cfg = {
            "system": {
                "thermal_network": {
                    "enabled": True,
                    "technical_limits": {"max_velocity_m_s": 3.0, "max_pressure_bar": 10.0},
                }
            }
        }
        result = normalize_thermal_network_config(cfg)
        assert result["parameters"]["max_velocity_m_s"] == 3.0

    def test_old_overrides_new(self):
        cfg = {
            "system": {"thermal_network": {"enabled": False}},
            "thermal_network": {"enabled": True},
        }
        result = normalize_thermal_network_config(cfg)
        assert result["enabled"] is True


# ---------------------------------------------------------------------------
# resolve_heating_curve_profile
# ---------------------------------------------------------------------------

class TestResolveHeatingCurveProfile:
    def test_non_mapping(self):
        assert resolve_heating_curve_profile("not_a_dict") == {}
        assert resolve_heating_curve_profile(None) == {}

    def test_inline_values_preserved(self):
        cfg = {"T_supply_min_c": 80.0, "T_supply_max_c": 120.0}
        result = resolve_heating_curve_profile(cfg)
        assert result["T_supply_min_c"] == 80.0

    def test_known_profile(self):
        cfg = {"enabled": True, "profile": "standard_dh"}
        result = resolve_heating_curve_profile(cfg)
        assert result["T_supply_min_c"] == 80.0
        assert result["T_supply_max_c"] == 120.0
        assert "profile" not in result  # popped

    def test_inline_overrides_profile(self):
        # If inline values are present, profile is not looked up
        cfg = {"profile": "standard_dh", "T_supply_min_c": 70.0}
        result = resolve_heating_curve_profile(cfg)
        assert result["T_supply_min_c"] == 70.0
