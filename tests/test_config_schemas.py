"""Tests for energis.config.schemas — dataclass schema definitions."""

from energis.config.schemas.asset_schema import (
    AssetCapacity,
    ExpansionPotential,
    ComponentAsset,
    HeatPumpAsset,
    StorageAsset,
    GeneratorAsset,
    P2HAsset,
    GridConnection,
)
from energis.config.schemas.network_schema import (
    NetworkNode,
    PipeCapacity,
    PipeExpansion,
    Pipe,
    Pump,
    HeatingCurve,
    ThermalNetwork,
    NetworkTopology,
)
from energis.config.schemas.tech_library_schema import (
    COPModel,
    HeatPumpTechnology,
    StorageTechnology,
    GeneratorTechnology,
    P2HTechnology,
    PipeTechnology,
    FuelProperties,
)
from energis.config.schemas.scenario_schema import (
    RepresentativePeriods,
    TimeConfig,
    CostConfig,
    ConstraintsConfig,
    OptimizationConfig,
    InitialState,
    TerminalConditions,
    Subsidies,
    EconomicsConfig,
    SensitivityConfig,
    SolverConfig,
    OutputConfig,
    ReportingConfig,
    AssetPaths,
    Scenario,
)


# ---------------------------------------------------------------------------
# Asset schemas
# ---------------------------------------------------------------------------

class TestAssetCapacity:
    def test_defaults(self):
        ac = AssetCapacity()
        assert ac.thermal_capacity_mw == 0.0
        assert ac.electrical_capacity_mw is None

    def test_from_dict(self):
        ac = AssetCapacity.from_dict({
            "thermal_capacity_mw": 10.0,
            "energy_capacity_mwh": 200.0,
            "commissioning_year": 2020,
        })
        assert ac.thermal_capacity_mw == 10.0
        assert ac.energy_capacity_mwh == 200.0
        assert ac.commissioning_year == 2020
        assert ac.electrical_capacity_mw is None

    def test_from_dict_empty(self):
        ac = AssetCapacity.from_dict({})
        assert ac.thermal_capacity_mw == 0.0


class TestExpansionPotential:
    def test_defaults(self):
        ep = ExpansionPotential()
        assert ep.enabled is False
        assert ep.lifetime_yr == 20.0

    def test_from_dict(self):
        ep = ExpansionPotential.from_dict({
            "enabled": True,
            "max_additional_capacity_mw": 50.0,
            "capex_eur_per_mw": 500000,
            "activation_cost_eur": 10000,
            "power_energy_coupling": 0.1,
        })
        assert ep.enabled is True
        assert ep.max_additional_capacity_mw == 50.0
        assert ep.power_energy_coupling == 0.1


class TestComponentAsset:
    def test_from_dict(self):
        ca = ComponentAsset.from_dict("HP1", {
            "description": "Test HP",
            "technology": "heat_pump",
            "existing": {"thermal_capacity_mw": 5.0},
            "expansion": {"enabled": True, "max_additional_capacity_mw": 10.0},
        })
        assert ca.id == "HP1"
        assert ca.existing.thermal_capacity_mw == 5.0
        assert ca.expansion.enabled is True

    def test_from_dict_minimal(self):
        ca = ComponentAsset.from_dict("X", {})
        assert ca.id == "X"
        assert ca.technology == ""


class TestHeatPumpAsset:
    def test_from_dict(self):
        hp = HeatPumpAsset.from_dict("HP1", {
            "description": "Large HP",
            "technology": "heat_pump",
            "waste_heat_source": {"type": "industrial", "temp_c": 40},
        })
        assert hp.waste_heat_source["type"] == "industrial"


class TestStorageAsset:
    def test_from_dict(self):
        sa = StorageAsset.from_dict("TES", {"technology": "hot_water_tank"})
        assert sa.id == "TES"


class TestGeneratorAsset:
    def test_from_dict(self):
        ga = GeneratorAsset.from_dict("Boiler", {"technology": "gas_boiler"})
        assert ga.id == "Boiler"


class TestP2HAsset:
    def test_from_dict(self):
        p = P2HAsset.from_dict("EB1", {"technology": "electrode_boiler"})
        assert p.id == "EB1"


class TestGridConnection:
    def test_from_dict_defaults(self):
        gc = GridConnection.from_dict({})
        assert gc.voltage_level_kv == 20.0
        assert gc.max_import_mw == 100.0
        assert gc.demand_charges_enabled is True

    def test_from_dict_full(self):
        gc = GridConnection.from_dict({
            "connection": {"voltage_level_kv": 110, "max_import_mw": 200},
            "pricing": {
                "wholesale": {"price_column": "my_price"},
                "buy_fees": {"total_buy_fees_eur_per_mwh": 30.0},
                "sell_model": {"haircut_fraction": 0.1, "spread_eur_per_mwh": 3.0},
            },
            "demand_charges": {"enabled": False, "annual_charge_eur_per_mw": 80000},
            "emissions": {"co2_intensity": {"intensity_column": "co2_col"}},
        })
        assert gc.voltage_level_kv == 110
        assert gc.sell_haircut_fraction == 0.1
        assert gc.demand_charges_enabled is False
        assert gc.co2_intensity_column == "co2_col"


# ---------------------------------------------------------------------------
# Network schemas
# ---------------------------------------------------------------------------

