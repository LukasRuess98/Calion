"""
CO2 Emissions Calculator Service for CALION Framework.

Centralizes all CO2 emission tracking logic that was previously duplicated
across system_builder.py. Provides a consistent interface for:
- Grid electricity emissions (heat pumps, P2H → grid CO2 factor time series)
- Fuel combustion emissions (thermal generators, CHP → fuel emission factors)
- CHP emissions with heat/electricity split by efficiency

Replaces duplicated patterns from:
- system_builder.py lines 332-354 (Heat Pump: Grid → Electricity)
- system_builder.py lines 862-931 (Thermal Generator: Fuel → Heat/Electricity)
- system_builder.py lines 805-826 (P2H: Grid → Electricity)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CO2Result:
    """
    Container for CO2 emission calculations.

    Separates emissions by category:
    - heat_kg / elec_kg: Emissions in kg attributed to heat vs electricity
    - heat_eur / elec_eur: CO2 cost in EUR for each category
    - total_kg / total_eur: Total combined emissions and costs
    - component_type: Type of emitting component ('heat_pump', 'p2h',
                      'thermal_generator', 'chp')

    All fields are Pyomo-compatible (can hold expressions or floats).
    """
    heat_kg: Any       # Pyomo expression or float [kg CO2]
    elec_kg: Any       # Pyomo expression or float [kg CO2]
    heat_eur: Any      # Pyomo expression or float [EUR]
    elec_eur: Any      # Pyomo expression or float [EUR]
    total_kg: Any      # Pyomo expression or float [kg CO2]
    total_eur: Any     # Pyomo expression or float [EUR]
    component_type: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage in model.co2_component_costs."""
        return {
            'heat_kg': self.heat_kg,
            'elec_kg': self.elec_kg,
            'heat_eur': self.heat_eur,
            'elec_eur': self.elec_eur,
            'total_kg': self.total_kg,
            'total_eur': self.total_eur,
            'type': self.component_type,
        }


class EmissionsCalculator:
    """
    Service class for calculating CO2 emission expressions.

    Encapsulates the emission factor and co2 price logic that was
    previously repeated for each component type in system_builder.py.
    The caller provides Pyomo variables/expressions; this service returns
    CO2Result objects with standardized cost breakdown.

    Args:
        co2_price_param: Pyomo parameter or float for CO2 price [EUR/t CO2]
        grid_co2_series: Dict mapping time index → grid emission factor [kg CO2/MWh]
        dt_h: Time step duration in hours
        time_set: Iterable of time indices (e.g., model.t)
    """

    def __init__(
        self,
        co2_price_param: Any,  # pyo.Param or float
        grid_co2_series: dict[int, float],
        dt_h: float,
        time_set: Any,  # pyo.Set or range
    ):
        self.co2_price = co2_price_param
        self.grid_co2_series = grid_co2_series
        self.dt_h = dt_h
        self.time_set = time_set

    def calculate_grid_electricity_emissions(
        self,
        electricity_var: Any,  # pyo.Var or pyo.Expression (indexed by time)
        component_type: str,
    ) -> CO2Result:
        """
        Calculate CO2 emissions from grid electricity consumption.

        Used for heat pumps and P2H converters where electricity comes from
        the grid and emissions are determined by the marginal grid emission
        factor (time-varying).

        Formula:
            co2_kg = Σ_t (elec_var[t] * grid_co2[t] * dt_h)
            co2_cost_eur = co2_price [EUR/t] / 1000 [kg/t] * co2_kg

        Args:
            electricity_var: Pyomo expression for electricity consumption [MW]
                             indexed by time set
            component_type: Type name for result metadata ('heat_pump', 'p2h')

        Returns:
            CO2Result with all cost terms. For grid electricity:
            - heat_kg = 0 (electricity consumed, not heat)
            - elec_kg = total grid-related emissions [kg CO2]
            - heat_eur = 0
            - elec_eur = CO2 cost [EUR]
        """
        co2_kg = sum(
            electricity_var[t] * self.grid_co2_series[t - 1] * self.dt_h
            for t in self.time_set
        )
        co2_cost_eur = (self.co2_price / 1000.0) * co2_kg

        return CO2Result(
            heat_kg=0,
            elec_kg=co2_kg,
            heat_eur=0,
            elec_eur=co2_cost_eur,
            total_kg=co2_kg,
            total_eur=co2_cost_eur,
            component_type=component_type,
        )

    def calculate_fuel_emissions(
        self,
        fuel_var: Any,  # pyo.Var (indexed by time)
        fuel_ef_kg_per_mwh: float,
        is_chp: bool = False,
        th_eff: float = 1.0,
        el_eff: float = 0.0,
        fuel_bus: str = "gas",
    ) -> CO2Result:
        """
        Calculate CO2 emissions from fuel combustion.

        For thermal generators (heat-only and CHP).

        Heat-only generator:
            All emissions attributed to heat production.
            co2_heat_kg = Σ_t (fuel[t] * emission_factor * dt_h)

        CHP generator (heat + electricity):
            Emissions split proportionally by efficiency:
            heat_fraction = th_eff / (th_eff + el_eff)
            elec_fraction = el_eff / (th_eff + el_eff)

        Args:
            fuel_var: Pyomo variable for fuel consumption [MW fuel], time-indexed
            fuel_ef_kg_per_mwh: Emission factor [kg CO2/MWh_fuel]
            is_chp: True if component has electrical output (CHP mode)
            th_eff: Thermal efficiency (used for CHP split only)
            el_eff: Electrical efficiency (used for CHP split only; 0 for heat-only)
            fuel_bus: Fuel type ('gas', 'biomass', 'waste') for metadata

        Returns:
            CO2Result with heat/electricity split as appropriate.
            For heat-only: heat_kg has total, elec_kg = 0.
            For CHP: split proportionally by efficiency.
        """
        # Total fuel-based emissions
        fuel_co2_kg = sum(
            fuel_var[t] * fuel_ef_kg_per_mwh * self.dt_h
            for t in self.time_set
        )

        if not is_chp or (th_eff + el_eff) <= 0:
            # Heat-only generator: all CO2 → heat
            co2_heat_kg = fuel_co2_kg
            co2_elec_kg = 0
            co2_heat_cost = (self.co2_price / 1000.0) * co2_heat_kg
            co2_elec_cost = 0
            comp_type = "thermal_generator"
        else:
            # CHP: split proportionally by output efficiency
            total_eff = th_eff + el_eff
            heat_fraction = th_eff / total_eff
            elec_fraction = el_eff / total_eff

            co2_heat_kg = fuel_co2_kg * heat_fraction
            co2_elec_kg = fuel_co2_kg * elec_fraction
            co2_heat_cost = (self.co2_price / 1000.0) * co2_heat_kg
            co2_elec_cost = (self.co2_price / 1000.0) * co2_elec_kg
            comp_type = "chp"

        return CO2Result(
            heat_kg=co2_heat_kg,
            elec_kg=co2_elec_kg,
            heat_eur=co2_heat_cost,
            elec_eur=co2_elec_cost,
            total_kg=fuel_co2_kg,
            total_eur=(self.co2_price / 1000.0) * fuel_co2_kg,
            component_type=comp_type,
        )


