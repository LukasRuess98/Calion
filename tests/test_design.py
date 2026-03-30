"""Tests for calion.design — OptimizationConfig loading, extraction, and legacy DesignSpec."""

import pytest

from calion.design import (
    DesignSpec,
    FixedValues,
    HeatPumpDesign,
    OptimizationConfig,
    OptimizationVariables,
    StorageDesign,
    apply_design_to_config,
    convert_to_design_spec,
    extract_optimization_results,
    load_optimization_config,
    save_optimization_results,
    validate_design,
)


# ---------------------------------------------------------------------------
# load_optimization_config
# ---------------------------------------------------------------------------

class TestLoadOptimizationConfig:
    def test_empty_config_returns_defaults(self):
        cfg = load_optimization_config({})
        assert isinstance(cfg, OptimizationConfig)
        assert cfg.fix_after_window is None
        assert cfg.fixed_values is None
        assert cfg.variables.hp_capacity is True

    def test_legacy_fix_design_flag(self):
        cfg = load_optimization_config({"fix_design": True})
        assert cfg.fix_after_window == 0
        assert cfg.variables.hp_capacity is True

    def test_full_optimization_section(self):
        scenario = {
            "optimization": {
                "variables": {
                    "heat_pumps": {"capacity": False, "build": True},
                    "storage": {"capacity": True, "power": False, "build": True},
                },
                "fix_after_window": 2,
                "save_result_to": "outputs/opt_result.yaml",
            }
        }
        cfg = load_optimization_config(scenario)
        assert cfg.variables.hp_capacity is False
        assert cfg.variables.hp_build is True
        assert cfg.variables.storage_power is False
        assert cfg.fix_after_window == 2
        assert cfg.save_result_to == "outputs/opt_result.yaml"

    def test_fixed_values_parsed(self):
        scenario = {
            "optimization": {
                "fixed_values": {
                    "heat_pumps": {"HP1": {"capacity_mw": 5.0}},
                    "storage": {"energy_mwh": 200.0},
                }
            }
        }
        cfg = load_optimization_config(scenario)
        assert cfg.fixed_values is not None
        assert cfg.fixed_values.heat_pumps["HP1"]["capacity_mw"] == 5.0
        assert cfg.fixed_values.storage["energy_mwh"] == 200.0


# ---------------------------------------------------------------------------
# extract_optimization_results
# ---------------------------------------------------------------------------

class TestExtractOptimizationResults:
    def test_empty_summary(self):
        results = extract_optimization_results({})
        assert results == {"heat_pumps": {}, "storage": {}}

    def test_heat_pump_extraction(self):
        summary = {
            "heat_pump_HP1": {
                "Thermal_capacity_MW": 8.5,
                "Build_binary": 1.0,
            }
        }
        results = extract_optimization_results(summary)
        assert "HP1" in results["heat_pumps"]
        assert results["heat_pumps"]["HP1"]["capacity_mw"] == pytest.approx(8.5)
        assert results["heat_pumps"]["HP1"]["build"] is True

    def test_storage_extraction(self):
        summary = {
            "storage_TES": {
                "Capacity_MWh": 200.0,
                "Power_limit_MW": 40.0,
                "Build_binary": 1.0,
            }
        }
        results = extract_optimization_results(summary)
        assert results["storage"]["energy_mwh"] == pytest.approx(200.0)
        assert results["storage"]["power_mw"] == pytest.approx(40.0)
        assert results["storage"]["build"] is True

    def test_build_false_when_binary_zero(self):
        summary = {
            "heat_pump_HP1": {
                "Thermal_capacity_MW": 0.0,
                "Build_binary": 0.0,
            }
        }
        results = extract_optimization_results(summary)
        assert results["heat_pumps"]["HP1"]["build"] is False


# ---------------------------------------------------------------------------
# save_optimization_results
# ---------------------------------------------------------------------------

class TestSaveOptimizationResults:
    def test_roundtrip(self, tmp_path):
        import yaml

        results = {
            "heat_pumps": {"HP1": {"capacity_mw": 5.0, "build": True}},
            "storage": {"energy_mwh": 100.0, "power_mw": 20.0, "build": True},
        }
        path = tmp_path / "opt_results.yaml"
        saved = save_optimization_results(results, path)
        assert saved == path
        assert path.exists()

        with open(path) as f:
            data = yaml.safe_load(f)

        assert data["optimization"]["fixed_values"]["heat_pumps"]["HP1"]["capacity_mw"] == 5.0

    def test_creates_parent_dirs(self, tmp_path):
        results = {"heat_pumps": {}, "storage": {}}
        path = tmp_path / "nested" / "deep" / "result.yaml"
        save_optimization_results(results, path)
        assert path.exists()


