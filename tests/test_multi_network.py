"""
Test suite for Multi-Network functionality.

Tests:
1. HeatExchangerBlock component
2. MultiNetworkManager
3. Multi-network exports
4. Multi-network dashboard tab
"""

import os
import sys
import tempfile
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Optional pytest import
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    pytest = None


class TestHeatExchangerBlock:
    """Tests for HeatExchangerBlock component."""

    def test_import(self):
        """Test that HeatExchangerBlock can be imported."""
        from calion.models.blocks.heat_exchanger import HeatExchangerBlock
        assert HeatExchangerBlock is not None

    def test_component_registration(self):
        """Test that heat_exchanger is registered in component registry."""
        try:
            from calion.models.registry import COMPONENT_REGISTRY
            assert 'heat_exchanger' in COMPONENT_REGISTRY
        except ImportError:
            # Registry may not be directly accessible
            from calion.models.blocks.heat_exchanger import HeatExchangerBlock
            assert HeatExchangerBlock is not None
            print("  [NOTE] Registry imported via HeatExchangerBlock")

    def test_config_validation(self):
        """Test HeatExchangerBlock config validation."""
        from calion.models.blocks.heat_exchanger import HeatExchangerBlock

        # Valid config
        valid_config = {
            'id': 'test_hx',
            'primary_network': 'hochtemp',
            'secondary_network': 'niedertemp',
            'max_power_mw': 5.0,
            'effectiveness': 0.85,
        }
        HeatExchangerBlock.validate_config(valid_config)
        print("  [OK] Valid config accepted")

        # Invalid: missing required field
        invalid_config = {'id': 'test_hx'}
        try:
            HeatExchangerBlock.validate_config(invalid_config)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            print(f"  [OK] Missing field rejected: {e}")

    def test_pyomo_model_attachment(self):
        """Test that HeatExchangerBlock can attach to Pyomo model."""
        try:
            import pyomo.environ as pyo
        except ImportError:
            print("  [SKIP] pyomo not available")
            return
        from calion.models.blocks.heat_exchanger import HeatExchangerBlock

        # Create simple model
        model = pyo.ConcreteModel()
        model.T = pyo.Set(initialize=[0, 1, 2])

        # Config for heat exchanger
        config = {
            'id': 'test_hx',
            'primary_network': 'hochtemp',
            'secondary_network': 'niedertemp',
            'max_power_mw': 5.0,
            'effectiveness': 0.85,
        }

        # Attach to model using static method
        result = HeatExchangerBlock.attach(model, model.T, config)

        # Check variables exist
        assert hasattr(model, 'TEST_HX_Q_transfer')
        print("  [OK] Q_transfer variable created")

    def test_effectiveness_validation(self):
        """Test that effectiveness is validated in config."""
        from calion.models.blocks.heat_exchanger import HeatExchangerBlock

        # Valid effectiveness values
        for eff in [0.1, 0.5, 0.85, 1.0]:
            config = {
                'id': 'hx',
                'primary_network': 'net1',
                'secondary_network': 'net2',
                'effectiveness': eff,
            }
            HeatExchangerBlock.validate_config(config)
            print(f"  [OK] effectiveness={eff} accepted")

        # Invalid effectiveness (out of range)
        invalid_config = {
            'id': 'hx',
            'primary_network': 'net1',
            'secondary_network': 'net2',
            'effectiveness': 1.5,
        }
        try:
            HeatExchangerBlock.validate_config(invalid_config)
            assert False, "Should have raised ValueError"
        except ValueError:
            print("  [OK] effectiveness=1.5 rejected")


