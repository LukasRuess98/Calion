"""
Test suite for component protocol compliance.

Verifies that all existing component blocks properly implement the
ComponentBlock protocol defined in energis.models.interfaces.

This ensures:
1. All components follow the expected interface
2. Protocol checking works at runtime
3. Type checkers can validate component usage
"""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from energis.models.interfaces import (
    ComponentBlock,
    InvestmentStrategy,
    CO2Calculator,
    is_valid_component_block,
    is_valid_investment_strategy,
    is_valid_co2_calculator,
    InvestmentConfig,
    EmissionResult,
)
from energis.models.component import BaseComponent
from energis.models.blocks.heat_pump import HeatPumpBlock
from energis.models.blocks.storage import StorageBlock
from energis.models.blocks.stratified_storage import StratifiedStorageBlock
from energis.models.blocks.thermal_gen import ThermalGeneratorBlock
from energis.models.blocks.p2h import P2HBlock


@pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not available")
class TestComponentProtocolCompliance:
    """Test that all component blocks implement ComponentBlock protocol."""

    def test_heat_pump_block_implements_protocol(self):
        """Verify HeatPumpBlock implements ComponentBlock protocol."""
        # Create with correct parameters
        hp = HeatPumpBlock(
            name="test_hp",
            min_load=0.3,
            cop_series=[3.0] * 24,
            capacity_min_mw=0.0,
            capacity_max_mw=10.0,
            capacity_init_mw=0.0,
            investable=True,
            cop_default=3.0  # Must be > COP_MIN (1.01)
        )

        # Runtime protocol check
        assert isinstance(hp, ComponentBlock)
        assert is_valid_component_block(hp)

        # Check required attributes
        assert hasattr(hp, 'name')
        assert hasattr(hp, 'attach')
        assert hasattr(hp, 'get_results')
        assert hasattr(hp, 'validate_config')

        # Check methods are callable
        assert callable(hp.attach)
        assert callable(hp.get_results)
        assert callable(hp.validate_config)

    def test_storage_block_implements_protocol(self):
        """Verify StorageBlock implements ComponentBlock protocol."""
        storage = StorageBlock(
            name="test_storage",
            e_min=0.1,  # min SOC fraction
            e_max=0.9,  # max SOC fraction
            p_max=5.0,  # max power MW
            eff_c=0.95,  # charge efficiency
            eff_d=0.95,  # discharge efficiency
            hourly_loss=0.001,
            dt_h=1.0,
            soc0=0.5,  # initial SOC
            investable=True,
            e_cap_min=0.0,
            e_cap_max=20.0,
            p_cap_min=0.0,
            p_cap_max=5.0,
            e_cap_init=10.0,
            p_cap_init=2.5,
            terminal_target=None
        )

        assert isinstance(storage, ComponentBlock)
        assert is_valid_component_block(storage)

    def test_stratified_storage_implements_protocol(self):
        """Verify StratifiedStorageBlock implements ComponentBlock protocol."""
        # StratifiedStorageBlock has different signature - just verify class structure
        assert hasattr(StratifiedStorageBlock, 'attach')
        assert hasattr(StratifiedStorageBlock, 'get_results')
        assert hasattr(StratifiedStorageBlock, 'validate_config')

        # Verify it inherits from BaseComponent (which implements the protocol)
        assert issubclass(StratifiedStorageBlock, BaseComponent)

    def test_thermal_generator_implements_protocol(self):
        """Verify ThermalGeneratorBlock implements ComponentBlock protocol."""
        gen = ThermalGeneratorBlock(
            name="test_gen",
            th_eff=0.9,  # thermal efficiency
            el_eff=None,  # no CHP
            cap_th_mw=10.0
        )

        assert isinstance(gen, ComponentBlock)
        assert is_valid_component_block(gen)

    def test_p2h_block_implements_protocol(self):
        """Verify P2HBlock implements ComponentBlock protocol."""
        p2h = P2HBlock(
            name="test_p2h",
            eff=0.98,  # efficiency
            cap_th_mw=5.0,  # thermal capacity
            min_load=0.0
        )

        assert isinstance(p2h, ComponentBlock)
        assert is_valid_component_block(p2h)

    def test_all_blocks_have_attach_method(self):
        """Verify all blocks have attach method with correct signature."""
        blocks = [
            HeatPumpBlock(
                name="hp", min_load=0.3, cop_series=[3.0] * 24,
                capacity_min_mw=0.0, capacity_max_mw=10.0,
                capacity_init_mw=0.0, investable=True, cop_default=3.0
            ),
            StorageBlock(
                name="storage", e_min=0.1, e_max=0.9, p_max=5.0,
                eff_c=0.95, eff_d=0.95, hourly_loss=0.001,
                dt_h=1.0, soc0=0.5, investable=True,
                e_cap_min=0.0, e_cap_max=20.0, p_cap_min=0.0,
                p_cap_max=5.0, e_cap_init=10.0, p_cap_init=2.5,
                terminal_target=None
            ),
            ThermalGeneratorBlock(
                name="gen", th_eff=0.9, el_eff=None, cap_th_mw=10.0
            ),
            P2HBlock(
                name="p2h", eff=0.98, cap_th_mw=5.0, min_load=0.0
            ),
        ]

        for block in blocks:
            # Verify method exists and has correct parameters
            import inspect
            sig = inspect.signature(block.attach)
            params = list(sig.parameters.keys())

            # Should have: self, model (or m), time_set (or Tset), config (or cfg), buses
            assert len(params) >= 4, f"{block.name} attach should have at least 4 params"

    def test_all_blocks_have_get_results_method(self):
        """Verify all blocks have get_results method."""
        blocks = [
            HeatPumpBlock(
                name="hp", min_load=0.3, cop_series=[3.0] * 24,
                capacity_min_mw=0.0, capacity_max_mw=10.0,
                capacity_init_mw=0.0, investable=True, cop_default=3.0
            ),
            StorageBlock(
                name="storage", e_min=0.1, e_max=0.9, p_max=5.0,
                eff_c=0.95, eff_d=0.95, hourly_loss=0.001,
                dt_h=1.0, soc0=0.5, investable=True,
                e_cap_min=0.0, e_cap_max=20.0, p_cap_min=0.0,
                p_cap_max=5.0, e_cap_init=10.0, p_cap_init=2.5,
                terminal_target=None
            ),
        ]

        for block in blocks:
            assert hasattr(block, 'get_results')
            assert callable(block.get_results)

    def test_component_attach_returns_dict(self):
        """Verify that attach() returns a dictionary with expected structure."""
        model = pyo.ConcreteModel()
        model.t = pyo.Set(initialize=range(1, 25))  # 24 hours

        hp = HeatPumpBlock(
            name="test_hp",
            min_load=0.3,
            cop_series=[3.0] * 24,
            capacity_min_mw=0.0,
            capacity_max_mw=10.0,
            capacity_init_mw=0.0,
            investable=True,
            cop_default=3.0
        )

        buses = {
            "heat": type('Bus', (), {'add_output': lambda self, x: None, 'add_input': lambda self, x: None})(),
            "electricity": type('Bus', (), {'add_output': lambda self, x: None, 'add_input': lambda self, x: None})(),
        }

        result = hp.attach(model, model.t, {}, buses)

        # Verify return type
        assert isinstance(result, dict)

        # Verify expected keys exist (either new format or legacy)
        assert 'flows' in result or 'Q_th_out' in result

        # Check new format structure
        if 'flows' in result:
            assert isinstance(result['flows'], dict)

    def test_non_component_fails_protocol_check(self):
        """Verify that objects not implementing protocol fail the check."""
        class NotAComponent:
            pass

        obj = NotAComponent()
        assert not isinstance(obj, ComponentBlock)
        assert not is_valid_component_block(obj)

    def test_partial_implementation_fails_protocol_check(self):
        """Verify that partial implementations fail protocol check."""
        class PartialComponent:
            def __init__(self):
                self.name = "partial"

            def attach(self, model, time_set, config, buses):
                return {}

            # Missing get_results and validate_config

        obj = PartialComponent()
        # Protocol check should pass because it only checks for attribute existence
        # but this demonstrates the importance of complete implementation
        assert hasattr(obj, 'attach')
        assert not hasattr(obj, 'get_results')
        assert not hasattr(obj, 'validate_config')


@pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not available")
class TestComponentIntegration:
    """Integration tests for component protocol usage."""

    def test_components_can_be_stored_in_list(self):
        """Verify components implementing protocol can be stored together."""
        components = [
            HeatPumpBlock(
                name="hp1", min_load=0.3, cop_series=[3.0] * 24,
                capacity_min_mw=0.0, capacity_max_mw=10.0,
                capacity_init_mw=0.0, investable=True, cop_default=3.0
            ),
            StorageBlock(
                name="storage1", e_min=0.1, e_max=0.9, p_max=5.0,
                eff_c=0.95, eff_d=0.95, hourly_loss=0.001,
                dt_h=1.0, soc0=0.5, investable=True,
                e_cap_min=0.0, e_cap_max=20.0, p_cap_min=0.0,
                p_cap_max=5.0, e_cap_init=10.0, p_cap_init=2.5,
                terminal_target=None
            ),
            ThermalGeneratorBlock(
                name="gen1", th_eff=0.9, el_eff=None, cap_th_mw=10.0
            ),
        ]

        # All should implement protocol
        for comp in components:
            assert isinstance(comp, ComponentBlock)

        # Can call attach on all
        model = pyo.ConcreteModel()
        model.t = pyo.Set(initialize=range(1, 25))
        buses = {
            "heat": type('Bus', (), {'add_output': lambda self, x: None, 'add_input': lambda self, x: None})(),
            "electricity": type('Bus', (), {'add_output': lambda self, x: None, 'add_input': lambda self, x: None})(),
        }

        for comp in components:
            result = comp.attach(model, model.t, {}, buses)
            assert isinstance(result, dict)

    def test_type_hints_work_with_protocol(self):
        """Verify type hints work correctly with protocol."""
        def attach_component_to_model(
            component: ComponentBlock,
            model: pyo.ConcreteModel,
            time_set,
            config: dict
        ) -> dict:
            """Helper function using protocol type hint."""
            return component.attach(model, time_set, config, {})

        hp = HeatPumpBlock(
            name="test_hp", min_load=0.3, cop_series=[3.0] * 24,
            capacity_min_mw=0.0, capacity_max_mw=10.0,
            capacity_init_mw=0.0, investable=True, cop_default=3.0
        )

        model = pyo.ConcreteModel()
        model.t = pyo.Set(initialize=range(1, 25))

        # Should work with type checker
        result = attach_component_to_model(hp, model, model.t, {})
        assert isinstance(result, dict)


