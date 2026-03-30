"""Tests for energis.network — programmatic Network builder."""

import pytest
from energis.network import Network, NetworkResult


class TestNetworkBuilder:
    def test_create(self):
        net = Network(dt_h=1.0, solver="glpk")
        assert net.dt_h == 1.0
        assert net.solver == "glpk"

    def test_add_heat_pump(self):
        net = Network()
        net.add_heat_pump("HP1", capacity_mw=10.0, cop=3.5)
        assert len(net._heat_pumps) == 1
        assert net._heat_pumps[0]["id"] == "HP1"
        assert net._heat_pumps[0]["cop_default"] == 3.5

    def test_add_heat_pump_with_investment(self):
        net = Network()
        net.add_heat_pump("HP1", capacity_mw=10.0, investment=True, capacity_min_mw=2.0)
        assert net._heat_pumps[0]["investment"]["enabled"] is True
        assert net._heat_pumps[0]["investment"]["capacity_min_mw"] == 2.0

    def test_add_storage(self):
        net = Network()
        net.add_storage("TES", energy_mwh=200.0, power_mw=40.0, eta_charge=0.95)
        assert net._storage is not None
        assert net._storage["energy_mwh"] == 200.0
        assert net._storage["eta_charge"] == 0.95

    def test_add_storage_with_investment(self):
        net = Network()
        net.add_storage("TES", energy_mwh=100.0, power_mw=20.0, investment=True)
        assert net._storage["investment"]["enabled"] is True

    def test_add_generator(self):
        net = Network()
        net.add_generator("Boiler", cap_th_mw=5.0, efficiency=0.90)
        assert "Boiler" in net._generators
        assert net._generators["Boiler"]["th_eff"] == 0.90

    def test_set_grid(self):
        net = Network()
        net.set_grid(max_import_mw=50.0)
        assert net._grid["max_import_mw"] == 50.0

    def test_set_costs(self):
        net = Network()
        net.set_costs(co2_price_eur_per_t=150.0)
        assert net._costs["co2_price_eur_per_t"] == 150.0

    def test_set_demand(self):
        net = Network()
        net.set_demand([5.0] * 24)
        assert net._n_steps == 24
        assert "waermebedarf_MWth" in net._series

    def test_set_electricity_price(self):
        net = Network()
        net.set_demand([5.0] * 24)
        net.set_electricity_price([50.0] * 24)
        assert "strompreis_EUR_MWh" in net._series

    def test_set_grid_co2(self):
        net = Network()
        net.set_demand([5.0] * 24)
        net.set_grid_co2([400.0] * 24)
        assert "grid_co2_kg_MWh" in net._series

    def test_series_length_mismatch(self):
        net = Network()
        net.set_demand([5.0] * 24)
        with pytest.raises(ValueError, match="expected 24"):
            net.set_electricity_price([50.0] * 12)

    def test_fluent_api(self):
        net = (
            Network(dt_h=1.0)
            .add_heat_pump("HP1", capacity_mw=10.0)
            .add_storage("TES", energy_mwh=200.0, power_mw=40.0)
            .add_generator("Boiler", cap_th_mw=5.0)
            .set_grid(max_import_mw=50.0)
            .set_costs(co2_price_eur_per_t=100.0)
        )
        assert len(net._heat_pumps) == 1
        assert net._storage is not None
        assert len(net._generators) == 1

    def test_repr(self):
        net = Network(dt_h=0.25, solver="cbc")
        net.add_heat_pump("HP1", capacity_mw=5.0)
        net.set_demand([1.0] * 10)
        r = repr(net)
        assert "dt_h=0.25" in r
        assert "heat_pumps: 1" in r
        assert "time_steps: 10" in r


class TestBuildConfig:
    def test_config_structure(self):
        net = Network()
        net.add_heat_pump("HP1", capacity_mw=10.0)
        net.add_storage("TES", energy_mwh=100.0, power_mw=20.0)
        net.add_generator("Boiler", cap_th_mw=5.0)

        cfg = net._build_config()
        assert cfg["run"]["dt_h"] == 1.0
        assert "heat_pumps" in cfg["system"]
        assert "storage" in cfg["system"]
        assert "generators" in cfg["system"]

    def test_config_no_components(self):
        net = Network()
        cfg = net._build_config()
        assert "heat_pumps" not in cfg["system"]