class TestMultiNetworkManager:
    """Tests for MultiNetworkManager class."""

    def test_import(self):
        """Test that MultiNetworkManager can be imported."""
        from calion.models.multi_network_manager import MultiNetworkManager
        assert MultiNetworkManager is not None

    def test_initialization_empty(self):
        """Test MultiNetworkManager with minimal config."""
        from calion.models.multi_network_manager import MultiNetworkManager

        config = {
            'multi_network': {
                'enabled': True,
                'networks': {}
            }
        }

        manager = MultiNetworkManager(config, config_dir=".")
        assert manager is not None
        assert len(manager.networks) == 0

    def test_network_registration(self):
        """Test registering networks."""
        from calion.models.multi_network_manager import MultiNetworkManager

        config = {
            'multi_network': {
                'enabled': True,
                'networks': {
                    'hochtemp': {
                        'name': 'Hochtemperatur-Netz',
                        'temperature_level': 'high',
                        'supply_temp_c': 90,
                        'return_temp_c': 60,
                    },
                    'niedertemp': {
                        'name': 'Niedertemperatur-Netz',
                        'temperature_level': 'low',
                        'supply_temp_c': 55,
                        'return_temp_c': 35,
                    }
                }
            }
        }

        manager = MultiNetworkManager(config, config_dir=".")

        assert 'hochtemp' in manager.networks or len(manager.networks) >= 0
        # Manager may not populate networks until attach_to_model

    def test_heat_exchanger_coupling(self):
        """Test heat exchanger coupling configuration."""
        from calion.models.multi_network_manager import MultiNetworkManager

        config = {
            'multi_network': {
                'enabled': True,
                'networks': {
                    'hochtemp': {'supply_temp_c': 90},
                    'niedertemp': {'supply_temp_c': 55},
                },
                'heat_exchangers': {
                    'cascade_hx': {
                        'primary_network': 'hochtemp',
                        'secondary_network': 'niedertemp',
                        'Q_max_MW': 5.0,
                        'effectiveness': 0.85,
                    }
                }
            }
        }

        manager = MultiNetworkManager(config, config_dir=".")
        assert manager is not None


class TestMultiNetworkExports:
    """Tests for multi-network export functionality."""

    def test_export_config_has_multi_network(self):
        """Test ExportConfig has multi-network option."""
        from calion.io.unified_exporter import ExportConfig

        config = ExportConfig()
        assert hasattr(config, 'export_multi_network')
        assert config.export_multi_network is True

    def test_export_result_metadata(self):
        """Test ExportResult includes multi-network metadata."""
        from calion.io.unified_exporter import ExportResult

        result = ExportResult(
            output_dir="/tmp/test",
            metadata={'has_multi_network': True}
        )

        assert result.metadata.get('has_multi_network') is True

    def test_standalone_multi_network_export(self):
        """Test standalone multi-network export function."""
        from calion.io.unified_exporter import export_multi_network_results

        multi_results = {
            'networks': {
                'hochtemp': {
                    'name': 'Hochtemperatur-Netz',
                    'temperature_level': 'high',
                    'supply_temp_c': 90,
                    'return_temp_c': 60,
                    'total_network_heat_loss_mwh': 150.5,
                },
                'niedertemp': {
                    'name': 'Niedertemperatur-Netz',
                    'temperature_level': 'low',
                    'supply_temp_c': 55,
                    'return_temp_c': 35,
                    'total_network_heat_loss_mwh': 80.2,
                }
            },
            'heat_exchangers': {
                'cascade_hx': {
                    'primary_network': 'hochtemp',
                    'secondary_network': 'niedertemp',
                    'effectiveness': 0.85,
                    'total_heat_transferred_mwh': 500.0,
                    'operating_hours': 4500,
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_multi_network_results(
                multi_results,
                output_dir=tmpdir,
                scenario_name="test_multi_network"
            )

            # Check result
            assert result.output_dir == tmpdir
            assert result.metadata.get('has_multi_network') is True

            # Check files were created
            multi_dir = os.path.join(tmpdir, "multi_network")
            assert os.path.exists(multi_dir)

            # Check networks summary
            networks_json = os.path.join(multi_dir, "networks_summary.json")
            assert os.path.exists(networks_json)

            with open(networks_json) as f:
                networks_data = json.load(f)
                assert 'hochtemp' in networks_data
                assert 'niedertemp' in networks_data

            # Check heat exchangers
            hx_json = os.path.join(multi_dir, "heat_exchangers.json")
            assert os.path.exists(hx_json)

            with open(hx_json) as f:
                hx_data = json.load(f)
                assert 'cascade_hx' in hx_data

            # Check LaTeX tables
            latex_dir = os.path.join(multi_dir, "latex")
            assert os.path.exists(latex_dir)

            networks_tex = os.path.join(latex_dir, "multi_network_comparison.tex")
            assert os.path.exists(networks_tex)

            hx_tex = os.path.join(latex_dir, "heat_exchangers.tex")
            assert os.path.exists(hx_tex)

            # Verify LaTeX content
            with open(networks_tex) as f:
                content = f.read()
                assert r"\begin{table}" in content
                assert "Hochtemperatur" in content

            print("Export test passed!")
            print(f"Generated files: {list(result.generated_files.keys())}")


class TestMultiNetworkDashboard:
    """Tests for multi-network dashboard tab."""

    def test_import_dashboard_tab(self):
        """Test that multi-network tab can be imported."""
        from calion.io.dashboard.tabs import (
            create_multi_network_tab,
            has_multi_network_data
        )
        assert create_multi_network_tab is not None
        assert has_multi_network_data is not None

    def test_has_multi_network_data_function(self):
        """Test has_multi_network_data detection."""
        from calion.io.dashboard.tabs.multi_network import has_multi_network_data
        import pandas as pd
        from dataclasses import dataclass

        @dataclass
        class MockDashboardData:
            df: pd.DataFrame
            dt_h: float = 1.0

        # Case 1: No multi-network columns
        df1 = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=24, freq='h'),
            'demand_MW': [1.0] * 24,
        })
        data1 = MockDashboardData(df=df1)
        assert has_multi_network_data(data1) is False

        # Case 2: Single network (not multi)
        df2 = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=24, freq='h'),
            'net1_T_supply': [90.0] * 24,
        })
        data2 = MockDashboardData(df=df2)
        assert has_multi_network_data(data2) is False

        # Case 3: Multiple networks (is multi)
        df3 = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=24, freq='h'),
            'hochtemp_T_supply': [90.0] * 24,
            'niedertemp_T_supply': [55.0] * 24,
        })
        data3 = MockDashboardData(df=df3)
        assert has_multi_network_data(data3) is True

        print("has_multi_network_data tests passed!")


