"""
Tests for the EmissionsCalculator service.

Verifies that:
1. Grid electricity emissions match legacy heat pump calculation
2. Fuel emissions match legacy thermal generator calculation
3. CHP emissions are correctly split by efficiency
4. CO2Result.to_dict() produces correct format for model storage
5. aggregate_emission_results correctly categorizes by component type
"""
import pytest

from calion.models.emissions_calculator import (
    EmissionsCalculator,
    CO2Result,
    aggregate_emission_results,
)


# ─── Helper Fixtures ──────────────────────────────────────────────────────────

def make_calculator(co2_price=100.0, dt_h=1.0, n_steps=24):
    """Create a test EmissionsCalculator with simple settings."""
    time_set = range(1, n_steps + 1)
    # Flat grid CO2 factor for easy testing: 300 kg CO2/MWh
    grid_co2_series = {i: 300.0 for i in range(n_steps)}  # 0-indexed like table
    return EmissionsCalculator(
        co2_price_param=co2_price,
        grid_co2_series=grid_co2_series,
        dt_h=dt_h,
        time_set=time_set,
    )


def make_flat_var(value: float, time_set):
    """Simulate a constant Pyomo variable as a dict for testing."""
    # Use a dict that behaves like pyo.Var[t] for simple tests
    return {t: value for t in time_set}


# ─── Tests for Grid Electricity Emissions ────────────────────────────────────

class TestGridElectricityEmissions:
    """Tests for calculate_grid_electricity_emissions()."""

    def test_heat_pump_emissions_formula(self):
        """HP grid emissions: co2_kg = sum(Pel[t] * grid_factor[t] * dt_h)."""
        calc = make_calculator(co2_price=100.0, dt_h=1.0, n_steps=24)
        time_set = range(1, 25)
        # Constant 1 MW electricity consumption
        pel = make_flat_var(1.0, time_set)

        result = calc.calculate_grid_electricity_emissions(pel, "heat_pump")

        # Expected: 24 * 1.0 MW * 300 kg/MWh * 1.0 h = 7200 kg
        expected_kg = 24 * 1.0 * 300.0 * 1.0
        assert result.elec_kg == pytest.approx(expected_kg)

    def test_heat_pump_emissions_cost(self):
        """HP CO2 cost: co2_eur = co2_price [EUR/t] / 1000 * co2_kg [kg]."""
        calc = make_calculator(co2_price=100.0, dt_h=1.0, n_steps=24)
        time_set = range(1, 25)
        pel = make_flat_var(1.0, time_set)

        result = calc.calculate_grid_electricity_emissions(pel, "heat_pump")

        expected_kg = 24 * 300.0 * 1.0
        expected_eur = (100.0 / 1000.0) * expected_kg
        assert result.elec_eur == pytest.approx(expected_eur)

    def test_heat_attributed_to_elec_not_heat(self):
        """HP emissions should be in elec_kg, not heat_kg."""
        calc = make_calculator()
        time_set = range(1, 25)
        pel = make_flat_var(2.0, time_set)

        result = calc.calculate_grid_electricity_emissions(pel, "heat_pump")

        assert result.heat_kg == 0
        assert result.heat_eur == 0
        assert result.elec_kg > 0

    def test_p2h_matches_hp_formula(self):
        """P2H grid emissions should use same formula as heat pump."""
        calc = make_calculator(co2_price=50.0, dt_h=0.5, n_steps=48)
        time_set = range(1, 49)
        pel = make_flat_var(3.0, time_set)

        hp_result = calc.calculate_grid_electricity_emissions(pel, "heat_pump")
        p2h_result = calc.calculate_grid_electricity_emissions(pel, "p2h")

        # Same formula, just different component_type
        assert hp_result.elec_kg == pytest.approx(p2h_result.elec_kg)
        assert hp_result.elec_eur == pytest.approx(p2h_result.elec_eur)
        assert p2h_result.component_type == "p2h"

    def test_component_type_stored_correctly(self):
        """component_type should be passed through to result."""
        calc = make_calculator()
        time_set = range(1, 25)
        pel = make_flat_var(1.0, time_set)

        result = calc.calculate_grid_electricity_emissions(pel, "heat_pump")
        assert result.component_type == "heat_pump"

        result2 = calc.calculate_grid_electricity_emissions(pel, "p2h")
        assert result2.component_type == "p2h"

    def test_time_varying_grid_factor(self):
        """Time-varying grid CO2 factor should be used correctly."""
        n_steps = 4
        time_set = range(1, n_steps + 1)
        # Different factors per hour
        grid_co2 = {0: 100.0, 1: 200.0, 2: 300.0, 3: 400.0}
        calc = EmissionsCalculator(
            co2_price_param=1000.0,  # EUR/t
            grid_co2_series=grid_co2,
            dt_h=1.0,
            time_set=time_set,
        )
        pel = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}  # 1 MW constant

        result = calc.calculate_grid_electricity_emissions(pel, "heat_pump")

        # Expected: sum = (100 + 200 + 300 + 400) * 1 * 1 = 1000 kg
        expected_kg = 1000.0
        assert result.elec_kg == pytest.approx(expected_kg)


