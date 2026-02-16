# EnerGIS Config v2.0 - Usage Guide

## Overview

EnerGIS v2.0 introduces a completely redesigned configuration system with:

✅ **Type-Safe Schemas** - Dataclass-based configuration with IDE autocomplete
✅ **Unified Asset Model** - No more brownfield/greenfield distinction
✅ **Multi-Node Networks** - Full thermal network topology with physics
✅ **Technology Library** - Reusable technology templates
✅ **3-Layer Architecture** - tech_library → assets → scenarios
✅ **Built-in Validation** - Automatic consistency checking
✅ **Backward Compatible** - Works with existing system_builder.py

---

## Quick Start

### 1. Basic Usage

```python
from energis.config.config_manager import ConfigManager

# Load and validate configuration
manager = ConfigManager("configs_new/scenarios/stadtbach_baseline_2023.yaml")
config = manager.load()

# Access type-safe schema objects
scenario = manager.scenario
components = manager.components
grid = manager.grid
network = manager.network

# Print summary
manager.print_summary()
```

### 2. Use with Existing Code

```python
from energis.config.loader_v2 import load_config_v2
from energis.models.system_builder import build_model

# Load new config format
config = load_config_v2("configs_new/scenarios/stadtbach_baseline_2023.yaml")

# Use with existing system_builder (backward compatible!)
model = build_model(config, table)
```

### 3. Type-Safe Access

```python
from energis.config.schemas import HeatPumpAsset

# Filter components by type
heat_pumps = {
    comp_id: comp for comp_id, comp in manager.components.items()
    if isinstance(comp, HeatPumpAsset)
}

# Access typed fields with autocomplete
for hp_id, hp in heat_pumps.items():
    print(f"{hp_id}: {hp.existing.thermal_capacity_mw} MW")
    if hp.expansion.enabled:
        print(f"  Can expand by {hp.expansion.max_additional_capacity_mw} MW")
        print(f"  CAPEX: {hp.expansion.capex_eur_per_mw:,.0f} EUR/MW")
```

---

## Configuration Structure

### Directory Layout

```
configs_new/
├── tech_library/           # Reusable technology templates
│   ├── heat_pumps.yaml
│   ├── storage.yaml
│   ├── generators.yaml
│   ├── p2h.yaml
│   ├── pipes.yaml
│   ├── fluids.yaml
│   └── fuels.yaml
│
├── assets/                 # Site-specific asset definitions
│   └── stadtbach/
│       ├── components.yaml        # Components (existing + expansion)
│       ├── grid.yaml              # Grid connection & pricing
│       ├── network_topology.yaml  # Multi-node network
│       └── data_sources.yaml      # Time series mappings
│
└── scenarios/              # Optimization scenarios
    ├── stadtbach_baseline_2023.yaml
    └── stadtbach_capacity_expansion.yaml
```

### Configuration Layers

**Layer 1: Technology Library** (tech_library/)
- Defines reusable technology templates
- COP models, efficiency curves, cost data
- Referenced by assets via `technology: high_temp_heat_pump`

**Layer 2: Assets** (assets/)
- Site-specific component configurations
- Each component has `existing` + `expansion`
- Network topology with nodes, pipes, pumps
- Grid connection and pricing

**Layer 3: Scenarios** (scenarios/)
- Optimization settings (mode, constraints, costs)
- Time horizon and representative periods
- Economics (fuel prices, CO2 price, subsidies)
- Solver configuration
- References Layer 2 assets

---

## Unified Asset Model

**No more brownfield/greenfield distinction!**

Every component has:
- `existing`: What's already installed
- `expansion`: What can be added (investment)

```yaml
heat_pumps:
  HP1:
    technology: high_temp_heat_pump    # References tech_library

    existing:
      thermal_capacity_mw: 25.0        # Already installed
      commissioning_year: 2018
      remaining_lifetime_yr: 10

    expansion:
      enabled: true
      min_additional_capacity_mw: 5.0  # Can add 5-75 MW
      max_additional_capacity_mw: 75.0
      capex_eur_per_mw: 400000
      lifetime_yr: 15
```

