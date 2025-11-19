"""
Component abstraction for EnerGIS framework.

This module provides the base abstractions for all components in the framework,
including protocols, base classes, and flow definitions.

Inspired by Oemof.solph and PyPSA design patterns.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal, Protocol, runtime_checkable
from enum import Enum

try:
    import pyomo.environ as pyo
except Exception:  # pragma: no cover - optional dependency
    pyo = None


class BusType(Enum):
    """Supported bus types in the framework."""
    ELECTRICITY = "electricity"
    HEAT = "heat"
    COOLING = "cooling"
    FUEL_GAS = "fuel_gas"
    FUEL_BIOMASS = "fuel_biomass"
    FUEL_WASTE = "fuel_waste"
    HYDROGEN = "hydrogen"
    GENERIC = "generic"


@dataclass
class Flow:
    """
    Flow definition for connections between components and buses.

    Inspired by Oemof.solph Flow concept - provides explicit declaration
    of energy/commodity flows between components and buses.

    Attributes:
        bus: Name of the bus this flow connects to
        direction: Flow direction ("input" or "output")
        variable: Pyomo variable representing the flow (set during attach)
        nominal_value: Maximum flow value (capacity)
        min_value: Minimum flow value when active
        max_value: Alternative to nominal_value
        investment: Whether this flow is investable
        variable_costs: Variable costs per unit flow (e.g., EUR/MWh)
        flow_type: Type of flow (power, heat, fuel, etc.)
    """
    bus: str
    direction: Literal["input", "output"]
    variable: Optional[Any] = None  # pyo.Var - set during attach
    nominal_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    investment: bool = False
    variable_costs: Optional[float] = None
    flow_type: Optional[str] = None


@dataclass
class InvestmentResult:
    """
    Investment results from optimization.

    Contains the variables related to investment decisions.
    """
    capacity: Optional[Any] = None  # pyo.Var
    build: Optional[Any] = None  # pyo.Var (binary)
    capacity_energy: Optional[Any] = None  # For storage
    capacity_power: Optional[Any] = None  # For storage


@runtime_checkable
class Component(Protocol):
    """
    Protocol for all components in the EnerGIS framework.

    This defines the interface that all components must implement.
    Using typing.Protocol provides runtime type checking while maintaining
    duck typing compatibility.

    All component implementations should provide these methods.
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
        Attach component to the Pyomo model.

        This method creates all necessary Pyomo variables, parameters, and
        constraints for the component and registers flows with buses.

        Args:
            model: Pyomo ConcreteModel to attach to
            time_set: Pyomo Set representing time indices
            config: Configuration dictionary
            buses: Dictionary of bus objects

        Returns:
            Dictionary with standardized keys:
            - 'flows': Dict[str, Dict[str, pyo.Var]] - Flow variables by bus and direction
            - 'investment': Optional[InvestmentResult] - Investment variables
            - 'state': Optional[pyo.Var] - State variables (e.g., SOC for storage)
            - 'metadata': Optional[Dict] - Additional component-specific data
        """
        ...

    def get_results(
        self,
        model: Any,  # pyo.ConcreteModel
        time_set: Any
    ) -> Dict[str, Any]:
        """
        Extract results from solved model.

        Args:
            model: Solved Pyomo model
            time_set: Time set used in model

        Returns:
            Dictionary with component results (flows, states, etc.)
        """
        ...

    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate component configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If configuration is invalid
        """
        ...


class BaseComponent(ABC):
    """
    Base class for all components with common functionality.

    Provides default implementations and helper methods that are shared
    across all component types. Subclasses should inherit from this class
    and implement the abstract methods.

    Attributes:
        name: Unique identifier for the component instance
        label: Human-readable label (defaults to name)
        flows: List of Flow objects declared by this component
        _attached: Whether component has been attached to a model
    """

    def __init__(self, name: str, label: str = None):
        """
        Initialize base component.

        Args:
            name: Unique component identifier
            label: Human-readable label (optional)
        """
        self.name = name
        self.label = label or name
        self.flows: List[Flow] = []
        self._attached = False
        self._model = None
        self._time_set = None

    @abstractmethod
    def attach(
        self,
        model: Any,
        time_set: Any,
        config: Dict[str, Any],
        buses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Attach component to model - must be implemented by subclasses.

        Args:
            model: Pyomo ConcreteModel
            time_set: Pyomo Set for time indices
            config: Configuration dictionary
            buses: Dictionary of bus objects

        Returns:
            Dictionary with standardized return values
        """
        pass

    def add_flow(self, flow: Flow) -> None:
        """
        Register a flow for this component.

        Args:
            flow: Flow object to register
        """
        self.flows.append(flow)

    def get_flows_for_bus(self, bus_name: str) -> List[Flow]:
        """
        Get all flows connected to a specific bus.

        Args:
            bus_name: Name of the bus

        Returns:
            List of Flow objects for that bus
        """
        return [f for f in self.flows if f.bus == bus_name]

    def get_input_flows(self) -> List[Flow]:
        """Get all input flows."""
        return [f for f in self.flows if f.direction == "input"]

    def get_output_flows(self) -> List[Flow]:
        """Get all output flows."""
        return [f for f in self.flows if f.direction == "output"]

    def get_results(
        self,
        model: Any,
        time_set: Any
    ) -> Dict[str, Any]:
        """
        Default implementation for result extraction.

        Extracts flow values from the model. Can be overridden by subclasses
        for component-specific results.

        Args:
            model: Solved Pyomo model
            time_set: Time set

        Returns:
            Dictionary with flow results
        """
        results = {
            'name': self.name,
            'label': self.label,
            'flows': {}
        }

        for flow in self.flows:
            if flow.variable is not None:
                flow_key = f"{flow.bus}_{flow.direction}"
                results['flows'][flow_key] = {
                    t: pyo.value(flow.variable[t]) for t in time_set
                }

        return results

    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        Default configuration validation.

        Subclasses can override for specific validation needs.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    def _validate_positive(self, value: float, name: str, allow_zero: bool = False) -> None:
        """
        Helper to validate positive values.

        Args:
            value: Value to check
            name: Parameter name for error message
            allow_zero: Whether zero is acceptable

        Raises:
            ValueError: If value is not positive (or non-negative if allow_zero)
        """
        if allow_zero:
            if value < 0:
                raise ValueError(f"{name} must be non-negative, got {value}")
        else:
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")

    def _validate_range(
        self,
        value: float,
        name: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None
    ) -> None:
        """
        Helper to validate value is in range.

        Args:
            value: Value to check
            name: Parameter name for error message
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)

        Raises:
            ValueError: If value is out of range
        """
        if min_val is not None and value < min_val:
            raise ValueError(f"{name} must be >= {min_val}, got {value}")
        if max_val is not None and value > max_val:
            raise ValueError(f"{name} must be <= {max_val}, got {value}")

    def __repr__(self) -> str:
        """String representation of component."""
        return f"{self.__class__.__name__}(name='{self.name}', label='{self.label}')"
