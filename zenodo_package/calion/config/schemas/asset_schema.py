"""
Asset configuration schemas.

Defines Pydantic models for component assets with existing + expansion model.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssetCapacity(BaseModel):
    """Capacity specification (existing or expansion)."""

    model_config = ConfigDict(populate_by_name=True)

    # Thermal capacity
    thermal_capacity_mw: float = Field(default=0.0, ge=0)

    # Electrical capacity (for CHP)
    electrical_capacity_mw: float | None = Field(default=None, ge=0)

    # Storage-specific
    energy_capacity_mwh: float | None = Field(default=None, ge=0)
    power_capacity_mw: float | None = Field(default=None, ge=0)

    # Commissioning info (for existing assets)
    commissioning_year: int | None = None
    remaining_lifetime_yr: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetCapacity:
        """Create from dictionary."""
        return cls(
            thermal_capacity_mw=float(data.get('thermal_capacity_mw', 0.0)),
            electrical_capacity_mw=float(data['electrical_capacity_mw']) if 'electrical_capacity_mw' in data else None,
            energy_capacity_mwh=float(data['energy_capacity_mwh']) if 'energy_capacity_mwh' in data else None,
            power_capacity_mw=float(data['power_capacity_mw']) if 'power_capacity_mw' in data else None,
            commissioning_year=int(data['commissioning_year']) if 'commissioning_year' in data else None,
            remaining_lifetime_yr=int(data['remaining_lifetime_yr']) if 'remaining_lifetime_yr' in data else None,
        )


class ExpansionPotential(BaseModel):
    """Expansion/investment potential for an asset."""

    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = False

    # Capacity bounds
    min_additional_capacity_mw: float = Field(default=0.0, ge=0)
    max_additional_capacity_mw: float = Field(default=0.0, ge=0)

    # Storage-specific
    min_additional_energy_mwh: float | None = Field(default=None, ge=0)
    max_additional_energy_mwh: float | None = Field(default=None, ge=0)
    min_additional_power_mw: float | None = Field(default=None, ge=0)
    max_additional_power_mw: float | None = Field(default=None, ge=0)

    # Coupling (e.g., P = 0.1 * E for storage)
    power_energy_coupling: float | None = None

    # Costs
    capex_eur_per_mw: float = Field(default=0.0, ge=0)
    energy_capex_eur_per_mwh: float | None = Field(default=None, ge=0)
    power_capex_eur_per_mw: float | None = Field(default=None, ge=0)
    opex_eur_per_mw_yr: float = Field(default=0.0, ge=0)
    activation_cost_eur: float = Field(default=0.0, ge=0)
    lifetime_yr: float = Field(default=20.0, gt=0)

    @model_validator(mode='after')
    def _check_capacity_ordering(self) -> ExpansionPotential:
        if (self.enabled and
                self.max_additional_capacity_mw < self.min_additional_capacity_mw):
            raise ValueError(
                "max_additional_capacity_mw must be >= min_additional_capacity_mw"
            )
        return self

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExpansionPotential:
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


class ComponentAsset(BaseModel):
    """Base class for component assets."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    description: str
    technology: str

    existing: AssetCapacity
    expansion: ExpansionPotential

    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, asset_id: str, data: dict[str, Any]) -> ComponentAsset:
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


class HeatPumpAsset(ComponentAsset):
    """Heat pump asset with waste heat source configuration."""

    waste_heat_source: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, asset_id: str, data: dict[str, Any]) -> HeatPumpAsset:
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
            waste_heat_source=data.get('waste_heat_source', {}),
        )


class StorageAsset(ComponentAsset):
    """Thermal storage asset."""

    @classmethod
    def from_dict(cls, asset_id: str, data: dict[str, Any]) -> StorageAsset:
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


class GeneratorAsset(ComponentAsset):
    """Thermal generator (boiler, CHP) asset."""

    @classmethod
    def from_dict(cls, asset_id: str, data: dict[str, Any]) -> GeneratorAsset:
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


class P2HAsset(ComponentAsset):
    """Power-to-Heat asset."""

    @classmethod
    def from_dict(cls, asset_id: str, data: dict[str, Any]) -> P2HAsset:
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


class GridConnection(BaseModel):
    """Grid connection and pricing configuration."""

    model_config = ConfigDict(populate_by_name=True)

    # Connection
    voltage_level_kv: float = Field(ge=0)
    max_import_mw: float = Field(ge=0)
    max_export_mw: float = Field(ge=0)
    connection_point_id: str

    # Pricing
    wholesale_price_column: str
    buy_fees_total_eur_per_mwh: float = Field(ge=0)
    sell_haircut_fraction: float = Field(ge=0, le=1)
    sell_spread_eur_per_mwh: float
    floor_price_eur_per_mwh: float

    # Demand charges
    demand_charges_enabled: bool
    annual_charge_eur_per_mw: float = Field(ge=0)

    # Emissions
    co2_intensity_column: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GridConnection:
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