# ─── Tests for Fuel Combustion Emissions ─────────────────────────────────────

class TestFuelEmissions:
    """Tests for calculate_fuel_emissions() method."""

    def test_heat_only_all_emissions_to_heat(self):
        """Heat-only generator: all CO2 should go to heat."""
        calc = make_calculator(co2_price=100.0, dt_h=1.0, n_steps=24)
        time_set = range(1, 25)
        fuel = make_flat_var(2.0, time_set)  # 2 MW fuel constant

        result = calc.calculate_fuel_emissions(
            fuel_var=fuel,
            fuel_ef_kg_per_mwh=200.0,  # kg CO2/MWh fuel
            is_chp=False,
        )

        # Expected: 24h * 2 MW * 200 kg/MWh = 9600 kg
        expected_kg = 24 * 2.0 * 200.0 * 1.0
        assert result.heat_kg == pytest.approx(expected_kg)
        assert result.elec_kg == 0

    def test_heat_only_component_type(self):
        """Heat-only generator should have component_type 'thermal_generator'."""
        calc = make_calculator()
        time_set = range(1, 25)
        fuel = make_flat_var(1.0, time_set)

        result = calc.calculate_fuel_emissions(fuel, 200.0, is_chp=False)
        assert result.component_type == "thermal_generator"

    def test_heat_only_cost_formula(self):
        """CO2 cost = co2_price/1000 * co2_kg."""
        calc = make_calculator(co2_price=80.0, dt_h=1.0, n_steps=24)
        time_set = range(1, 25)
        fuel = make_flat_var(1.0, time_set)

        result = calc.calculate_fuel_emissions(fuel, 200.0, is_chp=False)

        expected_kg = 24 * 1.0 * 200.0
        expected_eur = (80.0 / 1000.0) * expected_kg
        assert result.heat_eur == pytest.approx(expected_eur)
        assert result.elec_eur == 0

    def test_chp_splits_by_efficiency(self):
        """CHP emissions should split proportionally by efficiency."""
        calc = make_calculator(co2_price=100.0, dt_h=1.0, n_steps=24)
        time_set = range(1, 25)
        fuel = make_flat_var(1.0, time_set)

        # 60% thermal, 30% electric → heat fraction = 0.667, elec fraction = 0.333
        result = calc.calculate_fuel_emissions(
            fuel_var=fuel,
            fuel_ef_kg_per_mwh=300.0,
            is_chp=True,
            th_eff=0.6,
            el_eff=0.3,
        )

        total_kg = 24 * 1.0 * 300.0
        expected_heat = total_kg * (0.6 / 0.9)
        expected_elec = total_kg * (0.3 / 0.9)

        assert result.heat_kg == pytest.approx(expected_heat, rel=1e-6)
        assert result.elec_kg == pytest.approx(expected_elec, rel=1e-6)

    def test_chp_total_equals_fuel_emissions(self):
        """CHP total_kg should equal heat + elec emissions."""
        calc = make_calculator()
        time_set = range(1, 25)
        fuel = make_flat_var(2.0, time_set)

        result = calc.calculate_fuel_emissions(
            fuel_var=fuel,
            fuel_ef_kg_per_mwh=250.0,
            is_chp=True,
            th_eff=0.7,
            el_eff=0.2,
        )

        assert result.total_kg == pytest.approx(result.heat_kg + result.elec_kg, rel=1e-6)

    def test_chp_component_type(self):
        """CHP should have component_type 'chp'."""
        calc = make_calculator()
        time_set = range(1, 25)
        fuel = make_flat_var(1.0, time_set)

        result = calc.calculate_fuel_emissions(
            fuel_var=fuel,
            fuel_ef_kg_per_mwh=200.0,
            is_chp=True,
            th_eff=0.8,
            el_eff=0.2,
        )
        assert result.component_type == "chp"

    def test_zero_efficiency_fallback_to_heat_only(self):
        """Zero total efficiency should attribute all emissions to heat."""
        calc = make_calculator()
        time_set = range(1, 25)
        fuel = make_flat_var(1.0, time_set)

        result = calc.calculate_fuel_emissions(
            fuel_var=fuel,
            fuel_ef_kg_per_mwh=200.0,
            is_chp=True,
            th_eff=0.0,
            el_eff=0.0,
        )

        # Zero total efficiency → heat_only path
        assert result.heat_kg == pytest.approx(24 * 200.0)
        assert result.elec_kg == 0