def aggregate_emission_results(results: list[CO2Result]) -> dict[str, Any]:
    """
    Aggregate multiple CO2Result objects into summary totals.

    Computes total heat, total electricity, and total combined emissions
    and costs for the objective function.

    Args:
        results: List of CO2Result objects from all components

    Returns:
        Dictionary with aggregated lists suitable for building objective terms:
        {
            'co2_kg_heat_terms': [...],
            'co2_kg_elec_terms': [...],
            'co2_cost_heat_terms': [...],
            'co2_cost_elec_terms': [...],
            'co2_kg_fuel_to_heat': [...],  # Fuel → Heat
            'co2_kg_fuel_to_elec': [...],  # Fuel → Electricity (CHP)
            'co2_kg_grid_to_elec': [...],  # Grid → Electricity (HP, P2H)
        }
    """
    aggregated = {
        'co2_kg_heat_terms': [],
        'co2_kg_elec_terms': [],
        'co2_cost_heat_terms': [],
        'co2_cost_elec_terms': [],
        'co2_kg_fuel_to_heat': [],
        'co2_kg_fuel_to_elec': [],
        'co2_kg_grid_to_elec': [],
    }

    for result in results:
        # Add non-zero heat emissions
        if result.heat_kg != 0:
            aggregated['co2_kg_heat_terms'].append(result.heat_kg)
        if result.heat_eur != 0:
            aggregated['co2_cost_heat_terms'].append(result.heat_eur)

        # Add non-zero electricity emissions
        if result.elec_kg != 0:
            aggregated['co2_kg_elec_terms'].append(result.elec_kg)
        if result.elec_eur != 0:
            aggregated['co2_cost_elec_terms'].append(result.elec_eur)

        # Categorize by source
        if result.component_type in ('heat_pump', 'p2h'):
            if result.elec_kg != 0:
                aggregated['co2_kg_grid_to_elec'].append(result.elec_kg)
        elif result.component_type == 'thermal_generator':
            if result.heat_kg != 0:
                aggregated['co2_kg_fuel_to_heat'].append(result.heat_kg)
        elif result.component_type == 'chp':
            if result.heat_kg != 0:
                aggregated['co2_kg_fuel_to_heat'].append(result.heat_kg)
            if result.elec_kg != 0:
                aggregated['co2_kg_fuel_to_elec'].append(result.elec_kg)

    return aggregated


__all__ = [
    "CO2Result",
    "EmissionsCalculator",
    "aggregate_emission_results",
]
