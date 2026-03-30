"""
Configuration Manager for CALION v2.0.

High-level interface for loading and managing configurations.
"""

from pathlib import Path
from typing import Any

from calion.config.loader_v2 import load_config_v2
from calion.config.validation import ValidationResult, validate_config
from calion.logging_config import get_logger

logger = get_logger(__name__)


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
        self.config: dict[str, Any] | None = None
        self.validation_result: ValidationResult | None = None
        self._validate = validate

    def load(self) -> dict[str, Any]:
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

        logger.info(f"[ConfigManager] Loading configuration from {self.scenario_path}")

        # Load configuration
        self.config = load_config_v2(str(self.scenario_path))

        logger.info("[ConfigManager] Configuration loaded successfully")
        logger.info(f"  - Scenario: {self.config['scenario']['name']}")
        logger.info(f"  - Components: {len(self.config['_schemas']['components'])}")
        logger.info(f"  - Networks: {len(self.config['_schemas']['network'].networks)}")

        # Validate if requested
        if self._validate:
            self.validation_result = validate_config(self.config)

            if not self.validation_result.valid:
                logger.info(f"\n[ConfigManager] Configuration has {len(self.validation_result.errors)} error(s)")
                self.validation_result.print_summary()
                raise ValueError("Configuration validation failed")

            if self.validation_result.warnings:
                logger.info(f"\n[ConfigManager] Configuration has {len(self.validation_result.warnings)} warning(s)")
                for warning in self.validation_result.warnings:
                    loc = f" [{warning.location}]" if warning.location else ""
                    logger.info(f"  - {warning.message}{loc}")

            logger.info("[ConfigManager] Validation passed")

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
            logger.info("[ConfigManager] No configuration loaded")
            return

        logger.info("=" * 60)
        logger.info("CONFIGURATION SUMMARY")
        logger.info("="*70)

        # Scenario info
        scenario = self.scenario
        logger.info(f"\nScenario: {scenario.name}")
        logger.info(f"  Version: {scenario.version}")
        logger.info(f"  Mode: {scenario.optimization.mode}")

        # Components
        logger.info(f"\nComponents ({len(self.components)}):")
        for comp_id, comp in self.components.items():
            capacity = comp.existing.thermal_capacity_mw
            expansion_text = ""
            if comp.expansion.enabled:
                expansion_text = f" [+{comp.expansion.min_additional_capacity_mw:.0f}-{comp.expansion.max_additional_capacity_mw:.0f} MW expansion]"
            logger.info(f"  - {comp_id}: {capacity:.1f} MW ({comp.technology}){expansion_text}")

        # Network
        if self.network:
            logger.info(f"\nNetworks ({len(self.network.networks)}):")
            for net_id, net in self.network.networks.items():
                logger.info(f"  - {net_id}: {len(net.nodes)} nodes, {len(net.pipes)} pipes")

        # Economics
        econ = scenario.economics
        logger.info("\nEconomics:")
        logger.info(f"  - CO2 price: {econ.co2_price_eur_per_tonne:.0f} EUR/t")
        logger.info(f"  - Discount rate: {econ.discount_rate*100:.1f}%")

        # Solver
        solver = scenario.solver
        logger.info("\nSolver:")
        logger.info(f"  - Name: {solver.name}")
        logger.info(f"  - Time limit: {solver.timelimit_s}s")
        logger.info(f"  - MIP gap: {solver.mip_gap*100:.1f}%")

        logger.info("=" * 60)


def load_and_validate_config(scenario_path: str, validate: bool = True) -> dict[str, Any]:
    """
    Convenience function to load and validate configuration.

    Args:
        scenario_path: Path to scenario YAML file
        validate: Whether to validate configuration

    Returns:
        Loaded configuration dictionary

    Example:
        >>> config = load_and_validate_config("configs/scenarios/stadtbach_baseline_2023.yaml")
        >>> scenario = config['_schemas']['scenario']
        >>> print(scenario.name)
    """
    manager = ConfigManager(scenario_path, validate=validate)
    return manager.load()