# ─── Tests for CO2Result ────────────────────────────────────────────────────

class TestCO2Result:
    """Tests for CO2Result dataclass methods."""

    def test_to_dict_contains_required_keys(self):
        """to_dict() should produce dict compatible with model.co2_component_costs."""
        result = CO2Result(
            heat_kg=1000.0,
            elec_kg=0.0,
            heat_eur=100.0,
            elec_eur=0.0,
            total_kg=1000.0,
            total_eur=100.0,
            component_type="thermal_generator",
        )

        d = result.to_dict()

        required_keys = {'heat_kg', 'elec_kg', 'heat_eur', 'elec_eur',
                         'total_kg', 'total_eur', 'type'}
        assert required_keys.issubset(set(d.keys()))

    def test_to_dict_type_field(self):
        """to_dict() should use 'type' as key for component_type."""
        result = CO2Result(
            heat_kg=0, elec_kg=500.0,
            heat_eur=0, elec_eur=50.0,
            total_kg=500.0, total_eur=50.0,
            component_type="heat_pump"
        )
        d = result.to_dict()
        assert d['type'] == 'heat_pump'


# ─── Tests for Aggregation ──────────────────────────────────────────────────

class TestAggregation:
    """Tests for aggregate_emission_results()."""

    def test_heat_pump_goes_to_grid_to_elec(self):
        """Heat pump emissions should appear in co2_kg_grid_to_elec."""
        hp_result = CO2Result(
            heat_kg=0, elec_kg=5000.0,
            heat_eur=0, elec_eur=500.0,
            total_kg=5000.0, total_eur=500.0,
            component_type="heat_pump"
        )

        agg = aggregate_emission_results([hp_result])

        assert len(agg['co2_kg_grid_to_elec']) == 1
        assert agg['co2_kg_grid_to_elec'][0] == pytest.approx(5000.0)
        assert len(agg['co2_kg_fuel_to_heat']) == 0

    def test_thermal_generator_goes_to_fuel_to_heat(self):
        """Thermal generator emissions should appear in co2_kg_fuel_to_heat."""
        gen_result = CO2Result(
            heat_kg=8000.0, elec_kg=0,
            heat_eur=800.0, elec_eur=0,
            total_kg=8000.0, total_eur=800.0,
            component_type="thermal_generator"
        )

        agg = aggregate_emission_results([gen_result])

        assert len(agg['co2_kg_fuel_to_heat']) == 1
        assert agg['co2_kg_fuel_to_heat'][0] == pytest.approx(8000.0)

    def test_chp_splits_into_fuel_to_heat_and_elec(self):
        """CHP emissions should appear in both fuel_to_heat and fuel_to_elec."""
        chp_result = CO2Result(
            heat_kg=6000.0, elec_kg=2000.0,
            heat_eur=600.0, elec_eur=200.0,
            total_kg=8000.0, total_eur=800.0,
            component_type="chp"
        )

        agg = aggregate_emission_results([chp_result])

        assert len(agg['co2_kg_fuel_to_heat']) == 1
        assert agg['co2_kg_fuel_to_heat'][0] == pytest.approx(6000.0)
        assert len(agg['co2_kg_fuel_to_elec']) == 1
        assert agg['co2_kg_fuel_to_elec'][0] == pytest.approx(2000.0)

    def test_mixed_components(self):
        """Multiple different components should each appear in correct categories."""
        results = [
            CO2Result(heat_kg=0, elec_kg=3000.0, heat_eur=0, elec_eur=300.0,
                      total_kg=3000.0, total_eur=300.0, component_type="heat_pump"),
            CO2Result(heat_kg=5000.0, elec_kg=0, heat_eur=500.0, elec_eur=0,
                      total_kg=5000.0, total_eur=500.0, component_type="thermal_generator"),
            CO2Result(heat_kg=0, elec_kg=1000.0, heat_eur=0, elec_eur=100.0,
                      total_kg=1000.0, total_eur=100.0, component_type="p2h"),
        ]

        agg = aggregate_emission_results(results)

        # HP + P2H in grid_to_elec
        assert len(agg['co2_kg_grid_to_elec']) == 2
        # Generator in fuel_to_heat
        assert len(agg['co2_kg_fuel_to_heat']) == 1
        # Nothing in fuel_to_elec (no CHP)
        assert len(agg['co2_kg_fuel_to_elec']) == 0

    def test_empty_list_returns_empty_dicts(self):
        """Empty input should return dict with empty lists."""
        agg = aggregate_emission_results([])
        for key in agg:
            assert agg[key] == []


