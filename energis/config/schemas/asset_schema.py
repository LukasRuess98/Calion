"""
Asset configuration schemas.

Defines dataclasses for component assets with existing + expansion model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Any


@dataclass
class AssetCapacity:
    """Capacity specification (existing or expansion)."""

    # Thermal capacity
    thermal_capacity_mw: float = 0.0

    # Electrical capacity (for CHP)
    electrical_capacity_mw: Optional[float] = None

    # Storage-specific
    energy_capacity_mwh: Optional[float] = None
    power_capacity_mw: Optional[float] = None

    # Commissioning info (for existing assets)
    commissioning_year: Optional[int] = None
    remaining_lifetime_yr: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AssetCapacity:
        """Create from dictionary."""
        return cls(
            thermal_capacity_mw=float(data.get('thermal_capacity_mw', 0.0)),
            electrical_capacity_mw=float(data['electrical_capacity_mw']) if 'electrical_capacity_mw' in data else None,
            energy_capacity_mwh=float(data['energy_capacity_mwh']) if 'energy_capacity_mwh' in data else None,
            power_capacity_mw=float(data['power_capacity_mw']) if 'power_capacity_mw' in data else None,
            commissioning_year=int(data['commissioning_year']) if 'commissioning_year' in data else None,
            remaining_lifetime_yr=int(data['remaining_lifetime_yr']) if 'remaining_lifetime_yr' in data else None,
        )


@dataclass
class ExpansionPotential:
    """Expansion/investment potential for an asset."""

    enabled: bool = False

    # Capacity bounds
    min_additional_capacity_mw: float = 0.0
    max_additional_capacity_mw: float = 0.0

    # Storage-specific
    min_additional_energy_mwh: Optional[float] = None
    max_additional_energy_mwh: Optional[float] = None
    min_additional_power_mw: Optional[float] = None
    max_additional_power_mw: Optional[float] = None

    # Coupling (e.g., P = 0.1 * E for storage)
    power_energy_coupling: Optional[float] = None

    # Costs
    capex_eur_per_mw: float = 0.0
    energy_capex_eur_per_mwh: Optional[float] = None
    power_capex_eur_per_mw: Optional[float] = None
    opex_eur_per_mw_yr: float = 0.0
    activation_cost_eur: float = 0.0
    lifetime_yr: float = 20.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExpansionPotential:
        """Create from dictionary."""
        return cls(
            enabled=bool(data.get('enabled', False)),
            min_additional_capacity_mw=float(data.get('min_additional_capacity_mw', 0.0)),
            max_additional_capacity_mw=float(data.get('max_additional_capacity_mw', 0.0)),
            min_additional_energy_mwh=float(data['min_additional_energy_mwh']) if 'min_additional_energy_mwh' in data else None,
            max_additional_energy_mwh=float(data['max_additional_energy_mwh']) if 'max_additional_energy_mwh' in data else None,
            min_additional_power_mw=float(data['min_additional_power_mw']) if 'min_additional_power_mw' in data else None,
            max_additional_power_mw=float(data['max_additional_power_mw']) if 'max_additional_power_mw' in data else None,
            power_energy_coupling=float(data['power_energy_coupling']) if data.get('power_energy_coupling') is not None else None,
            capex_eur_per_mw=float(data.get('capex_eur_per_mw', 0.0)),
            energy_capex_eur_per_mwh=float(data['energy_capex_eur_per_mwh']) if 'energy_capex_eur_per_mwh' in data else None,
            power_capex_eur_per_mw=float(data['power_capex_eur_per_mw']) if 'power_capex_eur_per_mw' in data else None,
            opex_eur_per_mw_yr=float(data.get('opex_eur_per_mw_yr', 0.0)),
            activation_cost_eur=float(data.get('activation_cost_eur', 0.0)),
            lifetime_yr=float(data.get('lifetime_yr', 20.0)),
        )


@dataclass
class ComponentAsset:
    """Base class for component assets."""

    id: str
    description: str
    technology: str

    existing: AssetCapacity
    expansion: ExpansionPotential

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, asset_id: str, data: Dict[str, Any]) -> ComponentAsset:
        """Create from dictionary."""
        existing_data = data.get('existing', {})
        expansion_data = data.get('expansion', {})

        return cls(
            id=asset_id,
            description=str(data.get('description', '')),
            technology=str(data.get('technology', '')),
            existing=AssetCapacity.from_dict(existing_data),
            expansion=ExpansionPotential.from_dict(expansion_data),
            metadata=data.get('metadata', {}),
        )


@dataclass
class HeatPumpAsset(ComponentAsset):
    """Heat pump asset with waste heat source configuration."""

    waste_heat_source: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, asset_id: str, data: Dict[str, Any]) -> HeatPumpAsset:
        """Create from dictionary."""
        base = ComponentAsset.from_dict(asset_id, data)
        return cls(
            id=base.id,
            description=base.description,
            technology=base.technology,
            existing=base.existing,
            expansion=base.expansion,
            metadata=base.metadata,
            waste_heat_source=data.get('waste_heat_source', {}),
        )


@dataclass
class StorageAsset(ComponentAsset):
    """Thermal storage asset."""

    @classmethod
    def from_dict(cls, asset_id: str, data: Dict[str, Any]) -> StorageAsset:
        """Create from dictionary."""
        base = ComponentAsset.from_dict(asset_id, data)
        return cls(
            id=base.id,
            description=base.description,
            technology=base.technology,
            existing=base.existing,
            expansion=base.expansion,
            metadata=base.metadata,
        )


@dataclass
class GeneratorAsset(ComponentAsset):
    """Thermal generator (boiler, CHP) asset."""

    @classmethod
    def from_dict(cls, asset_id: str, data: Dict[str, Any]) -> GeneratorAsset:
        """Create from dictionary."""
        base = ComponentAsset.from_dict(asset_id, data)
        return cls(
            id=base.id,
            description=base.description,
            technology=base.technology,
            existing=base.existing,
            expansion=base.expansion,
            metadata=base.metadata,
        )


@dataclass
class P2HAsset(ComponentAsset):
    """Power-to-Heat asset."""

    @classmethod
    def from_dict(cls, asset_id: str, data: Dict[str, Any]) -> P2HAsset:
        """Create from dictionary."""
        base = ComponentAsset.from_dict(asset_id, data)
        return cls(
            id=base.id,
            description=base.description,
            technology=base.technology,
            existing=base.existing,
            expansion=base.expansion,
            metadata=base.metadata,
        )


@dataclass
class GridConnection:
    """Grid connection and pricing configuration."""

    # Connection
    voltage_level_kv: float
    max_import_mw: float
    max_export_mw: float
    connection_point_id: str

    # Pricing
    wholesale_price_column: str
    buy_fees_total_eur_per_mwh: float
    sell_haircut_fraction: float
    sell_spread_eur_per_mwh: float
    floor_price_eur_per_mwh: float

    # Demand charges
    demand_charges_enabled: bool
    annual_charge_eur_per_mw: float

    # Emissions
    co2_intensity_column: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GridConnection:
        """Create from dictionary."""
        connection = data.get('connection', {})
        pricing = data.get('pricing', {})
        buy_fees = pricing.get('buy_fees', {})
        sell_model = pricing.get('sell_model', {})
        demand_charges = data.get('demand_charges', {})
        emissions = data.get('emissions', {})

        return cls(
            voltage_level_kv=float(connection.get('voltage_level_kv', 20.0)),
            max_import_mw=float(connection.get('max_import_mw', 100.0)),
            max_export_mw=float(connection.get('max_export_mw', 50.0)),
            connection_point_id=str(connection.get('connection_point_id', '')),
            wholesale_price_column=str(pricing.get('wholesale', {}).get('price_column', 'strompreis_EUR_MWh')),
            buy_fees_total_eur_per_mwh=float(buy_fees.get('total_buy_fees_eur_per_mwh', 22.6)),
            sell_haircut_fraction=float(sell_model.get('haircut_fraction', 0.05)),
            sell_spread_eur_per_mwh=float(sell_model.get('spread_eur_per_mwh', 2.0)),
            floor_price_eur_per_mwh=float(sell_model.get('floor_price_eur_per_mwh', 0.0)),
            demand_charges_enabled=bool(demand_charges.get('enabled', True)),
            annual_charge_eur_per_mw=float(demand_charges.get('annual_charge_eur_per_mw', 50000.0)),
            co2_intensity_column=str(emissions.get('co2_intensity', {}).get('intensity_column', 'grid_co2_kg_MWh')),
        )
