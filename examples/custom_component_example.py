"""
Example: Adding a Custom Component to EnerGIS Framework

This example demonstrates how to add a new component type using the v2.0
architecture with BaseComponent and ComponentRegistry.

We'll create a "SolarThermalCollector" component that generates heat based
on solar irradiation data.

Key improvements over v1.0:
- Only need to create 1 file (this one!)
- Automatic registration via decorator
- Explicit flow declarations
- Type-safe component development
- No changes needed to system_builder
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

try:
    import pyomo.environ as pyo
except Exception:
    pyo = None

# Import the new framework abstractions
from energis.models import (
    BaseComponent,
    Flow,
    register_component,
    ComponentRegistry
)


@register_component(
    "solar_thermal",
    category="source",
    description="Solar thermal collector with irradiation-based heat generation",
    version="1.0.0",
    author="Example Developer"
)
class SolarThermalCollector(BaseComponent):
    """
    Solar thermal collector component.

    Generates heat based on solar irradiation and collector efficiency.
    Q_out[t] = area * irradiation[t] * efficiency

    Attributes:
        name: Component identifier
        area: Collector area in m²
        efficiency: Thermal efficiency (0-1)
        max_temp: Maximum output temperature
        irradiation_column: Name of column in time series data with irradiation
    """

    def __init__(
        self,
        name: str,
        area: float,
        efficiency: float = 0.7,
        max_temp: float = 90.0,
        irradiation_column: str = "solar_irradiation_W_m2",
        label: str = None
    ):
        """
        Initialize solar thermal collector.

        Args:
            name: Unique component identifier
            area: Collector area in m²
            efficiency: Thermal efficiency (0-1), default 0.7
            max_temp: Maximum output temperature in °C
            irradiation_column: Column name for irradiation data
            label: Human-readable label
        """
        super().__init__(name, label)

        # Validate parameters using helper methods from BaseComponent
        self._validate_positive(area, "area", allow_zero=False)
        self._validate_range(efficiency, "efficiency", 0.0, 1.0)
        self._validate_range(max_temp, "max_temp", 0.0, 200.0)

        self.area = float(area)
        self.efficiency = float(efficiency)
        self.max_temp = float(max_temp)
        self.irradiation_column = irradiation_column

    def attach(
        self,
        model: Any,
        time_set: Any,
        config: Dict[str, Any],
        buses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Attach solar thermal collector to Pyomo model.

        Creates:
        - Q_th_out[t]: Heat output variable
        - irradiation[t]: Parameter with irradiation data
        - Constraint linking output to irradiation

        Args:
            model: Pyomo ConcreteModel
            time_set: Pyomo Set for time indices
            config: Configuration dictionary (contains time series data)
            buses: Dictionary of Bus objects

        Returns:
            Standardized result dictionary with flows and metadata
        """
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach solar thermal collector")

        # Get irradiation time series from config
        inputs_cfg = config.get("inputs", {})
        table = inputs_cfg.get("table")

        if table is None:
            raise ValueError("Time series table not found in config['inputs']['table']")

        if self.irradiation_column not in table.columns:
            raise ValueError(
                f"Irradiation column '{self.irradiation_column}' not found in time series data. "
                f"Available columns: {table.columns}"
            )

        # Get irradiation data
        irradiation_data = {
            t: float(table[self.irradiation_column][t - 1])
            for t in time_set
        }

        # Create Pyomo components
        comp = self.name

        # Variable: Heat output
        Q_out = pyo.Var(time_set, domain=pyo.NonNegativeReals)
        setattr(model, f"{comp}_Q_out", Q_out)

        # Parameters
        irrad_param = pyo.Param(time_set, initialize=irradiation_data, mutable=False)
        setattr(model, f"{comp}_irradiation", irrad_param)

        setattr(model, f"{comp}_area", pyo.Param(initialize=self.area))
        setattr(model, f"{comp}_efficiency", pyo.Param(initialize=self.efficiency))

        # Constraint: Q_out = area * irradiation * efficiency
        # Convert W/m² to MW: divide by 1e6
        def output_rule(mm, t):
            return Q_out[t] == (
                mm.__getattribute__(f"{comp}_area") *
                irrad_param[t] *
                mm.__getattribute__(f"{comp}_efficiency") /
                1e6  # W/m² to MW
            )

        setattr(model, f"{comp}_output", pyo.Constraint(time_set, rule=output_rule))

        # Register flow with framework
        self.add_flow(Flow(
            bus="heat",
            direction="output",
            variable=Q_out,
            flow_type="solar_thermal"
        ))

        # Register with heat bus
        if buses and "heat" in buses:
            buses["heat"].add_output(Q_out)

        # Return standardized format
        return {
            "flows": {
                "heat": {"output": Q_out}
            },
            "metadata": {
                "area_m2": self.area,
                "efficiency": self.efficiency,
                "max_temp_C": self.max_temp,
                "irradiation_column": self.irradiation_column
            },
            # Legacy compatibility (if needed)
            "Q_th_out": Q_out
        }

    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate configuration for solar thermal collector.

        Checks that required time series data is available.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        inputs_cfg = config.get("inputs", {})
        table = inputs_cfg.get("table")

        if table is None:
            raise ValueError("Time series table required in config['inputs']['table']")

        if self.irradiation_column not in table.columns:
            raise ValueError(
                f"Required column '{self.irradiation_column}' not found in time series data"
            )

    def get_results(self, model: Any, time_set: Any) -> Dict[str, Any]:
        """
        Extract results for solar thermal collector.

        Args:
            model: Solved Pyomo model
            time_set: Time set

        Returns:
            Dictionary with results including heat output and capacity factor
        """
        # Use BaseComponent's default result extraction
        results = super().get_results(model, time_set)

        # Add component-specific metrics
        Q_out_var = getattr(model, f"{self.name}_Q_out")
        q_values = [pyo.value(Q_out_var[t]) for t in time_set]

        results["total_heat_MWh"] = sum(q_values)
        results["avg_output_MW"] = sum(q_values) / len(q_values) if q_values else 0
        results["peak_output_MW"] = max(q_values) if q_values else 0

        # Calculate capacity factor
        max_possible = self.area * self.efficiency / 1e6  # Assuming max irradiation = 1000 W/m²
        capacity_factor = (
            results["avg_output_MW"] / (max_possible * 1000) if max_possible > 0 else 0
        )
        results["capacity_factor"] = capacity_factor

        return results


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def example_usage():
    """
    Demonstrate how to use the custom SolarThermalCollector component.
    """
    print("=== Custom Component Example ===\n")

    # 1. Component is automatically registered via decorator
    print("1. Registered components:")
    print(f"   {ComponentRegistry.list_components()}\n")

    # 2. Get component metadata
    print("2. Solar thermal component info:")
    metadata = ComponentRegistry.get_metadata("solar_thermal")
    print(f"   Description: {metadata['description']}")
    print(f"   Category: {metadata['category']}")
    print(f"   Version: {metadata['version']}\n")

    # 3. Create component instance
    print("3. Creating solar thermal collector...")
    solar = ComponentRegistry.create(
        "solar_thermal",
        name="SolarCol1",
        area=500.0,  # 500 m²
        efficiency=0.75,
        irradiation_column="solar_W_m2"
    )
    print(f"   Created: {solar}")
    print(f"   Flows: {len(solar.flows)} registered\n")

    # 4. Alternative: Direct instantiation
    print("4. Alternative direct creation:")
    solar2 = SolarThermalCollector(
        name="SolarCol2",
        area=300.0,
        efficiency=0.7,
        label="Rooftop Solar Collector"
    )
    print(f"   Created: {solar2}\n")

    print("=== Integration with EnerGIS ===\n")
    print("To use in a system config (configs/systems/*.yaml):\n")
    print("""
system:
  solar_thermal:
    - id: SolarCol1
      component_type: solar_thermal  # Uses registry!
      area: 500.0
      efficiency: 0.75
      irradiation_column: solar_W_m2
      enabled: true
    """)

    print("\nNo changes to system_builder.py needed!")
    print("Component is automatically discovered and integrated.\n")


if __name__ == "__main__":
    # Run example
    example_usage()

    print("\n" + "=" * 70)
    print("COMPARISON: Old vs. New Architecture")
    print("=" * 70)

    print("\nOLD APPROACH (v1.0):")
    print("  1. Create energis/models/blocks/solar_thermal.py (100+ lines)")
    print("  2. Modify energis/models/system_builder.py (+50 lines)")
    print("  3. Add to configs/tech_catalog.yaml")
    print("  4. Update configs/systems/*.yaml")
    print("  Total: 4 files changed, ~150+ lines of code\n")

    print("NEW APPROACH (v2.0):")
    print("  1. Create THIS file with @register_component decorator")
    print("  2. Update configs/systems/*.yaml (optional)")
    print("  Total: 1 file created, auto-registered!\n")

    print("Benefits:")
    print("  ✓ Plugin architecture - drop in new components")
    print("  ✓ Type-safe with BaseComponent")
    print("  ✓ Explicit flow declarations")
    print("  ✓ Automatic registration")
    print("  ✓ No framework modifications needed")
    print("=" * 70)