class TestNetworkNode:
    def test_from_dict(self):
        nn = NetworkNode.from_dict("N1", {
            "type": "producer",
            "components": ["HP1"],
            "demand": {"demand_column": "heat_mw", "peak_demand_mw": 10.0},
        })
        assert nn.id == "N1"
        assert nn.type == "producer"
        assert nn.demand_column == "heat_mw"

    def test_from_dict_minimal(self):
        nn = NetworkNode.from_dict("J1", {})
        assert nn.type == "junction"


class TestPipeCapacity:
    def test_from_dict(self):
        pc = PipeCapacity.from_dict({
            "diameter_mm": 200,
        })
        assert pc.diameter_mm == 200


class TestPipe:
    def test_from_dict(self):
        p = Pipe.from_dict("P1", {
            "from_node": "N1",
            "to_node": "N2",
            "length_m": 500,
            "diameter_mm": 200,
        })
        assert p.id == "P1"
        assert p.from_node == "N1"
        assert p.length_m == 500


class TestThermalNetwork:
    def test_from_dict(self):
        tn = ThermalNetwork.from_dict("main", {"supply_temperature_c": 95.0})
        assert tn.id == "main"


class TestNetworkTopology:
    def test_from_dict(self):
        nt = NetworkTopology.from_dict({
            "networks": {
                "main": {
                    "supply_temperature_c": 95.0,
                }
            }
        })
        assert "main" in nt.networks


# ---------------------------------------------------------------------------
# Tech library schemas
# ---------------------------------------------------------------------------

class TestCOPModel:
    def test_from_dict(self):
        cop = COPModel.from_dict({
            "type": "carnot_factor",
            "carnot_efficiency": 0.5,
        })
        assert cop.type == "carnot_factor"
        assert cop.carnot_efficiency == 0.5

    def test_from_dict_lookup(self):
        cop = COPModel.from_dict({
            "type": "lookup_table_2d",
            "lookup_table": {
                "source_temps_K": [280, 290],
                "sink_temps_K": [340, 350],
                "cop_values": [[3.0, 2.8], [3.5, 3.2]],
            },
        })
        assert len(cop.source_temps_K) == 2


class TestHeatPumpTechnology:
    def test_from_dict(self):
        hp = HeatPumpTechnology.from_dict("hp_type_1", {
            "description": "Standard HP",
            "cop_model": {"type": "carnot_factor", "carnot_efficiency": 0.5},
        })
        assert hp.id == "hp_type_1"
        assert hp.cop_model.carnot_efficiency == 0.5


class TestStorageTechnology:
    def test_from_dict(self):
        st = StorageTechnology.from_dict("hot_water", {
            "description": "Hot water tank",
        })
        assert st.id == "hot_water"


class TestGeneratorTechnology:
    def test_from_dict(self):
        gt = GeneratorTechnology.from_dict("gas_boiler", {
            "description": "Gas boiler",
        })
        assert gt.id == "gas_boiler"


class TestP2HTechnology:
    def test_from_dict(self):
        pt = P2HTechnology.from_dict("electrode", {
            "description": "Electrode boiler",
        })
        assert pt.id == "electrode"


class TestPipeTechnology:
    def test_from_dict(self):
        pt = PipeTechnology.from_dict("standard", {
            "description": "Pre-insulated",
        })
        assert pt.id == "standard"


class TestFuelProperties:
    def test_from_dict(self):
        fp = FuelProperties.from_dict("natural_gas", {
            "description": "Natural gas",
        })
        assert fp.id == "natural_gas"


# ---------------------------------------------------------------------------
# Scenario schemas
# ---------------------------------------------------------------------------

class TestRepresentativePeriods:
    def test_defaults(self):
        rp = RepresentativePeriods()
        assert rp.method == "kmeans_clustering"
        assert rp.num_periods == 8

    def test_from_dict(self):
        rp = RepresentativePeriods.from_dict({"num_periods": 12})
        assert rp.num_periods == 12


class TestTimeConfig:
    def test_from_dict(self):
        tc = TimeConfig.from_dict({
            "data_file": "data.xlsx",
            "data_source_config": "default",
            "start": "2024-01-01",
            "resolution_h": 0.25,
        })
        assert tc.data_file == "data.xlsx"
        assert tc.resolution_h == 0.25


class TestCostConfig:
    def test_from_dict(self):
        cc = CostConfig.from_dict({
            "include_capex": True,
            "include_co2": False,
        })
        assert cc.include_capex is True
        assert cc.include_co2 is False

    def test_defaults(self):
        cc = CostConfig.from_dict({})
        assert cc.discount_rate is not None


class TestOptimizationConfig:
    def test_from_dict(self):
        oc = OptimizationConfig.from_dict({})
        assert oc.mode is not None


class TestSolverConfig:
    def test_from_dict(self):
        sc = SolverConfig.from_dict({"name": "gurobi", "timelimit_s": 300})
        assert sc.name == "gurobi"
        assert sc.timelimit_s == 300


class TestOutputConfig:
    def test_from_dict(self):
        oc = OutputConfig.from_dict({})
        assert oc is not None


class TestScenario:
    def test_from_dict(self):
        s = Scenario.from_dict({
            "scenario": {
                "name": "test_scenario",
                "description": "A test",
                "time": {
                    "data_file": "data.xlsx",
                    "data_source_config": "default",
                },
                "assets": {
                    "components": "components.yaml",
                    "grid": "grid.yaml",
                    "network": "network.yaml",
                },
            },
        })
        assert s.name == "test_scenario"
        assert s.time.data_file == "data.xlsx"