# ---------------------------------------------------------------------------
# convert_to_design_spec
# ---------------------------------------------------------------------------

class TestConvertToDesignSpec:
    def test_with_heat_pump_and_storage(self):
        results = {
            "heat_pumps": {"HP1": {"capacity_mw": 6.0, "build": True}},
            "storage": {"energy_mwh": 150.0, "power_mw": 30.0, "build": True},
        }
        spec = convert_to_design_spec(results)
        assert "HP1" in spec.heat_pumps
        assert spec.heat_pumps["HP1"].capacity_mw == pytest.approx(6.0)
        assert spec.heat_pumps["HP1"].enabled is True
        assert spec.storage is not None
        assert spec.storage.capacity_mwh == pytest.approx(150.0)

    def test_empty_results(self):
        spec = convert_to_design_spec({"heat_pumps": {}, "storage": {}})
        assert spec.heat_pumps == {}
        assert spec.storage is None


# ---------------------------------------------------------------------------
# apply_design_to_config
# ---------------------------------------------------------------------------

class TestApplyDesignToConfig:
    def _make_cfg(self):
        return {
            "system": {
                "heat_pumps": [
                    {"id": "HP1", "max_th_mw": 10.0, "investment": {"enabled": True}},
                ],
                "storage": {
                    "enabled": True,
                    "max_energy_mwh": 300.0,
                    "max_power_mw": 60.0,
                    "investment": {"enabled": True},
                },
            }
        }

    def test_heat_pump_capacity_fixed(self):
        design = DesignSpec(
            heat_pumps={"HP1": HeatPumpDesign(id="HP1", capacity_mw=5.0, enabled=True)}
        )
        cfg_out = apply_design_to_config(self._make_cfg(), design)
        hp = cfg_out["system"]["heat_pumps"][0]
        assert hp["investment"]["enabled"] is False
        assert hp["max_th_mw"] == pytest.approx(5.0)

    def test_storage_fixed(self):
        design = DesignSpec(
            storage=StorageDesign(capacity_mwh=100.0, power_mw=20.0, enabled=True)
        )
        cfg_out = apply_design_to_config(self._make_cfg(), design)
        storage = cfg_out["system"]["storage"]
        assert storage["investment"]["enabled"] is False
        assert storage["max_energy_mwh"] == pytest.approx(100.0)
        assert storage["max_power_mw"] == pytest.approx(20.0)

    def test_disabled_heat_pump(self):
        design = DesignSpec(
            heat_pumps={"HP1": HeatPumpDesign(id="HP1", capacity_mw=0.0, enabled=False)}
        )
        cfg_out = apply_design_to_config(self._make_cfg(), design)
        hp = cfg_out["system"]["heat_pumps"][0]
        assert hp.get("enabled") is False

    def test_does_not_mutate_original(self):
        cfg = self._make_cfg()
        design = DesignSpec(
            heat_pumps={"HP1": HeatPumpDesign(id="HP1", capacity_mw=3.0, enabled=True)}
        )
        apply_design_to_config(cfg, design)
        # Original unchanged
        assert cfg["system"]["heat_pumps"][0]["max_th_mw"] == 10.0


# ---------------------------------------------------------------------------
# validate_design
# ---------------------------------------------------------------------------

class TestValidateDesign:
    def test_valid_design_no_errors(self):
        design = DesignSpec(
            heat_pumps={"HP1": HeatPumpDesign(id="HP1", capacity_mw=5.0)},
            storage=StorageDesign(capacity_mwh=100.0, power_mw=20.0),
        )
        errors = validate_design(design)
        assert errors == []

    def test_zero_capacity_hp_enabled_is_error(self):
        design = DesignSpec(
            heat_pumps={"HP1": HeatPumpDesign(id="HP1", capacity_mw=0.0, enabled=True)},
        )
        errors = validate_design(design)
        assert any("HP1" in e for e in errors)

    def test_zero_storage_capacity_enabled_is_error(self):
        design = DesignSpec(
            storage=StorageDesign(capacity_mwh=0.0, power_mw=0.0, enabled=True),
        )
        errors = validate_design(design)
        assert len(errors) >= 2  # capacity AND power errors

    def test_disabled_storage_no_error(self):
        design = DesignSpec(
            storage=StorageDesign(capacity_mwh=0.0, power_mw=0.0, enabled=False),
        )
        errors = validate_design(design)
        assert errors == []