# ─── Regression Tests ────────────────────────────────────────────────────────

class TestRegressionVsLegacy:
    """Regression tests comparing new service vs original system_builder.py code."""

    def test_hp_co2_matches_legacy_formula(self):
        """HP CO2 should match: sum(P_el[t] * grid_co2[t-1] * dt_h)."""
        n_steps = 3
        time_set = range(1, n_steps + 1)

        # Simulate table["grid_co2_kg_MWh"] as 0-indexed
        legacy_grid = [200.0, 300.0, 400.0]
        grid_co2_series = {i: v for i, v in enumerate(legacy_grid)}

        # Simulate P_el_in as dict (constant 2 MW)
        p_el = {t: 2.0 for t in time_set}
        dt_h = 0.5
        co2_price = 80.0

        # Legacy calculation (from system_builder.py)
        legacy_kg = sum(
            p_el[t] * legacy_grid[t - 1] * dt_h
            for t in time_set
        )
        legacy_cost = (co2_price / 1000.0) * legacy_kg

        # New service calculation
        calc = EmissionsCalculator(
            co2_price_param=co2_price,
            grid_co2_series=grid_co2_series,
            dt_h=dt_h,
            time_set=time_set,
        )
        result = calc.calculate_grid_electricity_emissions(p_el, "heat_pump")

        assert result.elec_kg == pytest.approx(legacy_kg)
        assert result.elec_eur == pytest.approx(legacy_cost)

    def test_fuel_co2_matches_legacy_formula(self):
        """Fuel CO2 should match: sum(fuel[t] * ef * dt_h)."""
        n_steps = 3
        time_set = range(1, n_steps + 1)
        fuel = {t: 3.0 for t in time_set}  # 3 MW fuel constant
        ef = 250.0  # kg/MWh
        dt_h = 1.0
        co2_price = 100.0

        # Legacy calculation (from system_builder.py thermal generator)
        legacy_kg = sum(fuel[t] * ef * dt_h for t in time_set)
        legacy_cost = (co2_price / 1000.0) * legacy_kg

        # New service calculation
        calc = EmissionsCalculator(
            co2_price_param=co2_price,
            grid_co2_series={},  # not used for fuel emissions
            dt_h=dt_h,
            time_set=time_set,
        )
        result = calc.calculate_fuel_emissions(fuel, ef, is_chp=False)

        assert result.heat_kg == pytest.approx(legacy_kg)
        assert result.heat_eur == pytest.approx(legacy_cost)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
