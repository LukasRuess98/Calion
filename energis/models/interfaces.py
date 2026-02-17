"""
Formal interfaces and protocols for EnerGIS framework components.

This module defines the contracts that different parts of the system must follow,
enabling better type checking, clearer documentation, and easier testing.

Key protocols:
- ComponentBlock: Interface for all optimization component blocks
- InvestmentStrategy: Interface for investment cost calculation
- CO2Calculator: Interface for emissions calculation
- ResultExtractor: Interface for extracting results from solved models

These protocols use typing.Protocol which enables structural subtyping (duck typing)
while still providing static type checking capabilities.
"""
from __future__ import annotations

from typing import Protocol, Dict, Any, List, Optional, runtime_checkable, Tuple
from dataclasses import dataclass

try:
    import pyomo.environ as pyo
except Exception:  # pragma: no cover - optional dependency
    pyo = None


# Re-export core abstractions from component module for convenience
from .component import Component, Flow, InvestmentResult, BaseComponent, BusType


@runtime_checkable
class ComponentBlock(Protocol):
    """
    Formal interface for all component blocks in the optimization model.

    This protocol ensures that all components follow a consistent pattern for:
    1. Validation of configuration
    2. Attachment to Pyomo models
    3. Result extraction from solved models

    Components implementing this protocol can be used interchangeably in the
    model building process.

    Example implementations: HeatPumpBlock, StorageBlock, ThermalGeneratorBlock
    """

    name: str

    def attach(
        self,
        model: Any,  # pyo.ConcreteModel
        time_set: Any,  # pyo.Set
        config: Dict[str, Any],
        buses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Attach component to the optimization model.

        Creates all necessary variables, parameters, constraints, and expressions
        for this component. Registers flows with the bus system.

        Args:
            model: Pyomo ConcreteModel to attach to
            time_set: Pyomo Set representing time indices
            config: Configuration dictionary for the component
            buses: Dictionary of bus objects for flow registration

        Returns:
            Dictionary with standardized structure:
            {
                'flows': {
                    'heat': {'output': pyo.Var, 'input': pyo.Var},
                    'electricity': {'input': pyo.Var},
                    ...
                },
                'investment': InvestmentResult or None,
                'state': pyo.Var or None,  # For storage components
                'metadata': Dict[str, Any]  # Component-specific data
            }

        Raises:
            RuntimeError: If Pyomo is not available
            ValueError: If configuration is invalid
        """
        ...

    def get_results(
        self,
        model: Any,  # Solved pyo.ConcreteModel
        time_set: Any
    ) -> Dict[str, Any]:
        """
        Extract results from a solved optimization model.

        Args:
            model: Solved Pyomo model
            time_set: Time set used in the model

        Returns:
            Dictionary with extracted results including flow values,
            state variables, and component-specific outputs
        """
        ...

    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate component configuration before model building.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If configuration is invalid or inconsistent
        """
        ...


@dataclass
class InvestmentConfig:
    """
    Configuration for investment optimization.

    Standardized container for all investment-related parameters used
    across different component types (heat pumps, storage, generators, etc.).

    Attributes:
        capex_eur_per_mw: Capital expenditure per MW capacity
        activation_cost_eur: One-time activation/build cost
        tie_breaker_eur_per_mw: Small cost to break ties in optimization
        lifetime_years: Expected lifetime for annualization calculation
        capacity_min_mw: Minimum investable capacity
        capacity_max_mw: Maximum investable capacity
        capacity_init_mw: Initial/existing capacity
    """
    capex_eur_per_mw: float
    activation_cost_eur: float = 0.0
    tie_breaker_eur_per_mw: float = 0.01
    lifetime_years: float = 20.0
    capacity_min_mw: float = 0.0
    capacity_max_mw: float = float('inf')
    capacity_init_mw: float = 0.0


@dataclass
class InvestmentCostResult:
    """
    Result container for investment cost calculations.

    Contains all cost expressions and variables related to an investment decision.

    Attributes:
        capex_expr: Pyomo expression for annualized capital costs
        activation_expr: Pyomo expression for activation/build costs
        tie_breaker_expr: Pyomo expression for tie-breaking costs
        capacity_var: Pyomo variable for capacity decision
        build_var: Pyomo binary variable for build decision
    """
    capex_expr: Any  # Pyomo expression
    activation_expr: Any  # Pyomo expression
    tie_breaker_expr: Any  # Pyomo expression
    capacity_var: Any  # pyo.Var
    build_var: Any  # pyo.Var (binary)


@runtime_checkable
class InvestmentStrategy(Protocol):
    """
    Strategy interface for investment cost calculation.

    Enables different investment calculation approaches (e.g., with/without
    annualization, different activation cost models, technology-specific
    cost structures).

    This protocol follows the Strategy pattern, allowing investment logic
    to be varied independently from component logic.
    """

    def create_investment_variables(
        self,
        model: Any,  # pyo.ConcreteModel
        component_name: str,
        config: InvestmentConfig
    ) -> Tuple[Any, Any]:
        """
        Create investment decision variables.

        Args:
            model: Pyomo model to add variables to
            component_name: Name of the component (for variable naming)
            config: Investment configuration

        Returns:
            Tuple of (capacity_var, build_var)
        """
        ...

    def calculate_costs(
        self,
        capacity_var: Any,  # pyo.Var
        build_var: Any,  # pyo.Var
        config: InvestmentConfig
    ) -> InvestmentCostResult:
        """
        Calculate all investment cost terms.

        Args:
            capacity_var: Pyomo variable for capacity
            build_var: Pyomo binary variable for build decision
            config: Investment configuration

        Returns:
            InvestmentCostResult with all cost expressions
        """
        ...


@dataclass
class EmissionResult:
    """
    Container for CO2 emission calculations.

    Separates emissions by category (heat vs electricity, fuel vs grid)
    for detailed tracking and reporting.

    Attributes:
        co2_kg_heat: CO2 emissions in kg attributed to heat production
        co2_kg_elec: CO2 emissions in kg attributed to electricity consumption
        co2_cost_heat: CO2 cost in EUR for heat-related emissions
        co2_cost_elec: CO2 cost in EUR for electricity-related emissions
        category: Emission category (e.g., "fuel_to_heat", "grid_to_elec")
    """
    co2_kg_heat: Any  # Pyomo expression or float
    co2_kg_elec: Any  # Pyomo expression or float
    co2_cost_heat: Any  # Pyomo expression or float
    co2_cost_elec: Any  # Pyomo expression or float
    category: str


@runtime_checkable
class CO2Calculator(Protocol):
    """
    Strategy interface for CO2 emissions calculation.

    Supports different emission calculation methods:
    - Fuel combustion emissions (based on fuel type and consumption)
    - Grid electricity emissions (based on grid emission factor time series)
    - Process emissions

    This protocol enables consistent emission tracking across all components
    while allowing for different calculation methodologies.
    """

    def calculate_fuel_emissions(
        self,
        fuel_consumption: Any,  # pyo.Var or pyo.Expression
        fuel_emission_factor: float,  # kg CO2 per MWh
        category: str
    ) -> EmissionResult:
        """
        Calculate emissions from fuel combustion.

        Args:
            fuel_consumption: Pyomo variable/expression for fuel consumption [MW]
            fuel_emission_factor: Emission factor [kg CO2/MWh_fuel]
            category: Emission category ("fuel_to_heat", "fuel_to_elec", etc.)

        Returns:
            EmissionResult with CO2 quantities and costs
        """
        ...

    def calculate_grid_emissions(
        self,
        electricity_var: Any,  # pyo.Var or pyo.Expression
        grid_co2_series: Dict[int, float]  # Time-indexed emission factors
    ) -> EmissionResult:
        """
        Calculate emissions from grid electricity consumption.

        Args:
            electricity_var: Pyomo variable/expression for electricity [MW]
            grid_co2_series: Time series of grid emission factors [kg CO2/MWh]

        Returns:
            EmissionResult with CO2 quantities and costs
        """
        ...


@runtime_checkable
class ResultExtractor(Protocol):
    """
    Interface for extracting results from solved optimization models.

    Provides a consistent way to extract and format results from different
    types of optimization models and components.
    """

    def extract_timeseries(
        self,
        model: Any,  # Solved pyo.ConcreteModel
        time_set: Any,
        variable_name: str
    ) -> List[float]:
        """
        Extract time series from a Pyomo variable.

        Args:
            model: Solved Pyomo model
            time_set: Time indices
            variable_name: Name of the variable to extract

        Returns:
            List of values indexed by time
        """
        ...

    def extract_scalar(
        self,
        model: Any,
        variable_name: str
    ) -> float:
        """
        Extract a scalar value from the model.

        Args:
            model: Solved Pyomo model
            variable_name: Name of the variable/parameter

        Returns:
            Scalar value
        """
        ...


# Utility functions for protocol validation

def is_valid_component_block(obj: Any) -> bool:
    """
    Check if an object implements the ComponentBlock protocol.

    Args:
        obj: Object to check

    Returns:
        True if object implements ComponentBlock protocol
    """
    return isinstance(obj, ComponentBlock)


def is_valid_investment_strategy(obj: Any) -> bool:
    """
    Check if an object implements the InvestmentStrategy protocol.

    Args:
        obj: Object to check

    Returns:
        True if object implements InvestmentStrategy protocol
    """
    return isinstance(obj, InvestmentStrategy)


def is_valid_co2_calculator(obj: Any) -> bool:
    """
    Check if an object implements the CO2Calculator protocol.

    Args:
        obj: Object to check

    Returns:
        True if object implements CO2Calculator protocol
    """
    return isinstance(obj, CO2Calculator)


__all__ = [
    # Core component abstractions (re-exported)
    'Component',
    'BaseComponent',
    'Flow',
    'InvestmentResult',
    'BusType',
    # Protocol interfaces
    'ComponentBlock',
    'InvestmentStrategy',
    'CO2Calculator',
    'ResultExtractor',
    # Data containers
    'InvestmentConfig',
    'InvestmentCostResult',
    'EmissionResult',
    # Validation utilities
    'is_valid_component_block',
    'is_valid_investment_strategy',
    'is_valid_co2_calculator',
]