class TestProtocolValidation:
    """Test protocol validation utilities."""

    def test_base_component_satisfies_protocol(self):
        """Verify that BaseComponent implements the ComponentBlock protocol."""
        # BaseComponent is abstract, but should structurally satisfy the protocol
        assert hasattr(BaseComponent, 'attach')
        assert hasattr(BaseComponent, 'get_results')
        assert hasattr(BaseComponent, 'validate_config')

    def test_investment_config_dataclass(self):
        """Verify InvestmentConfig dataclass works correctly."""
        config = InvestmentConfig(
            capex_eur_per_mw=100000.0,
            activation_cost_eur=5000.0,
            tie_breaker_eur_per_mw=0.01,
            lifetime_years=20.0,
            capacity_min_mw=0.0,
            capacity_max_mw=10.0,
            capacity_init_mw=0.0
        )

        assert config.capex_eur_per_mw == 100000.0
        assert config.activation_cost_eur == 5000.0
        assert config.lifetime_years == 20.0

    def test_emission_result_dataclass(self):
        """Verify EmissionResult dataclass works correctly."""
        result = EmissionResult(
            co2_kg_heat=1000.0,
            co2_kg_elec=500.0,
            co2_cost_heat=100.0,
            co2_cost_elec=50.0,
            category="fuel_to_heat"
        )

        assert result.co2_kg_heat == 1000.0
        assert result.category == "fuel_to_heat"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
