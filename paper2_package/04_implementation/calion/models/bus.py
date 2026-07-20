"""
Bus abstraction for CALION framework.

This module provides bus classes for modeling energy/commodity flows.
Buses are central connection points where component flows are balanced.

Inspired by Oemof.solph and PyPSA bus concepts.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Union

try:
    import pyomo.environ as pyo
except Exception:  # pragma: no cover - optional dependency
    pyo = None

from .component import BaseComponent, BusType


class Bus(BaseComponent):
    """
    Bus class for energy/commodity flows.

    A bus is a connection point where multiple component flows meet and must
    be balanced. In energy system modeling, buses represent:
    - Electricity grids
    - Heat networks
    - Gas pipelines
    - Other commodity networks

    The bus enforces energy/commodity balance:
        sum(inputs) * (1 - loss_factor) == sum(outputs)

    Attributes:
        name: Unique bus identifier
        bus_type: Type of commodity/energy (electricity, heat, etc.)
        capacity: Optional capacity limit for flows through the bus
        loss_factor: Fraction of energy lost (0.0 = no losses, 0.1 = 10% loss)
        price: Optional time series of prices for this commodity
        co2_factor: Optional CO2 emission factor
        _inputs: List of input flow variables
        _outputs: List of output flow variables
    """

    def __init__(
        self,
        name: str,
        bus_type: Union[BusType, str],
        *,
        capacity: float | None = None,
        loss_factor: float = 0.0,
        price: Union[Sequence[float], dict[int, float]] | None = None,
        co2_factor: Union[Sequence[float], dict[int, float]] | None = None,
        label: str | None = None
    ):
        """
        Initialize bus.

        Args:
            name: Unique bus identifier
            bus_type: Type of bus (from BusType enum or string)
            capacity: Maximum flow through bus (optional)
            loss_factor: Fraction of energy lost (0.0 to 1.0)
            price: Time series of commodity prices (optional)
            co2_factor: CO2 emission factor (optional)
            label: Human-readable label
        """
        super().__init__(name, label)

        # Convert string to BusType if needed
        if isinstance(bus_type, str):
            try:
                self.bus_type = BusType(bus_type)
            except ValueError:
                # Allow custom bus types
                self.bus_type = bus_type
        else:
            self.bus_type = bus_type

        self.capacity = capacity
        self.loss_factor = float(loss_factor)
        self.price = price
        self.co2_factor = co2_factor

        # Validate parameters
        self._validate_range(self.loss_factor, "loss_factor", 0.0, 1.0)
        if capacity is not None:
            self._validate_positive(capacity, "capacity", allow_zero=False)

        # Track connected flows
        self._inputs: list[Any] = []  # pyo.Var
        self._outputs: list[Any] = []  # pyo.Var
        self._balance_constraint = None

    def add_input(self, flow: Any) -> None:
        """
        Register an input flow to this bus.

        Args:
            flow: Pyomo variable representing input flow
        """
        if flow not in self._inputs:
            self._inputs.append(flow)

    def add_output(self, flow: Any) -> None:
        """
        Register an output flow from this bus.

        Args:
            flow: Pyomo variable representing output flow
        """
        if flow not in self._outputs:
            self._outputs.append(flow)

    def attach(
        self,
        model: Any,
        time_set: Any,
        config: dict[str, Any],
        buses: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Attach bus to model by creating balance constraint.

        Creates the fundamental balance constraint:
            sum(inputs) * (1 - loss) == sum(outputs)

        And optionally capacity constraints.

        Args:
            model: Pyomo ConcreteModel
            time_set: Pyomo Set for time indices
            config: Configuration dictionary
            buses: Dictionary of all buses (not used for bus itself)

        Returns:
            Dictionary with constraint references
        """
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach buses")

        self._model = model
        self._time_set = time_set

        # Create balance constraint
        def balance_rule(m, t):
            inputs_sum = sum(f[t] for f in self._inputs) if self._inputs else 0
            outputs_sum = sum(f[t] for f in self._outputs) if self._outputs else 0

            # Apply loss factor to inputs
            effective_inputs = inputs_sum * (1 - self.loss_factor)

            return effective_inputs == outputs_sum

        constraint_name = f"{self.name}_balance"
        self._balance_constraint = pyo.Constraint(time_set, rule=balance_rule)
        setattr(model, constraint_name, self._balance_constraint)

        # Optional: Capacity constraint
        if self.capacity is not None:
            def capacity_rule(m, t):
                total_flow = sum(f[t] for f in self._outputs) if self._outputs else 0
                return total_flow <= self.capacity

            capacity_constraint_name = f"{self.name}_capacity"
            capacity_constraint = pyo.Constraint(time_set, rule=capacity_rule)
            setattr(model, capacity_constraint_name, capacity_constraint)

        self._attached = True

        return {
            'balance_constraint': self._balance_constraint,
            'inputs_count': len(self._inputs),
            'outputs_count': len(self._outputs)
        }

    def get_results(
        self,
        model: Any,
        time_set: Any
    ) -> dict[str, Any]:
        """
        Extract bus flow results from solved model.

        Returns aggregated input and output flows.

        Args:
            model: Solved Pyomo model
            time_set: Time set

        Returns:
            Dictionary with bus results
        """
        results = {
            'name': self.name,
            'bus_type': str(self.bus_type),
            'total_inputs': {},
            'total_outputs': {},
            'net_flow': {}
        }

        for t in time_set:
            total_in = sum(pyo.value(f[t]) for f in self._inputs) if self._inputs else 0.0
            total_out = sum(pyo.value(f[t]) for f in self._outputs) if self._outputs else 0.0

            results['total_inputs'][t] = total_in
            results['total_outputs'][t] = total_out
            results['net_flow'][t] = total_in - total_out

        return results

    def validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate bus configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        # Currently no additional validation needed
        pass

    def get_input_count(self) -> int:
        """Get number of connected input flows."""
        return len(self._inputs)

    def get_output_count(self) -> int:
        """Get number of connected output flows."""
        return len(self._outputs)

    def is_balanced(self) -> bool:
        """Check if bus has at least one input and one output."""
        return len(self._inputs) > 0 and len(self._outputs) > 0

    def __repr__(self) -> str:
        """String representation of bus."""
        return (
            f"Bus(name='{self.name}', type={self.bus_type}, "
            f"inputs={len(self._inputs)}, outputs={len(self._outputs)})"
        )


