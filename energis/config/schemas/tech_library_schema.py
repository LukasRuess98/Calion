"""
Technology library configuration schemas.

Defines dataclasses for reusable technology templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class COPModel:
    """COP (Coefficient of Performance) model for heat pumps."""

    type: str  # lookup_table_2d, polynomial, carnot_factor

    # For lookup_table_2d
    source_temps_K: List[float] = field(default_factory=list)
    sink_temps_K: List[float] = field(default_factory=list)
    cop_values: List[List[Optional[float]]] = field(default_factory=list)

    # For polynomial or carnot_factor
    coefficients: Dict[str, float] = field(default_factory=dict)
    carnot_efficiency: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> COPModel:
        """Create from dictionary."""
        lookup = data.get('lookup_table', {})

        return cls(
            type=str(data.get('type', 'lookup_table_2d')),
            source_temps_K=lookup.get('source_temps_K', []),
            sink_temps_K=lookup.get('sink_temps_K', []),
            cop_values=lookup.get('cop_values', []),
            coefficients=data.get('coefficients', {}),
            carnot_efficiency=float(data['carnot_efficiency']) if 'carnot_efficiency' in data else None,
        )


@dataclass
class HeatPumpTechnology:
    """Heat pump technology template."""

    id: str
    description: str

    # COP model
    cop_model: COPModel

    # Operational constraints
    min_load_fraction: float = 0.30
    max_modulation_rate_per_h: Optional[float] = None

    # Temperature limits
    min_source_temp_K: Optional[float] = None
    max_source_temp_K: Optional[float] = None
    min_sink_temp_K: Optional[float] = None
    max_sink_temp_K: Optional[float] = None

    # Costs
    capex_eur_per_mw_th: float = 400000.0
    opex_fixed_eur_per_mw_yr: float = 8000.0
    opex_variable_eur_per_mwh: float = 0.5
    lifetime_yr: float = 15.0

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, tech_id: str, data: Dict[str, Any]) -> HeatPumpTechnology:
        """Create from dictionary."""
        cop_model_data = data.get('cop_model', {})
        operational = data.get('operational', {})
        temp_limits = data.get('temperature_limits', {})
        costs = data.get('costs', {})

        return cls(
            id=tech_id,
            description=str(data.get('description', '')),
            cop_model=COPModel.from_dict(cop_model_data),
            min_load_fraction=float(operational.get('min_load_fraction', 0.30)),
            max_modulation_rate_per_h=float(operational['max_modulation_rate_per_h']) if 'max_modulation_rate_per_h' in operational else None,
            min_source_temp_K=float(temp_limits['min_source_temp_K']) if 'min_source_temp_K' in temp_limits else None,
            max_source_temp_K=float(temp_limits['max_source_temp_K']) if 'max_source_temp_K' in temp_limits else None,
            min_sink_temp_K=float(temp_limits['min_sink_temp_K']) if 'min_sink_temp_K' in temp_limits else None,
            max_sink_temp_K=float(temp_limits['max_sink_temp_K']) if 'max_sink_temp_K' in temp_limits else None,
            capex_eur_per_mw_th=float(costs.get('capex_eur_per_mw_th', 400000.0)),
            opex_fixed_eur_per_mw_yr=float(costs.get('opex_fixed_eur_per_mw_yr', 8000.0)),
            opex_variable_eur_per_mwh=float(costs.get('opex_variable_eur_per_mwh', 0.5)),
            lifetime_yr=float(costs.get('lifetime_yr', 15.0)),
            metadata=data.get('metadata', {}),
        )


@dataclass
class StorageTechnology:
    """Thermal storage technology template."""

    id: str
    description: str

    # Storage model
    model: str  # two_zone_stratified, single_zone, simplified

    # Efficiency
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    hourly_loss_factor: float = 0.9999  # (1 - loss_fraction)

    # Thermal properties (for stratified model)
    hot_zone_temp_c: Optional[float] = None
    cold_zone_temp_c: Optional[float] = None

    # Heat loss coefficients (W/(m²·K))
    U_top: float = 0.30
    U_side: float = 0.20
    U_bottom: float = 0.15

    # Geometry (for heat loss calculation)
    height_to_diameter_ratio: float = 2.0

    # Operational constraints
    min_soc_fraction: float = 0.05
    max_soc_fraction: float = 0.95
    max_charge_rate_fraction: float = 0.25  # Fraction of capacity per hour
    max_discharge_rate_fraction: float = 0.25

    # Costs
    capex_eur_per_mwh: float = 50000.0
    power_capex_eur_per_mw: float = 10000.0  # For charge/discharge capacity
    opex_fixed_eur_per_mwh_yr: float = 500.0
    lifetime_yr: float = 30.0

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, tech_id: str, data: Dict[str, Any]) -> StorageTechnology:
        """Create from dictionary."""
        efficiency = data.get('efficiency', {})
        thermal = data.get('thermal', {})
        heat_loss = data.get('heat_loss', {})
        geometry = data.get('geometry', {})
        operational = data.get('operational', {})
        costs = data.get('costs', {})

        return cls(
            id=tech_id,
            description=str(data.get('description', '')),
            model=str(data.get('model', 'two_zone_stratified')),
            charge_efficiency=float(efficiency.get('charge', 0.95)),
            discharge_efficiency=float(efficiency.get('discharge', 0.95)),
            hourly_loss_factor=float(efficiency.get('hourly_loss_factor', 0.9999)),
            hot_zone_temp_c=float(thermal['hot_zone_temp_c']) if 'hot_zone_temp_c' in thermal else None,
            cold_zone_temp_c=float(thermal['cold_zone_temp_c']) if 'cold_zone_temp_c' in thermal else None,
            U_top=float(heat_loss.get('U_top', 0.30)),
            U_side=float(heat_loss.get('U_side', 0.20)),
            U_bottom=float(heat_loss.get('U_bottom', 0.15)),
            height_to_diameter_ratio=float(geometry.get('height_to_diameter_ratio', 2.0)),
            min_soc_fraction=float(operational.get('min_soc_fraction', 0.05)),
            max_soc_fraction=float(operational.get('max_soc_fraction', 0.95)),
            max_charge_rate_fraction=float(operational.get('max_charge_rate_fraction', 0.25)),
            max_discharge_rate_fraction=float(operational.get('max_discharge_rate_fraction', 0.25)),
            capex_eur_per_mwh=float(costs.get('capex_eur_per_mwh', 50000.0)),
            power_capex_eur_per_mw=float(costs.get('power_capex_eur_per_mw', 10000.0)),
            opex_fixed_eur_per_mwh_yr=float(costs.get('opex_fixed_eur_per_mwh_yr', 500.0)),
            lifetime_yr=float(costs.get('lifetime_yr', 30.0)),
            metadata=data.get('metadata', {}),
        )


@dataclass
class GeneratorTechnology:
    """Thermal generator (boiler, CHP) technology template."""

    id: str
    description: str

    # Generator type
    type: str  # boiler, chp_extraction, chp_backpressure

    # Efficiency
    thermal_efficiency: float = 0.90
    electrical_efficiency: Optional[float] = None  # For CHP

    # Power-to-heat ratio (for CHP)
    power_to_heat_ratio: Optional[float] = None

    # Fuel
    fuel_type: str = "natural_gas"  # References tech_library/fuels.yaml

    # Operational constraints
    min_load_fraction: float = 0.40
    max_ramp_up_per_h: float = 1.0  # Fraction of capacity
    max_ramp_down_per_h: float = 1.0
    min_uptime_h: float = 1.0
    min_downtime_h: float = 1.0
    startup_time_h: float = 0.5

    # Costs
    capex_eur_per_mw_th: float = 200000.0
    startup_cost_eur: float = 1000.0
    opex_fixed_eur_per_mw_yr: float = 5000.0
    opex_variable_eur_per_mwh: float = 0.5
    lifetime_yr: float = 25.0

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, tech_id: str, data: Dict[str, Any]) -> GeneratorTechnology:
        """Create from dictionary."""
        efficiency = data.get('efficiency', {})
        fuel = data.get('fuel', {})
        operational = data.get('operational', {})
        costs = data.get('costs', {})

        # Handle nullable fields
        electrical_eff = efficiency.get('electrical')
        power_heat_ratio = data.get('power_to_heat_ratio')

        return cls(
            id=tech_id,
            description=str(data.get('description', '')),
            type=str(data.get('type', 'boiler')),
            thermal_efficiency=float(efficiency.get('thermal', 0.90)),
            electrical_efficiency=float(electrical_eff) if electrical_eff is not None else None,
            power_to_heat_ratio=float(power_heat_ratio) if power_heat_ratio is not None else None,
            fuel_type=str(fuel.get('type', 'natural_gas')),
            min_load_fraction=float(operational.get('min_load_fraction', 0.40)),
            max_ramp_up_per_h=float(operational.get('max_ramp_up_per_h', 1.0)),
            max_ramp_down_per_h=float(operational.get('max_ramp_down_per_h', 1.0)),
            min_uptime_h=float(operational.get('min_uptime_h', 1.0)),
            min_downtime_h=float(operational.get('min_downtime_h', 1.0)),
            startup_time_h=float(operational.get('startup_time_h', 0.5)),
            capex_eur_per_mw_th=float(costs.get('capex_eur_per_mw_th', 200000.0)),
            startup_cost_eur=float(costs.get('startup_cost_eur', 1000.0)),
            opex_fixed_eur_per_mw_yr=float(costs.get('opex_fixed_eur_per_mw_yr', 5000.0)),
            opex_variable_eur_per_mwh=float(costs.get('opex_variable_eur_per_mwh', 0.5)),
            lifetime_yr=float(costs.get('lifetime_yr', 25.0)),
            metadata=data.get('metadata', {}),
        )


@dataclass
class P2HTechnology:
    """Power-to-Heat technology template."""

    id: str
    description: str

    # Type
    type: str  # resistance_heater, electrode_boiler

    # Efficiency
    electric_to_thermal_efficiency: float = 0.99

    # Operational constraints
    min_load_fraction: float = 0.10
    max_ramp_up_per_h: float = 1.0
    max_ramp_down_per_h: float = 1.0

    # Costs
    capex_eur_per_mw_th: float = 50000.0
    opex_fixed_eur_per_mw_yr: float = 1000.0
    opex_variable_eur_per_mwh: float = 0.2
    lifetime_yr: float = 20.0

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, tech_id: str, data: Dict[str, Any]) -> P2HTechnology:
        """Create from dictionary."""
        efficiency = data.get('efficiency', {})
        operational = data.get('operational', {})
        costs = data.get('costs', {})

        return cls(
            id=tech_id,
            description=str(data.get('description', '')),
            type=str(data.get('type', 'resistance_heater')),
            electric_to_thermal_efficiency=float(efficiency.get('electric_to_thermal', 0.99)),
            min_load_fraction=float(operational.get('min_load_fraction', 0.10)),
            max_ramp_up_per_h=float(operational.get('max_ramp_up_per_h', 1.0)),
            max_ramp_down_per_h=float(operational.get('max_ramp_down_per_h', 1.0)),
            capex_eur_per_mw_th=float(costs.get('capex_eur_per_mw_th', 50000.0)),
            opex_fixed_eur_per_mw_yr=float(costs.get('opex_fixed_eur_per_mw_yr', 1000.0)),
            opex_variable_eur_per_mwh=float(costs.get('opex_variable_eur_per_mwh', 0.2)),
            lifetime_yr=float(costs.get('lifetime_yr', 20.0)),
            metadata=data.get('metadata', {}),
        )


@dataclass
class PipeTechnology:
    """Pipe technology template."""

    id: str
    description: str

    # Heat transfer coefficients (W/(m·K)) by diameter
    heat_transfer_coefficients: Dict[str, float] = field(default_factory=dict)

    # Hydraulic properties
    roughness_mm: float = 0.05
    friction_model: str = "darcy_weisbach"  # darcy_weisbach, hazen_williams

    # Material properties
    material: str = "steel"
    insulation_material: str = "mineral_wool"
    insulation_thickness_mm: float = 100.0

    # Costs (per meter)
    capex_eur_per_m_by_diameter: Dict[str, float] = field(default_factory=dict)
    opex_eur_per_m_yr: float = 10.0
    lifetime_yr: float = 40.0

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, tech_id: str, data: Dict[str, Any]) -> PipeTechnology:
        """Create from dictionary."""
        thermal = data.get('thermal', {})
        hydraulic = data.get('hydraulic', {})
        material_props = data.get('material', {})
        costs = data.get('costs', {})

        return cls(
            id=tech_id,
            description=str(data.get('description', '')),
            heat_transfer_coefficients=thermal.get('heat_transfer_coefficients', {}),
            roughness_mm=float(hydraulic.get('roughness_mm', 0.05)),
            friction_model=str(hydraulic.get('friction_model', 'darcy_weisbach')),
            material=str(material_props.get('material', 'steel')),
            insulation_material=str(material_props.get('insulation_material', 'mineral_wool')),
            insulation_thickness_mm=float(material_props.get('insulation_thickness_mm', 100.0)),
            capex_eur_per_m_by_diameter=costs.get('capex_eur_per_m_by_diameter', {}),
            opex_eur_per_m_yr=float(costs.get('opex_eur_per_m_yr', 10.0)),
            lifetime_yr=float(costs.get('lifetime_yr', 40.0)),
            metadata=data.get('metadata', {}),
        )


@dataclass
class FuelProperties:
    """Fuel properties template."""

    id: str
    description: str

    # Energy content
    lhv_kwh_per_kg: Optional[float] = None  # Lower heating value
    lhv_kwh_per_m3: Optional[float] = None  # For gaseous fuels
    hhv_kwh_per_kg: Optional[float] = None  # Higher heating value

    # Pricing
    default_price_eur_per_mwh: float = 40.0
    price_unit: str = "eur_per_mwh"  # eur_per_mwh, eur_per_kg, eur_per_m3

    # Emissions
    co2_kg_per_mwh_lhv: float = 0.0
    nox_kg_per_mwh: float = 0.0
    particulate_kg_per_mwh: float = 0.0

    # Availability
    renewable: bool = False
    carbon_neutral: bool = False

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, fuel_id: str, data: Dict[str, Any]) -> FuelProperties:
        """Create from dictionary."""
        energy = data.get('energy_content', {})
        pricing = data.get('pricing', {})
        emissions = data.get('emissions', {})
        availability = data.get('availability', {})

        return cls(
            id=fuel_id,
            description=str(data.get('description', '')),
            lhv_kwh_per_kg=float(energy['lhv_kwh_per_kg']) if 'lhv_kwh_per_kg' in energy else None,
            lhv_kwh_per_m3=float(energy['lhv_kwh_per_m3']) if 'lhv_kwh_per_m3' in energy else None,
            hhv_kwh_per_kg=float(energy['hhv_kwh_per_kg']) if 'hhv_kwh_per_kg' in energy else None,
            default_price_eur_per_mwh=float(pricing.get('default_price_eur_per_mwh', 40.0)),
            price_unit=str(pricing.get('price_unit', 'eur_per_mwh')),
            co2_kg_per_mwh_lhv=float(emissions.get('co2_kg_per_mwh_lhv', 0.0)),
            nox_kg_per_mwh=float(emissions.get('nox_kg_per_mwh', 0.0)),
            particulate_kg_per_mwh=float(emissions.get('particulate_kg_per_mwh', 0.0)),
            renewable=bool(availability.get('renewable', False)),
            carbon_neutral=bool(availability.get('carbon_neutral', False)),
            metadata=data.get('metadata', {}),
        )
