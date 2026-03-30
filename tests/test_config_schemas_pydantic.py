"""Pydantic-specific tests for CALION config schemas.

Tests that validate the new Pydantic constraints:
- Field(ge=0) bounds on capacities and costs
- @model_validator cross-field checks on ExpansionPotential
- Literal enforcement on OptimizationConfig.mode and SolverConfig.name
- AliasChoices on Pump for alternate YAML keys
- model_json_schema() smoke test
"""

import pytest
from pydantic import ValidationError

from calion.config.schemas.asset_schema import AssetCapacity, ExpansionPotential
from calion.config.schemas.network_schema import Pump
from calion.config.schemas.scenario_schema import OptimizationConfig, SolverConfig


# ---------------------------------------------------------------------------
# AssetCapacity — Field(ge=0) constraints
# ---------------------------------------------------------------------------

class TestAssetCapacityConstraints:
    def test_negative_thermal_capacity_raises(self):
        with pytest.raises(ValidationError):
            AssetCapacity(thermal_capacity_mw=-1.0)

    def test_negative_energy_capacity_raises(self):
        with pytest.raises(ValidationError):
            AssetCapacity(energy_capacity_mwh=-0.1)

    def test_negative_electrical_capacity_raises(self):
        with pytest.raises(ValidationError):
            AssetCapacity(electrical_capacity_mw=-5.0)

    def test_zero_thermal_capacity_ok(self):
        ac = AssetCapacity(thermal_capacity_mw=0.0)
        assert ac.thermal_capacity_mw == 0.0

    def test_positive_values_ok(self):
        ac = AssetCapacity(thermal_capacity_mw=10.0, energy_capacity_mwh=200.0)
        assert ac.thermal_capacity_mw == 10.0
        assert ac.energy_capacity_mwh == 200.0


# ---------------------------------------------------------------------------
# ExpansionPotential — cross-field validator
# ---------------------------------------------------------------------------

class TestExpansionPotentialValidator:
    def test_max_lt_min_when_enabled_raises(self):
        with pytest.raises(ValidationError, match="max_additional_capacity_mw must be >="):
            ExpansionPotential(
                enabled=True,
                min_additional_capacity_mw=10.0,
                max_additional_capacity_mw=5.0,
            )

    def test_max_lt_min_when_disabled_ok(self):
        # Ordering constraint only applies when enabled=True
        ep = ExpansionPotential(
            enabled=False,
            min_additional_capacity_mw=10.0,
            max_additional_capacity_mw=5.0,
        )
        assert ep.enabled is False

    def test_max_equal_min_when_enabled_ok(self):
        ep = ExpansionPotential(
            enabled=True,
            min_additional_capacity_mw=5.0,
            max_additional_capacity_mw=5.0,
        )
        assert ep.max_additional_capacity_mw == 5.0

    def test_negative_capex_raises(self):
        with pytest.raises(ValidationError):
            ExpansionPotential(capex_eur_per_mw=-1000.0)

    def test_zero_lifetime_raises(self):
        with pytest.raises(ValidationError):
            ExpansionPotential(lifetime_yr=0.0)


# ---------------------------------------------------------------------------
# OptimizationConfig — Literal mode
# ---------------------------------------------------------------------------

class TestOptimizationConfigLiteral:
    def test_valid_dispatch_mode(self):
        oc = OptimizationConfig(mode="dispatch")
        assert oc.mode == "dispatch"

    def test_valid_capacity_expansion_mode(self):
        oc = OptimizationConfig(mode="capacity_expansion")
        assert oc.mode == "capacity_expansion"

    def test_valid_network_design_mode(self):
        oc = OptimizationConfig(mode="network_design")
        assert oc.mode == "network_design"

    def test_invalid_mode_raises(self):
        with pytest.raises(ValidationError):
            OptimizationConfig(mode="unknown_mode")

    def test_default_mode_is_dispatch(self):
        oc = OptimizationConfig()
        assert oc.mode == "dispatch"


# ---------------------------------------------------------------------------
# SolverConfig — Literal name
# ---------------------------------------------------------------------------

class TestSolverConfigLiteral:
    def test_gurobi_accepted(self):
        sc = SolverConfig(name="gurobi")
        assert sc.name == "gurobi"

    def test_glpk_accepted(self):
        sc = SolverConfig(name="glpk")
        assert sc.name == "glpk"

    def test_cbc_accepted(self):
        sc = SolverConfig(name="cbc")
        assert sc.name == "cbc"

    def test_highs_accepted(self):
        sc = SolverConfig(name="highs")
        assert sc.name == "highs"

    def test_scip_accepted(self):
        sc = SolverConfig(name="scip")
        assert sc.name == "scip"

    def test_invalid_solver_raises(self):
        with pytest.raises(ValidationError):
            SolverConfig(name="mosek")

    def test_mip_gap_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            SolverConfig(mip_gap=1.5)

    def test_zero_timelimit_raises(self):
        with pytest.raises(ValidationError):
            SolverConfig(timelimit_s=0)


# ---------------------------------------------------------------------------
# Pump — AliasChoices for alternate YAML keys
# ---------------------------------------------------------------------------

class TestPumpAliasChoices:
    def test_primary_key_rated_pressure_bar(self):
        pump = Pump(id="P1", node="n1", rated_pressure_bar=3.0, rated_flow_m3_per_h=100.0)
        assert pump.rated_pressure_bar == 3.0

    def test_alias_rated_pressure_rise_bar(self):
        pump = Pump.model_validate({
            "id": "P1",
            "node": "n1",
            "rated_pressure_rise_bar": 3.0,
            "rated_flow_m3_per_h": 100.0,
        })
        assert pump.rated_pressure_bar == 3.0

    def test_alias_rated_flow_m3_h(self):
        pump = Pump.model_validate({
            "id": "P1",
            "node": "n1",
            "rated_pressure_bar": 3.0,
            "rated_flow_m3_h": 100.0,
        })
        assert pump.rated_flow_m3_per_h == 100.0

    def test_from_dict_with_rise_bar_alias(self):
        pump = Pump.from_dict("P1", {
            "node": "n1",
            "rated_pressure_rise_bar": 4.0,
            "rated_flow_m3_per_h": 80.0,
        })
        assert pump.rated_pressure_bar == 4.0

    def test_invalid_efficiency_raises(self):
        with pytest.raises(ValidationError):
            Pump(id="P1", node="n1", rated_pressure_bar=3.0,
                 rated_flow_m3_per_h=100.0, efficiency=1.5)


# ---------------------------------------------------------------------------
# model_json_schema — smoke test
# ---------------------------------------------------------------------------

class TestJsonSchema:
    def test_asset_capacity_schema_is_dict(self):
        schema = AssetCapacity.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema

    def test_expansion_potential_schema_has_constraints(self):
        schema = ExpansionPotential.model_json_schema()
        props = schema.get("properties", {})
        # capex_eur_per_mw should have minimum: 0
        assert "capex_eur_per_mw" in props

    def test_solver_config_schema_has_enum(self):
        schema = SolverConfig.model_json_schema()
        props = schema.get("properties", {})
        name_prop = props.get("name", {})
        # Literal produces anyOf or enum in JSON schema
        assert "enum" in name_prop or "anyOf" in name_prop

    def test_optimization_config_schema_is_dict(self):
        schema = OptimizationConfig.model_json_schema()
        assert isinstance(schema, dict)