def create_default_buses() -> dict[str, Bus]:
    """
    Create default buses for a standard energy system.

    Creates commonly used buses:
    - electricity: For electrical power
    - heat: For thermal energy
    - fuel_gas: For natural gas
    - fuel_biomass: For biomass
    - fuel_waste: For waste

    Returns:
        Dictionary mapping bus names to Bus objects
    """
    buses = {
        'electricity': Bus('electricity', BusType.ELECTRICITY),
        'heat': Bus('heat', BusType.HEAT),
        'fuel_gas': Bus('fuel_gas', BusType.FUEL_GAS),
        'fuel_biomass': Bus('fuel_biomass', BusType.FUEL_BIOMASS),
        'fuel_waste': Bus('fuel_waste', BusType.FUEL_WASTE),
    }
    return buses


def create_buses_from_config(config: dict[str, Any]) -> dict[str, Bus]:
    """
    Create buses from configuration dictionary.

    Expected config format:
    {
        "buses": {
            "bus_name": {
                "type": "electricity",
                "capacity": 100.0,  # optional
                "loss_factor": 0.05  # optional
            }
        }
    }

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary mapping bus names to Bus objects
    """
    buses = create_default_buses()

    # Add/override with custom buses from config
    buses_config = config.get('buses', {})
    for bus_name, bus_cfg in buses_config.items():
        bus_type_str = bus_cfg.get('type', 'generic')

        # Try to convert to BusType, fall back to string
        try:
            bus_type = BusType(bus_type_str)
        except ValueError:
            bus_type = bus_type_str

        buses[bus_name] = Bus(
            bus_name,
            bus_type,
            capacity=bus_cfg.get('capacity'),
            loss_factor=bus_cfg.get('loss_factor', 0.0),
            label=bus_cfg.get('label')
        )

    return buses