**Interpretation:**
- `existing > 0` → Brownfield (has existing capacity)
- `existing = 0` → Greenfield (new installation)
- `expansion.enabled = true` → Can be expanded via investment

---

## Multi-Node Network Topology

Define realistic district heating networks with:
- Multiple nodes (producer, consumer, junction)
- Pipes with length, diameter, insulation
- Circulation pumps
- Physics modeling (pressure, temperature, time delays)

```yaml
networks:
  DH_primary:
    temperatures:
      supply_bounds_c: [90, 130]
      return_bounds_c: [40, 70]

    nodes:
      central_plant:
        type: producer
        components: [HKW, GTOST, HP1, HP2, TES1]
        pressure:
          setpoint_bar: 10.0

      stadtbach_west:
        type: consumer
        demand:
          demand_column: "demand_west_MW"
          peak_demand_mw: 80.0

    pipes:
      pipe_plant_to_west:
        from_node: central_plant
        to_node: stadtbach_west
        length_m: 1200
        diameter_mm: 400
        insulation: standard_insulated
```

**Physics Models:**
- ✅ Mass balance at each node: Σṁ_in = Σṁ_out
- ✅ Enthalpy balance: Σ(ṁ·h)_in = Σ(ṁ·h)_out
- ✅ Pressure drop (Darcy-Weisbach): ΔP = f·(L/D)·(ρ·v²/2)
- ✅ Temperature loss: Q_loss = U·π·D·L·ΔT
- ✅ Transport delay: τ = L/v

---

## Technology Library

Define technologies once, reference everywhere:

```yaml
# tech_library/heat_pumps.yaml
heat_pumps:
  high_temp_heat_pump:
    cop_model:
      type: lookup_table_2d
      lookup_table:
        source_temps_K: [273, 283, 293, 303, 313, 323, 333, 343]
        sink_temps_K: [343, 353, 363, 373, 383]
        cop_values:
          - [2.45, 2.86, 3.43, 4.29, 5.72, 8.58, 17.15, null]
          - [2.21, 2.58, 3.06, 3.78, 4.91, 7.07, 12.37, 71.14]
          # ... more rows

    operational:
      min_load_fraction: 0.30

    costs:
      capex_eur_per_mw_th: 400000
      opex_fixed_eur_per_mw_yr: 8000
      lifetime_yr: 15
```

**Benefits:**
- ✅ No repetition (HP1, HP2, HP3, HP4 all reference same tech)
- ✅ Consistent parameters across components
- ✅ Easy to update (change one place, affects all)
- ✅ Technology database can be version controlled

---

## Validation

Built-in validation checks for:

```python
from energis.config.validation import validate_config

# Validate loaded config
validation_result = validate_config(config)

if not validation_result.valid:
    validation_result.print_summary()
    # Shows:
    # - Missing technology references
    # - Invalid capacity ranges
    # - Disconnected network nodes
    # - Missing time series columns
    # - Inconsistent optimization settings
```

**Validation Categories:**
- **Components:** Technology references, capacity constraints, expansion logic
- **Network:** Node connectivity, pipe references, pump configuration
- **Scenario:** Optimization mode vs decision variables, cost components
- **Economics:** Fuel prices, CO2 price, discount rate ranges
- **Tech Library:** Referenced technologies exist

---

## Schema Objects

All configuration is loaded into type-safe dataclass objects:

### Asset Schemas

