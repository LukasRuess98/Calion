"""Tests for the unified configuration parser.

Covers:
- Parsing of all three config levels (copperplate, 5-node, 30-node)
- Validation (missing assets, invalid pipe refs, missing demand columns)
- Copperplate detection
- Asset-to-legacy conversion
- Model building with unified config
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from energis.config.unified_config import (
    parse_unified_config,
    UnifiedSystemConfig,
    NodeConfig,
    PipeConfig,
    AssetConfig,
    DemandConfig,
    PhysicsConfig,
    unified_assets_to_legacy_system,
    unified_generators_defaults,
)

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:
    HAVE_PYOMO = False

from energis.utils.timeseries import TimeSeriesTable


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _minimal_copperplate_cfg(**overrides):
    """Return a minimal valid copperplate config dict."""
    cfg = {
        "assets": {
            "boiler_1": {
                "type": "thermal_generator",
                "fuel": "gas",
                "capacity_mw": 50.0,
                "thermal_efficiency": 0.9,
            },
        },
        "network": {
            "nodes": {
                "system": {
                    "type": "producer",
                    "assets": ["boiler_1"],
                    "demand": {"column": "waermebedarf_MWth"},
                },
            },
        },
        "grid": {"gridcost_eur_mwh": 20.0},
        "fuels": {"gas": {"price_eur_mwh": 45.0, "ef_kg_per_mwh_fuel": 200.0}},
        "costs": {"co2_price_eur_per_t": 100.0, "dump_cost_eur_per_mwh_th": 1.0},
    }
    cfg.update(overrides)
    return cfg


def _5node_cfg():
    """Return a valid 5-node config dict."""
    return {
        "assets": {
            "boiler_1": {
                "type": "thermal_generator",
                "fuel": "gas",
                "capacity_mw": 150.0,
                "thermal_efficiency": 0.9,
            },
            "hp_1": {
                "type": "heat_pump",
                "capacity_mw": 80.0,
                "cop_default": 3.5,
            },
            "tes_1": {
                "type": "storage",
                "energy_mwh": 500,
                "power_mw": 50,
            },
            "hp_south": {
                "type": "heat_pump",
                "capacity_mw": 10.0,
                "cop_default": 4.0,
            },
        },
        "network": {
            "physics": {
                "heat_loss": True,
                "pressure_drop": True,
            },
            "supply_temp_c": 90,
            "return_temp_c": 55,
            "ground_temp_c": 10,
            "nodes": {
                "plant": {
                    "type": "producer",
                    "assets": ["boiler_1", "hp_1", "tes_1"],
                },
                "north": {
                    "type": "consumer",
                    "demand": {"column": "demand_north_MW"},
                },
                "south": {
                    "type": "consumer",
                    "demand": {"column": "demand_south_MW"},
                    "assets": ["hp_south"],
                },
                "junction_1": {
                    "type": "junction",
                },
                "industrial": {
                    "type": "consumer",
                    "demand": {"column": "demand_industrial_MW"},
                },
            },
            "pipes": {
                "plant_to_j1": {"from": "plant", "to": "junction_1", "length_m": 1200, "diameter_mm": 400},
                "j1_to_north": {"from": "junction_1", "to": "north", "length_m": 2500, "diameter_mm": 350},
                "j1_to_south": {"from": "junction_1", "to": "south", "length_m": 1800, "diameter_mm": 300},
                "plant_to_ind": {"from": "plant", "to": "industrial", "length_m": 800, "diameter_mm": 250},
            },
        },
        "grid": {"gridcost_eur_mwh": 20.0},
        "fuels": {"gas": {"price_eur_mwh": 45.0, "ef_kg_per_mwh_fuel": 200.0}},
        "costs": {"co2_price_eur_per_t": 100.0, "dump_cost_eur_per_mwh_th": 10.0},
    }


def _table(hours=4, demand=10.0):
    """Create a minimal test TimeSeriesTable."""
    base = datetime(2023, 1, 1)
    idx = [base + timedelta(hours=i) for i in range(hours)]
    cols = ["strompreis_EUR_MWh", "waermebedarf_MWth", "grid_co2_kg_MWh"]
    data = {
        "strompreis_EUR_MWh": [50.0] * hours,
        "waermebedarf_MWth": [demand] * hours,
        "grid_co2_kg_MWh": [400.0] * hours,
    }
    return TimeSeriesTable(idx, cols, data)


# ─── Level 1 (Copperplate) Tests ─────────────────────────────────────────────

class TestCopperplateParsing:
    def test_basic_copperplate(self):
        cfg = _minimal_copperplate_cfg()
        ucfg = parse_unified_config(cfg)

        assert ucfg.is_copperplate is True
        assert len(ucfg.nodes) == 1
        assert len(ucfg.pipes) == 0
        assert "system" in ucfg.nodes
        assert ucfg.nodes["system"].type == "producer"
        assert ucfg.nodes["system"].assets == ["boiler_1"]
        assert ucfg.nodes["system"].demand.column == "waermebedarf_MWth"

    def test_copperplate_assets(self):
        cfg = _minimal_copperplate_cfg()
        ucfg = parse_unified_config(cfg)

        assert "boiler_1" in ucfg.assets
        assert ucfg.assets["boiler_1"].type == "thermal_generator"
        assert ucfg.assets["boiler_1"].params["fuel"] == "gas"
        assert ucfg.assets["boiler_1"].params["capacity_mw"] == 50.0

    def test_copperplate_with_hp_and_storage(self):
        cfg = _minimal_copperplate_cfg()
        cfg["assets"]["hp_1"] = {
            "type": "heat_pump",
            "capacity_mw": 80.0,
            "cop_default": 3.5,
        }
        cfg["assets"]["tes_1"] = {
            "type": "storage",
            "energy_mwh": 500,
            "power_mw": 50,
        }
        cfg["network"]["nodes"]["system"]["assets"] = ["boiler_1", "hp_1", "tes_1"]

        ucfg = parse_unified_config(cfg)
        assert ucfg.is_copperplate is True
        assert len(ucfg.assets) == 3
        assets_at_system = ucfg.assets_at_node("system")
        assert len(assets_at_system) == 3

    def test_copperplate_physics_defaults(self):
        cfg = _minimal_copperplate_cfg()
        ucfg = parse_unified_config(cfg)

        assert ucfg.physics.heat_loss is False
        assert ucfg.physics.pressure_drop is False
        assert ucfg.physics.supply_temp_c == 90.0  # default


# ─── Level 2 (5-node) Tests ──────────────────────────────────────────────────

class TestMultiNodeParsing:
    def test_5node_parsing(self):
        cfg = _5node_cfg()
        ucfg = parse_unified_config(cfg)

        assert ucfg.is_copperplate is False
        assert len(ucfg.nodes) == 5
        assert len(ucfg.pipes) == 4
        assert len(ucfg.assets) == 4

    def test_node_types(self):
        cfg = _5node_cfg()
        ucfg = parse_unified_config(cfg)

        assert ucfg.nodes["plant"].type == "producer"
        assert ucfg.nodes["north"].type == "consumer"
        assert ucfg.nodes["south"].type == "consumer"
        assert ucfg.nodes["junction_1"].type == "junction"
        assert ucfg.nodes["industrial"].type == "consumer"

    def test_consumer_demand_columns(self):
        cfg = _5node_cfg()
        ucfg = parse_unified_config(cfg)

        assert ucfg.nodes["north"].demand.column == "demand_north_MW"
        assert ucfg.nodes["south"].demand.column == "demand_south_MW"
        assert ucfg.nodes["industrial"].demand.column == "demand_industrial_MW"

    def test_distributed_assets(self):
        cfg = _5node_cfg()
        ucfg = parse_unified_config(cfg)

        # hp_south is at consumer node "south"
        assert "hp_south" in ucfg.nodes["south"].assets
        # Verify we can look it up
        south_assets = ucfg.assets_at_node("south")
        assert len(south_assets) == 1
        assert south_assets[0].type == "heat_pump"

    def test_pipe_connections(self):
        cfg = _5node_cfg()
        ucfg = parse_unified_config(cfg)

        pipe = ucfg.pipes["plant_to_j1"]
        assert pipe.from_node == "plant"
        assert pipe.to_node == "junction_1"
        assert pipe.length_m == 1200
        assert pipe.diameter_mm == 400

    def test_physics_config(self):
        cfg = _5node_cfg()
        ucfg = parse_unified_config(cfg)

        assert ucfg.physics.heat_loss is True
        assert ucfg.physics.pressure_drop is True
        assert ucfg.physics.transport_delay is False
        assert ucfg.physics.supply_temp_c == 90
        assert ucfg.physics.return_temp_c == 55
        assert ucfg.physics.ground_temp_c == 10

    def test_helper_methods(self):
        cfg = _5node_cfg()
        ucfg = parse_unified_config(cfg)

        producers = ucfg.producer_nodes()
        assert len(producers) == 1
        assert "plant" in producers

        consumers = ucfg.consumer_nodes()
        assert len(consumers) == 3

        by_type = ucfg.node_ids_by_type("junction")
        assert by_type == ["junction_1"]


# ─── Validation Tests ─────────────────────────────────────────────────────────

class TestValidation:
    def test_missing_assets_section(self):
        cfg = {"network": {"nodes": {"sys": {"type": "producer"}}}}
        with pytest.raises(ValueError, match="assets.*required"):
            parse_unified_config(cfg)

    def test_missing_network_nodes(self):
        cfg = {"assets": {"b1": {"type": "thermal_generator"}}}
        with pytest.raises(ValueError, match="network.*nodes.*required"):
            parse_unified_config(cfg)

    def test_undefined_asset_reference(self):
        cfg = {
            "assets": {"boiler_1": {"type": "thermal_generator"}},
            "network": {
                "nodes": {
                    "sys": {
                        "type": "producer",
                        "assets": ["boiler_1", "nonexistent"],
                        "demand": {"column": "heat"},
                    }
                }
            },
        }
        with pytest.raises(ValueError, match="undefined asset 'nonexistent'"):
            parse_unified_config(cfg)

    def test_invalid_pipe_node_reference(self):
        cfg = {
            "assets": {"b1": {"type": "thermal_generator", "capacity_mw": 10}},
            "network": {
                "nodes": {
                    "plant": {"type": "producer", "assets": ["b1"], "demand": {"column": "heat"}},
                },
                "pipes": {
                    "p1": {"from": "plant", "to": "missing_node", "length_m": 100, "diameter_mm": 200},
                },
            },
        }
        with pytest.raises(ValueError, match="missing_node.*not a defined node"):
            parse_unified_config(cfg)

    def test_consumer_without_demand(self):
        cfg = {
            "assets": {"b1": {"type": "thermal_generator", "capacity_mw": 10}},
            "network": {
                "nodes": {
                    "plant": {"type": "producer", "assets": ["b1"]},
                    "consumer_a": {"type": "consumer"},  # missing demand!
                },
            },
        }
        with pytest.raises(ValueError, match="consumer.*demand.column"):
            parse_unified_config(cfg)

    def test_no_producer_node(self):
        cfg = {
            "assets": {"b1": {"type": "thermal_generator", "capacity_mw": 10}},
            "network": {
                "nodes": {
                    "consumer_a": {"type": "consumer", "demand": {"column": "heat"}},
                },
            },
        }
        with pytest.raises(ValueError, match="producer node is required"):
            parse_unified_config(cfg)

    def test_invalid_node_type(self):
        cfg = {
            "assets": {"b1": {"type": "thermal_generator"}},
            "network": {
                "nodes": {
                    "sys": {"type": "invalid_type", "assets": ["b1"]},
                },
            },
        }
        with pytest.raises(ValueError, match="producer/consumer/junction"):
            parse_unified_config(cfg)

    def test_pipe_zero_length(self):
        cfg = {
            "assets": {"b1": {"type": "thermal_generator"}},
            "network": {
                "nodes": {
                    "a": {"type": "producer", "assets": ["b1"]},
                    "b": {"type": "consumer", "demand": {"column": "heat"}},
                },
                "pipes": {
                    "p1": {"from": "a", "to": "b", "length_m": 0, "diameter_mm": 200},
                },
            },
        }
        with pytest.raises(ValueError, match="length_m must be > 0"):
            parse_unified_config(cfg)

    def test_asset_missing_type(self):
        cfg = {
            "assets": {"b1": {"capacity_mw": 10}},  # missing type!
            "network": {
                "nodes": {
                    "sys": {"type": "producer", "assets": ["b1"]},
                },
            },
        }
        with pytest.raises(ValueError, match="must have 'type'"):
            parse_unified_config(cfg)


# ─── Demand Config Tests ─────────────────────────────────────────────────────

class TestDemandConfig:
    def test_string_demand(self):
        d = DemandConfig.from_dict("my_column")
        assert d.column == "my_column"

    def test_dict_demand(self):
        d = DemandConfig.from_dict({"column": "heat_MW"})
        assert d.column == "heat_MW"

    def test_dict_missing_column(self):
        with pytest.raises(ValueError, match="column"):
            DemandConfig.from_dict({"fraction": 0.5})

    def test_invalid_demand(self):
        with pytest.raises(ValueError):
            DemandConfig.from_dict(42)


# ─── Legacy Conversion Tests ─────────────────────────────────────────────────

class TestLegacyConversion:
    def test_generator_conversion(self):
        cfg = _minimal_copperplate_cfg()
        ucfg = parse_unified_config(cfg)
        legacy = unified_assets_to_legacy_system(ucfg)

        assert len(legacy["generators"]) == 1
        gen = legacy["generators"]["boiler_1"]
        assert gen["enabled"] is True
        assert gen["cap_th_mw"] == 50.0
        assert gen["_defaults"]["th_eff"] == 0.9
        assert gen["_defaults"]["fuel_bus"] == "gas"

    def test_hp_conversion(self):
        cfg = _minimal_copperplate_cfg()
        cfg["assets"]["hp_1"] = {
            "type": "heat_pump",
            "capacity_mw": 80.0,
            "cop_default": 3.5,
        }
        cfg["network"]["nodes"]["system"]["assets"].append("hp_1")
        ucfg = parse_unified_config(cfg)
        legacy = unified_assets_to_legacy_system(ucfg)

        assert len(legacy["heat_pumps"]) == 1
        hp = legacy["heat_pumps"][0]
        assert hp["id"] == "hp_1"
        assert hp["max_th_mw"] == 80.0

    def test_storage_conversion(self):
        cfg = _minimal_copperplate_cfg()
        cfg["assets"]["tes_1"] = {
            "type": "storage",
            "energy_mwh": 500,
            "power_mw": 50,
        }
        cfg["network"]["nodes"]["system"]["assets"].append("tes_1")
        ucfg = parse_unified_config(cfg)
        legacy = unified_assets_to_legacy_system(ucfg)

        sto = legacy["storage"]
        assert sto["enabled"] is True
        assert sto["max_energy_mwh"] == 500
        assert sto["max_power_mw"] == 50

    def test_generator_defaults(self):
        cfg = _minimal_copperplate_cfg()
        ucfg = parse_unified_config(cfg)
        defaults = unified_generators_defaults(ucfg)

        assert "boiler_1" in defaults
        assert defaults["boiler_1"]["th_eff"] == 0.9
        assert defaults["boiler_1"]["fuel_bus"] == "gas"


# ─── Model Building Integration Tests ────────────────────────────────────────

@pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not available")
class TestUnifiedModelBuilding:
    def test_copperplate_builds(self):
        """A copperplate unified config should build a valid Pyomo model."""
        from energis.models.system_builder import build_model

        table = _table(hours=4, demand=10.0)
        cfg = _minimal_copperplate_cfg()
        model = build_model(table, cfg, dt_h=1.0)

        assert model is not None
        assert hasattr(model, "obj")
        assert hasattr(model, "heatd")
        assert hasattr(model, "ht_balance")
        assert hasattr(model, "el_balance")

    def test_copperplate_with_hp_builds(self):
        """Copperplate with HP + generator builds and has correct variables."""
        from energis.models.system_builder import build_model

        table = _table(hours=2, demand=5.0)
        cfg = _minimal_copperplate_cfg()
        cfg["assets"]["hp_1"] = {
            "type": "heat_pump",
            "capacity_mw": 20.0,
            "cop_default": 3.0,
        }
        cfg["network"]["nodes"]["system"]["assets"] = ["boiler_1", "hp_1"]

        model = build_model(table, cfg, dt_h=1.0)
        assert model is not None

        # HP variables should exist (HeatPumpBlock uses {name}_Q)
        assert hasattr(model, "hp_1_Q")

    def test_unified_config_stored_on_model(self):
        """Unified config reference is stored on the model for export."""
        from energis.models.system_builder import build_model

        table = _table(hours=2, demand=5.0)
        cfg = _minimal_copperplate_cfg()
        model = build_model(table, cfg, dt_h=1.0)

        assert hasattr(model, "_unified_config")
        assert model._unified_config.is_copperplate is True

    def test_legacy_config_still_works(self):
        """Legacy config format should still work via the old path."""
        from energis.models.system_builder import build_model

        table = _table(hours=2, demand=0.0)
        cfg = {
            "costs": {
                "include_co2_cost_in_objective": False,
                "dump_cost_eur_per_mwh_th": 0.0,
            },
            "grid": {},
            "system": {
                "heat_pumps": [],
                "storage": {"enabled": False},
                "generators": {},
            },
        }
        model = build_model(table, cfg, dt_h=1.0)
        assert model is not None
        assert hasattr(model, "obj")
        # Legacy models don't have _unified_config
        assert not hasattr(model, "_unified_config")
