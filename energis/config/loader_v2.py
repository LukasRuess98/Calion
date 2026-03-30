"""
Configuration loader for EnerGIS v2.0.

Loads new config structure: tech_library → assets → scenarios
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

from energis.config.schemas import (
    # Asset schemas
    ComponentAsset,
    HeatPumpAsset,
    StorageAsset,
    GeneratorAsset,
    P2HAsset,
    GridConnection,
    # Network schemas
    NetworkTopology,
    # Tech library schemas
    HeatPumpTechnology,
    StorageTechnology,
    GeneratorTechnology,
    P2HTechnology,
    PipeTechnology,
    FuelProperties,
    # Scenario schemas
    Scenario,
)


class ConfigLoaderV2:
    """Configuration loader for v2.0 config structure."""

    def __init__(self, scenario_path: str):
        """
        Initialize config loader.

        Args:
            scenario_path: Path to scenario YAML file
        """
        self.scenario_path = Path(scenario_path)
        self.scenario_dir = self.scenario_path.parent
        self.config_root = self.scenario_dir.parent

        # Loaded data
        self.scenario: Optional[Scenario] = None
        self.tech_library: Dict[str, Any] = {}
        self.components: Dict[str, ComponentAsset] = {}
        self.grid: Optional[GridConnection] = None
        self.network: Optional[NetworkTopology] = None

    def load(self) -> Dict[str, Any]:
        """
        Load complete configuration.

        Returns:
            Dictionary with all configuration data
        """
        # 1. Load scenario
        self.scenario = self._load_scenario()

        # 2. Load tech library
        self.tech_library = self._load_tech_library()

        # 3. Load assets
        self._load_assets()

        # 4. Build unified config dict (for backward compatibility)
        return self._build_unified_config()

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML file."""
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve path relative to scenario file."""
        return (self.scenario_dir / relative_path).resolve()

    def _load_scenario(self) -> Scenario:
        """Load scenario configuration."""
        data = self._load_yaml(self.scenario_path)
        return Scenario.from_dict(data)

    def _load_tech_library(self) -> Dict[str, Any]:
        """Load technology library."""
        tech_lib_dir = self.config_root / "tech_library"

        tech_library = {
            'heat_pumps': {},
            'storage': {},
            'generators': {},
            'p2h': {},
            'pipes': {},
            'fluids': {},
            'fuels': {},
        }

        # Load heat pumps
        hp_path = tech_lib_dir / "heat_pumps.yaml"
        if hp_path.exists():
            data = self._load_yaml(hp_path)
            hp_data = data.get('heat_pumps', {})
            tech_library['heat_pumps'] = {
                tech_id: HeatPumpTechnology.from_dict(tech_id, tech_data)
                for tech_id, tech_data in hp_data.items()
            }

        # Load storage
        storage_path = tech_lib_dir / "storage.yaml"
        if storage_path.exists():
            data = self._load_yaml(storage_path)
            storage_data = data.get('storage', {})
            tech_library['storage'] = {
                tech_id: StorageTechnology.from_dict(tech_id, tech_data)
                for tech_id, tech_data in storage_data.items()
            }

        # Load generators
        gen_path = tech_lib_dir / "generators.yaml"
        if gen_path.exists():
            data = self._load_yaml(gen_path)
            gen_data = data.get('generators', {})
            tech_library['generators'] = {
                tech_id: GeneratorTechnology.from_dict(tech_id, tech_data)
                for tech_id, tech_data in gen_data.items()
            }

        # Load P2H
        p2h_path = tech_lib_dir / "p2h.yaml"
        if p2h_path.exists():
            data = self._load_yaml(p2h_path)
            p2h_data = data.get('p2h', {})
            tech_library['p2h'] = {
                tech_id: P2HTechnology.from_dict(tech_id, tech_data)
                for tech_id, tech_data in p2h_data.items()
            }

        # Load pipes
        pipes_path = tech_lib_dir / "pipes.yaml"
        if pipes_path.exists():
            data = self._load_yaml(pipes_path)
            pipes_data = data.get('pipes', {})
            tech_library['pipes'] = {
                tech_id: PipeTechnology.from_dict(tech_id, tech_data)
                for tech_id, tech_data in pipes_data.items()
            }

        # Load fluids (raw dict for now)
        fluids_path = tech_lib_dir / "fluids.yaml"
        if fluids_path.exists():
            data = self._load_yaml(fluids_path)
            tech_library['fluids'] = data.get('fluids', {})

        # Load fuels
        fuels_path = tech_lib_dir / "fuels.yaml"
        if fuels_path.exists():
            data = self._load_yaml(fuels_path)
            fuels_data = data.get('fuels', {})
            tech_library['fuels'] = {
                fuel_id: FuelProperties.from_dict(fuel_id, fuel_data)
                for fuel_id, fuel_data in fuels_data.items()
            }

        return tech_library

    def _load_assets(self):
        """Load asset configurations."""
        # Load components
        components_path = self._resolve_path(self.scenario.assets.components)
        components_data = self._load_yaml(components_path)

        # Parse heat pumps
        hp_data = components_data.get('heat_pumps', {})
        for hp_id, hp_config in hp_data.items():
            self.components[hp_id] = HeatPumpAsset.from_dict(hp_id, hp_config)

        # Parse storage
        storage_data = components_data.get('storage', {})
        for storage_id, storage_config in storage_data.items():
            self.components[storage_id] = StorageAsset.from_dict(storage_id, storage_config)

        # Parse CHP plants
        chp_data = components_data.get('chp_plants', {})
        for chp_id, chp_config in chp_data.items():
            self.components[chp_id] = GeneratorAsset.from_dict(chp_id, chp_config)

        # Parse boilers
        boiler_data = components_data.get('boilers', {})
        for boiler_id, boiler_config in boiler_data.items():
            self.components[boiler_id] = GeneratorAsset.from_dict(boiler_id, boiler_config)

        # Parse P2H
        p2h_data = components_data.get('p2h', {})
        for p2h_id, p2h_config in p2h_data.items():
            self.components[p2h_id] = P2HAsset.from_dict(p2h_id, p2h_config)

        # Parse waste heat sources (as GeneratorAsset with zero fuel cost)
        waste_heat_data = components_data.get('waste_heat_sources', {})
        for wh_id, wh_config in waste_heat_data.items():
            self.components[wh_id] = GeneratorAsset.from_dict(wh_id, wh_config)

        # Load grid connection
        grid_path = self._resolve_path(self.scenario.assets.grid)
        grid_data = self._load_yaml(grid_path)
        self.grid = GridConnection.from_dict(grid_data.get('grid_connection', {}))

        # Load network topology
        network_path = self._resolve_path(self.scenario.assets.network)
        network_data = self._load_yaml(network_path)
        self.network = NetworkTopology.from_dict(network_data)

    def _build_unified_config(self) -> Dict[str, Any]:
        """
        Build unified config dict for backward compatibility.

        This creates a config structure that system_builder.py can understand.
        """
        config = {
            # Scenario metadata
            'scenario': {
                'name': self.scenario.name,
                'description': self.scenario.description,
                'version': self.scenario.version,
            },

            # Time configuration
            'run': {
                'dt_h': self.scenario.time.resolution_h,
                'start': self.scenario.time.start,
                'end': self.scenario.time.end,
            },

            # Optimization mode
            'optimization': {
                'mode': self.scenario.optimization.mode,
                'objective': self.scenario.optimization.objective,
            },

            # Economics
            'costs': {
                'co2_price_eur_per_tonne': self.scenario.economics.co2_price_eur_per_tonne,
                'heat_dump_penalty_eur_per_mwh': self.scenario.economics.heat_dump_penalty_eur_per_mwh,
                'discount_rate': self.scenario.economics.discount_rate,
            },

            # Grid connection
            'grid': {
                'max_import_mw': self.grid.max_import_mw,
                'max_export_mw': self.grid.max_export_mw,
                'buy_fees_eur_per_mwh': self.grid.buy_fees_total_eur_per_mwh,
                'sell_haircut': self.grid.sell_haircut_fraction,
                'demand_charge_eur_per_mw': self.grid.annual_charge_eur_per_mw,
                'wholesale_price_column': self.grid.wholesale_price_column,
            },

            # Initial state
            'initial_state': {},

            # Terminal conditions
            'terminal_conditions': {},

            # Solver
            'solver': {
                'name': self.scenario.solver.name,
                'timelimit_s': self.scenario.solver.timelimit_s,
                'mip_gap': self.scenario.solver.mip_gap,
                'threads': self.scenario.solver.threads,
                'options': self.scenario.solver.options,
            },

            # Components (will be populated below)
            'system': {},

            # Tech library reference
            '_tech_library': self.tech_library,

            # Schema objects (for type-safe access)
            '_schemas': {
                'scenario': self.scenario,
                'components': self.components,
                'grid': self.grid,
                'network': self.network,
            },
        }

        # Build component configs (backward compatible format)
        self._build_component_configs(config)

        # Add fuel prices
        config['costs']['fuel_prices'] = {}
        for fuel_id, fuel in self.tech_library['fuels'].items():
            config['costs']['fuel_prices'][fuel_id] = fuel.default_price_eur_per_mwh

        # Override with scenario-specific fuel prices
        config['costs']['fuel_prices'].update(self.scenario.economics.fuel_prices)

        return config

    def _build_component_configs(self, config: Dict[str, Any]):
        """Build component configs in backward-compatible format."""
        system = config['system']

        # Heat pumps
        system['heat_pumps'] = []
        for comp_id, comp in self.components.items():
            if isinstance(comp, HeatPumpAsset):
                # Get technology from library
                tech = self.tech_library['heat_pumps'].get(comp.technology)
                if not tech:
                    continue

                hp_config = {
                    'id': comp.id,
                    'enabled': True,
                    'max_th_mw': comp.existing.thermal_capacity_mw,
                    'min_load': tech.min_load_fraction,
                    'type': comp.technology,
                }

                # Waste heat source
                if comp.waste_heat_source:
                    hp_config['wrg_source_column'] = comp.waste_heat_source.get('temperature_column')
                    hp_config['wrg_power_column'] = comp.waste_heat_source.get('available_power_column')

                # Investment
                if comp.expansion.enabled:
                    hp_config['investment'] = {
                        'enabled': True,
                        'min_capacity_mw': comp.expansion.min_additional_capacity_mw,
                        'max_capacity_mw': comp.expansion.max_additional_capacity_mw,
                        'capex_eur_per_mw': comp.expansion.capex_eur_per_mw,
                        'lifetime_yr': comp.expansion.lifetime_yr,
                    }

                system['heat_pumps'].append(hp_config)

        # Storage
        system['storage'] = []
        for comp_id, comp in self.components.items():
            if isinstance(comp, StorageAsset):
                tech = self.tech_library['storage'].get(comp.technology)
                if not tech:
                    continue

                storage_config = {
                    'id': comp.id,
                    'enabled': True,
                    'capacity_mwh': comp.existing.energy_capacity_mwh or 0.0,
                    'power_mw': comp.existing.power_capacity_mw or 0.0,
                    'efficiency': tech.charge_efficiency,
                    'loss_factor': tech.hourly_loss_factor,
                }

                # Investment
                if comp.expansion.enabled:
                    storage_config['investment'] = {
                        'enabled': True,
                        'min_energy_mwh': comp.expansion.min_additional_energy_mwh,
                        'max_energy_mwh': comp.expansion.max_additional_energy_mwh,
                        'energy_capex_eur_per_mwh': comp.expansion.energy_capex_eur_per_mwh,
                        'lifetime_yr': comp.expansion.lifetime_yr,
                    }

                system['storage'].append(storage_config)

        # Thermal generators (CHP + Boilers + Waste Heat)
        system['thermal_generators'] = []
        for comp_id, comp in self.components.items():
            if isinstance(comp, GeneratorAsset):
                tech = self.tech_library['generators'].get(comp.technology)
                if not tech:
                    continue

                gen_config = {
                    'id': comp.id,
                    'enabled': True,
                    'max_th_mw': comp.existing.thermal_capacity_mw,
                    'efficiency': tech.thermal_efficiency,
                    'fuel_type': tech.fuel_type,
                    'min_load': tech.min_load_fraction,
                    'type': tech.type,
                }

                # For CHP
                if comp.existing.electrical_capacity_mw:
                    gen_config['max_el_mw'] = comp.existing.electrical_capacity_mw
                    gen_config['electrical_efficiency'] = tech.electrical_efficiency

                # Investment
                if comp.expansion.enabled:
                    gen_config['investment'] = {
                        'enabled': True,
                        'min_capacity_mw': comp.expansion.min_additional_capacity_mw,
                        'max_capacity_mw': comp.expansion.max_additional_capacity_mw,
                        'capex_eur_per_mw': comp.expansion.capex_eur_per_mw,
                        'lifetime_yr': comp.expansion.lifetime_yr,
                    }

                system['thermal_generators'].append(gen_config)

        # P2H
        system['p2h'] = []
        for comp_id, comp in self.components.items():
            if isinstance(comp, P2HAsset):
                tech = self.tech_library['p2h'].get(comp.technology)
                if not tech:
                    continue

                p2h_config = {
                    'id': comp.id,
                    'enabled': True,
                    'max_th_mw': comp.existing.thermal_capacity_mw,
                    'efficiency': tech.electric_to_thermal_efficiency,
                    'min_load': tech.min_load_fraction,
                }

                # Investment
                if comp.expansion.enabled:
                    p2h_config['investment'] = {
                        'enabled': True,
                        'min_capacity_mw': comp.expansion.min_additional_capacity_mw,
                        'max_capacity_mw': comp.expansion.max_additional_capacity_mw,
                        'capex_eur_per_mw': comp.expansion.capex_eur_per_mw,
                        'lifetime_yr': comp.expansion.lifetime_yr,
                    }

                system['p2h'].append(p2h_config)


def load_config_v2(scenario_path: str) -> Dict[str, Any]:
    """
    Load v2.0 configuration structure.

    Args:
        scenario_path: Path to scenario YAML file

    Returns:
        Unified config dictionary
    """
    loader = ConfigLoaderV2(scenario_path)
    return loader.load()