```python
from energis.config.schemas import (
    AssetCapacity,           # Existing capacity
    ExpansionPotential,      # Investment potential
    ComponentAsset,          # Base class
    HeatPumpAsset,           # Heat pump specific
    StorageAsset,            # Storage specific
    GeneratorAsset,          # Boiler/CHP
    P2HAsset,                # Power-to-Heat
    GridConnection,          # Grid connection
)

# Example usage
hp = manager.get_component("HP1")  # Returns HeatPumpAsset
print(hp.existing.thermal_capacity_mw)
print(hp.expansion.capex_eur_per_mw)
print(hp.waste_heat_source['temperature_column'])
```

### Network Schemas

```python
from energis.config.schemas import (
    NetworkNode,             # Node (producer/consumer/junction)
    Pipe,                    # Pipe connection
    Pump,                    # Circulation pump
    ThermalNetwork,          # Complete network
    NetworkTopology,         # All networks
)

# Example usage
network = manager.get_network("DH_primary")
for node_id, node in network.nodes.items():
    print(f"{node_id}: {node.type}")
```

### Tech Library Schemas

```python
from energis.config.schemas import (
    HeatPumpTechnology,      # HP technology with COP model
    StorageTechnology,       # Storage technology
    GeneratorTechnology,     # Generator technology
    P2HTechnology,           # P2H technology
    PipeTechnology,          # Pipe technology
    FuelProperties,          # Fuel properties
)

# Example usage
hp_tech = tech_library['heat_pumps']['high_temp_heat_pump']
print(hp_tech.cop_model.source_temps_K)
print(hp_tech.costs.capex_eur_per_mw_th)
```

### Scenario Schemas

```python
from energis.config.schemas import (
    TimeConfig,              # Time horizon
    OptimizationConfig,      # Optimization settings
    EconomicsConfig,         # Economics
    SolverConfig,            # Solver parameters
    Scenario,                # Complete scenario
)

# Example usage
scenario = manager.scenario
print(scenario.optimization.mode)
print(scenario.economics.co2_price_eur_per_tonne)
print(scenario.solver.name)
```

---

## Backward Compatibility

The new config loader creates a backward-compatible dict that works with existing `system_builder.py`:

```python
config = load_config_v2("configs_new/scenarios/stadtbach_baseline_2023.yaml")

# Old-style access (still works!)
config['system']['heat_pumps']  # List[Dict]
config['grid']['max_import_mw']  # float
config['costs']['co2_price_eur_per_tonne']  # float

# New-style access (type-safe!)
config['_schemas']['scenario']    # Scenario object
config['_schemas']['components']  # Dict[str, ComponentAsset]
config['_schemas']['grid']        # GridConnection object
config['_schemas']['network']     # NetworkTopology object
config['_tech_library']           # Technology library
```

---

## Migration from Old Config

### Old Format (v1.0)

```yaml
system:
  heat_pumps:
    - id: HP1
      max_th_mw: 50.0              # ❌ Mixed brownfield/greenfield
      investment:
        enabled: true
```

### New Format (v2.0)

```yaml
heat_pumps:
  HP1:
    technology: high_temp_heat_pump
    existing:
      thermal_capacity_mw: 25.0    # ✅ Clear: 25 MW existing
    expansion:
      enabled: true
      max_additional_capacity_mw: 25.0  # ✅ Can add 25 MW more
```

**Key Differences:**
- Components are dict (not list) - indexed by ID
- `existing` + `expansion` instead of single capacity
- Technology references instead of inline parameters
- Multi-node network instead of single bus

---

## Best Practices

### 1. Use Technology Library

❌ **Bad:** Duplicate parameters for each component

```yaml
heat_pumps:
  HP1:
    min_load: 0.30
    cop_model: {...}  # 50 lines
    capex: 400000
  HP2:
    min_load: 0.30
    cop_model: {...}  # Same 50 lines repeated!
    capex: 400000
```

✅ **Good:** Reference technology

```yaml
heat_pumps:
  HP1:
    technology: high_temp_heat_pump  # Defined once in tech_library
  HP2:
    technology: high_temp_heat_pump  # Reuse!
```