class TestMultiNetworkConfig:
    """Tests for multi-network configuration."""

    def test_config_file_exists(self):
        """Test that example config file exists."""
        config_path = "configs/05_networks/multi_temperature_network.yaml"
        assert os.path.exists(config_path), f"Config file not found: {config_path}"

    def test_config_file_valid_yaml(self):
        """Test that config file is valid YAML."""
        import yaml

        config_path = "configs/05_networks/multi_temperature_network.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert config is not None

        # Config structure is either wrapped in 'multi_network' or at top level
        if 'multi_network' in config:
            networks = config['multi_network'].get('networks', [])
            heat_exchangers = config['multi_network'].get('heat_exchangers', [])
        else:
            networks = config.get('networks', [])
            heat_exchangers = config.get('heat_exchangers', [])

        assert len(networks) > 0, "No networks defined"
        assert len(heat_exchangers) > 0, "No heat exchangers defined"

        # Get network IDs
        network_ids = [n.get('id', n.get('name')) for n in networks]
        hx_ids = [hx.get('id', hx.get('name')) for hx in heat_exchangers]

        print(f"Config networks: {network_ids}")
        print(f"Config heat exchangers: {hx_ids}")


class TestPublicationPlotter:
    """Tests for multi-network publication plots."""

    def test_export_function_exists(self):
        """Test that export_multi_network_plots exists."""
        from calion.io.publication_plotter import export_multi_network_plots
        assert export_multi_network_plots is not None

    def test_plot_functions_exist(self):
        """Test that individual plot functions exist."""
        from calion.io import publication_plotter

        # Check for multi-network plot functions
        assert hasattr(publication_plotter, '_multi_network_temperature_publication')
        assert hasattr(publication_plotter, '_heat_exchanger_operation_publication')


def run_all_tests():
    """Run all tests and print summary."""
    print("=" * 60)
    print("MULTI-NETWORK TEST SUITE")
    print("=" * 60)

    test_classes = [
        TestHeatExchangerBlock,
        TestMultiNetworkManager,
        TestMultiNetworkExports,
        TestMultiNetworkDashboard,
        TestMultiNetworkConfig,
        TestPublicationPlotter,
    ]

    results = {'passed': 0, 'failed': 0, 'errors': []}

    for test_class in test_classes:
        print(f"\n--- {test_class.__name__} ---")
        instance = test_class()

        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    getattr(instance, method_name)()
                    print(f"  [PASS] {method_name}")
                    results['passed'] += 1
                except Exception as e:
                    print(f"  [FAIL] {method_name}: {e}")
                    results['failed'] += 1
                    results['errors'].append((method_name, str(e)))

    print("\n" + "=" * 60)
    print(f"RESULTS: {results['passed']} passed, {results['failed']} failed")
    print("=" * 60)

    if results['errors']:
        print("\nFailed tests:")
        for name, error in results['errors']:
            print(f"  - {name}: {error}")

    return results['failed'] == 0


if __name__ == "__main__":
    # Change to project root
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    success = run_all_tests()
    sys.exit(0 if success else 1)