class TestNetworkTopology:
    def test_add_node(self):
        net = Network()
        net.add_node("plant", "producer", assets=["HP1", "Boiler"])
        assert "plant" in net._nodes
        assert net._nodes["plant"]["type"] == "producer"
        assert net._nodes["plant"]["assets"] == ["HP1", "Boiler"]

    def test_add_consumer_node(self):
        net = Network()
        net.add_node("north", "consumer", demand_fraction=0.4, peak_demand_mw=40.0)
        assert net._nodes["north"]["type"] == "consumer"
        assert net._nodes["north"]["demand_fraction"] == 0.4
        assert net._nodes["north"]["demand"]["peak_demand_mw"] == 40.0

    def test_add_junction(self):
        net = Network()
        net.add_node("jct1", "junction")
        assert net._nodes["jct1"]["type"] == "junction"

    def test_add_pipe(self):
        net = Network()
        net.add_pipe("p1", "plant", "north", length_m=2000, diameter_mm=350)
        assert "p1" in net._pipes
        assert net._pipes["p1"]["from"] == "plant"
        assert net._pipes["p1"]["to"] == "north"
        assert net._pipes["p1"]["length_m"] == 2000
        assert net._pipes["p1"]["diameter_mm"] == 350

    def test_add_pipe_with_u_value(self):
        net = Network()
        net.add_pipe("p1", "a", "b", length_m=500, u_value_w_per_m_k=0.5, burial_depth_m=1.2)
        assert net._pipes["p1"]["u_value_w_per_m_k"] == 0.5
        assert net._pipes["p1"]["burial_depth_m"] == 1.2

    def test_set_network_temps(self):
        net = Network()
        net.set_network_temps(supply_temp_c=95, return_temp_c=60, ground_temp_c=8)
        assert net._network_temps["supply_temp_c"] == 95
        assert net._network_temps["return_temp_c"] == 60

    def test_set_network_physics(self):
        net = Network()
        net.set_network_physics(heat_loss=True, pressure_drop=True)
        assert net._network_physics["heat_loss"] is True
        assert net._network_physics["pressure_drop"] is True
        assert net._network_physics["transport_delay"] is False

    def test_set_fuel(self):
        net = Network()
        net.set_fuel("gas", price_eur_mwh=45.0, ef_kg_per_mwh_fuel=200.0)
        assert net._fuels["gas"]["price_eur_mwh"] == 45.0

    def test_config_includes_network(self):
        net = Network()
        net.add_node("plant", "producer", assets=["HP1"])
        net.add_node("c1", "consumer", demand_fraction=0.5)
        net.add_pipe("p1", "plant", "c1", length_m=1000, diameter_mm=300)
        net.set_network_temps(supply_temp_c=90, return_temp_c=55)
        net.set_network_physics(heat_loss=True)

        cfg = net._build_config()
        assert "thermal_network" in cfg
        tn = cfg["thermal_network"]
        assert tn["enabled"] is True
        assert len(tn["nodes"]) == 2
        assert len(tn["pipes"]) == 1
        assert tn["parameters"]["supply_temp_nominal_c"] == 90
        # Consumer node has demand_fraction
        consumer = [n for n in tn["nodes"] if n["type"] == "consumer"][0]
        assert consumer["demand_fraction"] == 0.5

    def test_config_without_network(self):
        net = Network()
        cfg = net._build_config()
        assert "thermal_network" not in cfg

    def test_config_includes_fuels(self):
        net = Network()
        net.set_fuel("gas", price_eur_mwh=45.0)
        cfg = net._build_config()
        assert "fuels" in cfg
        assert cfg["fuels"]["gas"]["price_eur_mwh"] == 45.0

    def test_fluent_topology(self):
        net = (
            Network(dt_h=1.0)
            .set_network_temps(supply_temp_c=90)
            .set_network_physics(heat_loss=True)
            .add_node("plant", "producer", assets=["HP1"])
            .add_node("c1", "consumer", demand_fraction=1.0)
            .add_pipe("p1", "plant", "c1", length_m=1000, diameter_mm=300)
            .add_heat_pump("HP1", capacity_mw=10.0)
            .set_fuel("gas", price_eur_mwh=45.0)
        )
        assert len(net._nodes) == 2
        assert len(net._pipes) == 1
        assert len(net._heat_pumps) == 1

    def test_auto_demand_fraction(self):
        """Consumers without explicit fraction get equal share of remainder."""
        net = Network()
        net.add_node("plant", "producer")
        net.add_node("c1", "consumer", demand_fraction=0.6)
        net.add_node("c2", "consumer")
        net.add_node("c3", "consumer")
        net.add_pipe("p1", "plant", "c1", length_m=100, diameter_mm=200)
        net.add_pipe("p2", "plant", "c2", length_m=100, diameter_mm=200)
        net.add_pipe("p3", "plant", "c3", length_m=100, diameter_mm=200)

        cfg = net._build_config()
        nodes = {n["id"]: n for n in cfg["thermal_network"]["nodes"]}
        assert nodes["c1"]["demand_fraction"] == 0.6
        assert nodes["c2"]["demand_fraction"] == 0.2
        assert nodes["c3"]["demand_fraction"] == 0.2

    def test_repr_shows_topology(self):
        net = Network()
        net.add_node("plant", "producer")
        net.add_node("c1", "consumer")
        net.add_pipe("p1", "plant", "c1", length_m=1000, diameter_mm=300)
        r = repr(net)
        assert "nodes: 2" in r
        assert "pipes: 1" in r


class TestBuildTable:
    def test_builds_table(self):
        net = Network()
        net.set_demand([5.0] * 24)
        net.set_electricity_price([50.0] * 24)
        table = net._build_table()
        assert len(table) == 24
        assert "waermebedarf_MWth" in table.columns

    def test_default_series(self):
        net = Network()
        net.set_demand([5.0] * 24)
        table = net._build_table()
        # Should have default electricity price and CO2
        assert "strompreis_EUR_MWh" in table.columns
        assert "grid_co2_kg_MWh" in table.columns

    def test_no_demand_raises(self):
        net = Network()
        with pytest.raises(ValueError, match="demand"):
            net._build_table()

    def test_no_series_raises(self):
        net = Network()
        with pytest.raises(ValueError, match="No time series"):
            net._build_table()