### 2. Type-Safe Access

❌ **Bad:** Use raw dict (no type safety)

```python
hp_capacity = config['system']['heat_pumps'][0]['max_th_mw']  # KeyError risk!
```

✅ **Good:** Use schema objects

```python
hp = manager.get_component("HP1")  # Type: HeatPumpAsset
hp_capacity = hp.existing.thermal_capacity_mw  # Type-safe, autocomplete!
```

### 3. Always Validate

❌ **Bad:** Load without validation

```python
config = load_config_v2(scenario_path)  # May have errors!
```

✅ **Good:** Use ConfigManager with validation

```python
manager = ConfigManager(scenario_path, validate=True)
config = manager.load()  # Raises error if invalid
```

### 4. Use Unified Asset Model

❌ **Bad:** Separate brownfield/greenfield

```yaml
brownfield_heat_pumps: [...]
greenfield_heat_pumps: [...]
```

✅ **Good:** Unified existing + expansion

```yaml
heat_pumps:
  HP_existing:
    existing:
      thermal_capacity_mw: 25.0
    expansion:
      enabled: false

  HP_new:
    existing:
      thermal_capacity_mw: 0.0   # Greenfield
    expansion:
      enabled: true
      max_additional_capacity_mw: 50.0
```

---

## Complete Example

See `examples/use_new_config_structure.py` for a complete working example.

---

## API Reference

### ConfigManager

```python
class ConfigManager:
    def __init__(self, scenario_path: str, validate: bool = True)
    def load(self) -> Dict[str, Any]

    @property
    def scenario -> Scenario
    @property
    def components -> Dict[str, ComponentAsset]
    @property
    def grid -> GridConnection
    @property
    def network -> NetworkTopology
    @property
    def tech_library -> Dict[str, Any]

    def get_component(self, component_id: str) -> ComponentAsset
    def get_network(self, network_id: str) -> ThermalNetwork
    def print_summary(self)
```

### Convenience Functions

```python
def load_config_v2(scenario_path: str) -> Dict[str, Any]
    """Load config without validation."""

def load_and_validate_config(scenario_path: str, validate: bool = True) -> Dict[str, Any]
    """Load and validate config."""

def validate_config(config: Dict[str, Any]) -> ValidationResult
    """Validate loaded config."""
```

---

## Troubleshooting

### Error: Technology not found in tech_library

**Problem:** Component references a technology that doesn't exist.

```yaml
heat_pumps:
  HP1:
    technology: nonexistent_tech  # ❌ Not in tech_library/heat_pumps.yaml
```

**Solution:** Use a technology that exists in `tech_library/heat_pumps.yaml`:

```yaml
heat_pumps:
  HP1:
    technology: high_temp_heat_pump  # ✅ Exists
```

### Error: Network node not found

**Problem:** Pipe references a node that doesn't exist.

```yaml
pipes:
  pipe1:
    from_node: central_plant
    to_node: nonexistent_node  # ❌ Not in nodes
```

**Solution:** Ensure all referenced nodes exist:

```yaml
nodes:
  central_plant: {...}
  consumer_west: {...}

pipes:
  pipe1:
    from_node: central_plant
    to_node: consumer_west  # ✅ Exists
```

### Warning: Mode is 'capacity_expansion' but no components have expansion enabled

**Problem:** Scenario mode is investment but no components can be invested in.

**Solution:** Enable expansion for at least one component:

```yaml
heat_pumps:
  HP1:
    expansion:
      enabled: true  # ✅
      max_additional_capacity_mw: 50.0
```

---

## Support

For questions or issues:
- See examples in `examples/use_new_config_structure.py`
- Check config validation output
- Review `docs/CONFIG_REFACTORING_PROPOSAL.md` for design rationale
- Review `configs_new/README.md` for config structure overview

---

**Version:** 2.0.0
**Date:** 2026-02-16
**Status:** ✅ Complete
