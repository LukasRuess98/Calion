"""
Configuration Manager for EnerGIS v2.0.

High-level interface for loading and managing configurations.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from energis.config.loader_v2 import load_config_v2, ConfigLoaderV2
from energis.config.validation import validate_config, ValidationResult


class ConfigManager:
    """
    High-level configuration manager.

    Handles loading, validation, and access to configuration.
    """

    def __init__(self, scenario_path: str, validate: bool = True):
        """
        Initialize configuration manager.

        Args:
            scenario_path: Path to scenario YAML file
            validate: Whether to validate configuration after loading
        """
        self.scenario_path = Path(scenario_path)
        self.config: Optional[Dict[str, Any]] = None
        self.validation_result: Optional[ValidationResult] = None
        self._validate = validate

    def load(self) -> Dict[str, Any]:
        """
        Load configuration.

        Returns:
            Loaded configuration dictionary

        Raises:
            FileNotFoundError: If scenario file not found
            ValidationError: If validation fails (and validate=True)
        """
        if not self.scenario_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {self.scenario_path}")

        print(f"[ConfigManager] Loading configuration from {self.scenario_path}")

        # Load configuration
        self.config = load_config_v2(str(self.scenario_path))

        print(f"[ConfigManager] Configuration loaded successfully")
        print(f"  - Scenario: {self.config['scenario']['name']}")
        print(f"  - Components: {len(self.config['_schemas']['components'])}")
        print(f"  - Networks: {len(self.config['_schemas']['network'].networks)}")

        # Validate if requested
        if self._validate:
            self.validation_result = validate_config(self.config)

            if not self.validation_result.valid:
                print(f"\n[ConfigManager] Configuration has {len(self.validation_result.errors)} error(s)")
                self.validation_result.print_summary()
                raise ValueError("Configuration validation failed")

            if self.validation_result.warnings:
                print(f"\n[ConfigManager] Configuration has {len(self.validation_result.warnings)} warning(s)")
                for warning in self.validation_result.warnings:
                    loc = f" [{warning.location}]" if warning.location else ""
                    print(f"  - {warning.message}{loc}")

            print(f"[ConfigManager] Validation passed")

        return self.config

    @property
    def scenario(self):
        """Get scenario configuration (type-safe)."""
        if not self.config:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self.config['_schemas']['scenario']

    @property
    def components(self):
        """Get component assets (type-safe)."""
        if not self.config:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self.config['_schemas']['components']

    @property
    def grid(self):
        """Get grid connection (type-safe)."""
        if not self.config:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self.config['_schemas']['grid']

    @property
    def network(self):
        """Get network topology (type-safe)."""
        if not self.config:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self.config['_schemas']['network']

    @property
    def tech_library(self):
        """Get technology library."""
        if not self.config:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self.config['_tech_library']

    def get_component(self, component_id: str):
        """
        Get a specific component by ID.

        Args:
            component_id: Component ID

        Returns:
            ComponentAsset instance

        Raises:
            KeyError: If component not found
        """
        return self.components[component_id]

    def get_network(self, network_id: str):
        """
        Get a specific network by ID.

        Args:
            network_id: Network ID

        Returns:
            ThermalNetwork instance

        Raises:
            KeyError: If network not found
        """
        return self.network.networks[network_id]

    def print_summary(self):
        """Print configuration summary."""
        if not self.config:
            print("[ConfigManager] No configuration loaded")
            return

        print("\n" + "=" * 60)
        print("CONFIGURATION SUMMARY")
        print("=" * 60)

        # Scenario info
        scenario = self.scenario
        print(f"\nScenario: {scenario.name}")
        print(f"  Version: {scenario.version}")
        print(f"  Mode: {scenario.optimization.mode}")

        # Components
        print(f"\nComponents ({len(self.components)}):")
        for comp_id, comp in self.components.items():
            capacity = comp.existing.thermal_capacity_mw
            expansion_text = ""
            if comp.expansion.enabled:
                expansion_text = f" [+{comp.expansion.min_additional_capacity_mw:.0f}-{comp.expansion.max_additional_capacity_mw:.0f} MW expansion]"
            print(f"  - {comp_id}: {capacity:.1f} MW ({comp.technology}){expansion_text}")

        # Network
        if self.network:
            print(f"\nNetworks ({len(self.network.networks)}):")
            for net_id, net in self.network.networks.items():
                print(f"  - {net_id}: {len(net.nodes)} nodes, {len(net.pipes)} pipes")

        # Economics
        econ = scenario.economics
        print(f"\nEconomics:")
        print(f"  - CO2 price: {econ.co2_price_eur_per_tonne:.0f} EUR/t")
        print(f"  - Discount rate: {econ.discount_rate*100:.1f}%")

        # Solver
        solver = scenario.solver
        print(f"\nSolver:")
        print(f"  - Name: {solver.name}")
        print(f"  - Time limit: {solver.timelimit_s}s")
        print(f"  - MIP gap: {solver.mip_gap*100:.1f}%")

        print("=" * 60 + "\n")


def load_and_validate_config(scenario_path: str, validate: bool = True) -> Dict[str, Any]:
    """
    Convenience function to load and validate configuration.

    Args:
        scenario_path: Path to scenario YAML file
        validate: Whether to validate configuration

    Returns:
        Loaded configuration dictionary

    Example:
        >>> config = load_and_validate_config("configs_new/scenarios/stadtbach_baseline_2023.yaml")
        >>> scenario = config['_schemas']['scenario']
        >>> print(scenario.name)
    """
    manager = ConfigManager(scenario_path, validate=validate)
    return manager.load()
