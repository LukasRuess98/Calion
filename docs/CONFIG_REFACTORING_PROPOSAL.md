# Config Structure Refactoring Proposal

## 🎯 Executive Summary

**Current State:** Mixed brownfield/greenfield concepts, repetitive configs, no multi-node network support
**Target State:** Unified asset-based config, network-ready architecture, clear separation of concerns

---

## 🔴 Problems with Current Config Structure

### 1. Conceptual Issues

**Problem: Brownfield/Greenfield Duplication**
```yaml
# Current: Two separate concepts
thermal_network:
  brownfield_mode: true  # ❌ Binary flag, not flexible

heat_pumps:
  defaults:
    capacity_mw: 50.0
    build: true           # ❌ What does this mean?
  investment:
    enabled: true         # ❌ Overlaps with build
```

**Problem: Repetitive Component Definitions**
```yaml
# Current: Copy-paste for each heat pump
heat_pumps:
  - id: HP1
    wrg_source_column: "WRG1_T °C"
    technical_limits: {...}
    defaults: {...}
    investment: {...}
  - id: HP2
    wrg_source_column: "WRG2_T °C"
    technical_limits: {...}  # ❌ Identical to HP1
    defaults: {...}          # ❌ Identical to HP1
    investment: {...}        # ❌ Identical to HP1
```

**Problem: Overlapping Concepts**
```yaml
# Current: Three places for capacity info
technical_limits:
  capacity_min_mw: 5.0    # If built, minimum size
  capacity_max_mw: 100.0  # Maximum possible
defaults:
  capacity_mw: 50.0       # ❌ Used when? Fixed capacity?
  build: true             # ❌ Build new or use existing?
investment:
  enabled: true           # ❌ Overlaps with build flag
```

### 2. Structure Issues

**Problem: Unclear Layer Separation**
```
01_tech/heat_pumps.yaml    # Technology template
  ├─ investment:
  │   └─ capex_eur_per_mw: 400000    # Cost is here
  └─ bounds: {...}

03_systems/full.yaml       # System instance
  └─ heat_pumps:
      └─ investment:
          └─ capex_eur_per_mw: 400000  # ❌ Cost duplicated here
```

### 3. Thermal Network Issues

**Problem: No Multi-Node Support**
```yaml
# Current: Single-bus simplification
thermal_network:
  enabled: true
  brownfield_mode: true        # ❌ Doesn't support multi-node
  parameters:
    supply_temp_nominal_c: 120  # ❌ Single temperature level
    return_temp_nominal_c: 55
```

**Missing:**
- ❌ Network nodes (junctions, connection points)
- ❌ Pipe segments with pressure/temperature losses
- ❌ Time delays (transport lag)
- ❌ Multi-level networks (different temperature zones)
- ❌ Inter-network connections (heat pumps between networks)
- ❌ Node-level mass, enthalpy, pressure balances

---

## ✅ Proposed Config Structure (Best Practice)

### 🏗️ Architecture Principles

1. **Asset-Centric:** Every component is an "asset" with `existing` capacity + `expansion` potential
2. **Network-Ready:** First-class support for multi-node thermal networks
3. **Clear Layering:**
   - `tech_library/` - Technology templates (reusable)
   - `assets/` - Physical asset definitions (site-specific)
   - `scenarios/` - Optimization scenarios (what to optimize)
4. **Type-Safe:** Uses dataclasses from `config_schema.py`

---

### 📁 New Directory Structure

```
configs/
├── tech_library/           # Technology templates (reusable across sites)
│   ├── heat_pumps.yaml     # HP performance curves, efficiency models
│   ├── boilers.yaml        # Boiler efficiency models
│   ├── chp.yaml            # CHP efficiency models
│   ├── storage.yaml        # Storage loss models, thermal stratification
│   ├── pipes.yaml          # Pipe friction/heat loss models
│   └── pumps.yaml          # Pump efficiency curves
│
├── assets/                 # Site-specific asset definitions
│   └── stadtbach/
│       ├── components.yaml      # All components at this site
│       ├── network_topology.yaml  # Network nodes, pipes, connections
│       └── data_sources.yaml    # Time series mappings
│
└── scenarios/              # Optimization scenarios
    ├── baseline_2023.yaml       # Fixed capacities, dispatch only
    ├── capacity_expansion.yaml  # Optimize new investments
    └── network_design.yaml      # Optimize pipe routing + capacities
```

---

### 🔧 Component Config Schema (Unified Asset Model)

**Core Concept:** Every component has:
- `existing`: What's already installed (brownfield)
- `expansion`: What can be added (greenfield/expansion)

```yaml
# assets/stadtbach/components.yaml
# ============================================================================
# COMPONENTS - Stadtbach District Heating System
# ============================================================================

heat_pumps:
  HP1:
    # Technology reference (from tech_library)
    technology: high_temp_heat_pump

    # Data source (waste heat recovery)
    waste_heat_source:
      temperature_column: "WRG1_T_K"       # Source temperature [K]
      available_power_column: "WRG1_Q_MW"  # Available heat [MW]

    # Existing asset (installed capacity)
    existing:
      thermal_capacity_mw: 25.0   # Currently installed
      commissioning_year: 2018
      remaining_lifetime_yr: 10

    # Expansion potential (can be added)
    expansion:
      enabled: true
      min_additional_capacity_mw: 5.0    # Minimum expansion size
      max_additional_capacity_mw: 75.0   # Maximum total (existing + new)
      capex_eur_per_mw: 400000
      opex_eur_per_mw_yr: 8000
      lifetime_yr: 15

  HP2:
    technology: high_temp_heat_pump
    waste_heat_source:
      temperature_column: "WRG2_T_K"
      available_power_column: "WRG2_Q_MW"
    existing:
      thermal_capacity_mw: 0.0  # Not yet built
    expansion:
      enabled: true
      min_additional_capacity_mw: 10.0
      max_additional_capacity_mw: 100.0
      capex_eur_per_mw: 400000
      opex_eur_per_mw_yr: 8000
      lifetime_yr: 15


thermal_storage:
  TES1:
    technology: stratified_tank

    existing:
      energy_capacity_mwh: 500.0
      power_capacity_mw: 50.0
      commissioning_year: 2015

    expansion:
      enabled: true
      max_additional_energy_mwh: 1500.0
      max_additional_power_mw: 150.0
      energy_capex_eur_per_mwh: 5000
      power_capex_eur_per_mw: 50000
      coupling_ratio: 0.1  # Power = 0.1 * Energy (MW = 0.1 * MWh)
      lifetime_yr: 25


boilers:
  HWS:
    technology: gas_condensing_boiler
    existing:
      thermal_capacity_mw: 120.0
      commissioning_year: 2010
    expansion:
      enabled: false  # Keep existing, no expansion


chp_plants:
  HKW:
    technology: gas_chp_extraction
    existing:
      thermal_capacity_mw: 150.0
      electrical_capacity_mw: 35.0
      commissioning_year: 2005
    expansion:
      enabled: false
```

---

### 🌐 Network Topology Schema (Multi-Node)

**Core Concept:** Network is a graph of nodes connected by pipes

```yaml
# assets/stadtbach/network_topology.yaml
# ============================================================================
# THERMAL NETWORK TOPOLOGY - Multi-Node with Pressure/Temperature
# ============================================================================

networks:
  # High-temperature district heating network (primary)
  DH_primary:
    type: district_heating
    temperature_level: high

    # Supply/return temperature bounds
    supply_temp_bounds_c: [90, 130]
    return_temp_bounds_c: [40, 70]

    # Nodes (junction points, producers, consumers)
    nodes:
      # Production nodes
      central_plant:
        type: producer
        location:
          lat: 48.1234
          lon: 11.5678
        components:
          - HKW          # CHP plant
          - HWS          # Gas boiler
          - HP1          # Heat pump
          - TES1         # Storage (charge/discharge)

      # Consumer nodes
      stadtbach_west:
        type: consumer
        demand_column: "demand_west_MW"

      stadtbach_east:
        type: consumer
        demand_column: "demand_east_MW"

      # Junction nodes (pure distribution)
      junction_1:
        type: junction

    # Pipes connecting nodes
    pipes:
      pipe_plant_to_west:
        from_node: central_plant
        to_node: stadtbach_west
        length_m: 2500
        diameter_mm: 400
        insulation_type: standard
        burial_depth_m: 1.2

        existing:
          installed: true

        expansion:
          enabled: false  # Existing pipe, no replacement

      pipe_plant_to_junction:
        from_node: central_plant
        to_node: junction_1
        length_m: 1200
        diameter_mm: 300
        insulation_type: standard
        burial_depth_m: 1.2

        existing:
          installed: false  # Greenfield pipe

        expansion:
          enabled: true
          diameter_options_mm: [200, 300, 400, 500]
          capex_eur_per_m: 800

      pipe_junction_to_east:
        from_node: junction_1
        to_node: stadtbach_east
        length_m: 1800
        diameter_mm: 250
        insulation_type: standard
        burial_depth_m: 1.2

        existing:
          installed: true

    # Pumps (pressure management)
    pumps:
      main_circulation_pump:
        node: central_plant
        existing:
          rated_pressure_bar: 6.0
          rated_flow_m3_h: 500
        expansion:
          enabled: false

  # Low-temperature network (secondary, e.g., for waste heat recovery)
  DH_secondary:
    type: district_heating
    temperature_level: low

    supply_temp_bounds_c: [50, 80]
    return_temp_bounds_c: [30, 50]

    nodes:
      waste_heat_source:
        type: producer
        components:
          - HP2  # Heat pump extracting from waste heat

      industrial_zone:
        type: consumer
        demand_column: "demand_industrial_MW"

    pipes:
      pipe_wh_to_ind:
        from_node: waste_heat_source
        to_node: industrial_zone
        length_m: 800
        diameter_mm: 200
        existing:
          installed: true

# Inter-network connections (heat pumps between networks)
inter_network_connections:
  HP_primary_to_secondary:
    type: heat_pump
    component: HP3
    source_network: DH_secondary   # Takes heat from low-temp
    sink_network: DH_primary       # Delivers to high-temp
```

---

### 🎮 Scenario Configuration (What to Optimize)

```yaml
# scenarios/capacity_expansion_2024.yaml
# ============================================================================
# SCENARIO: Capacity Expansion 2024
# ============================================================================
# Optimize which assets to expand and by how much

scenario:
  name: "Stadtbach Capacity Expansion 2024"
  description: "Determine optimal investments for 2024-2030 horizon"

  # Time horizon
  time:
    data_source: "../data/stadtbach_2023_full.xlsx"
    date_column: "timestamp"
    start: "2023-01-01"
    end: "2023-12-31"
    resolution_h: 1.0

  # Reference assets
  assets: "../assets/stadtbach/components.yaml"
  network: "../assets/stadtbach/network_topology.yaml"

  # Optimization settings
  optimization:
    mode: capacity_expansion  # Options: dispatch, capacity_expansion, network_design

    # What can be optimized
    decision_variables:
      - component_capacities    # Size of heat pumps, boilers, storage
      - component_dispatch      # Hourly operation schedules
      # - pipe_diameters        # (for network_design mode)

    # Objective function
    objective: minimize_total_cost

    # Cost components
    costs:
      include_capex: true
      include_opex: true
      include_fuel: true
      include_co2: true
      include_demand_charge: true

      # Economic parameters
      discount_rate: 0.05
      planning_horizon_yr: 15

    # Constraints
    constraints:
      # Energy balance
      enforce_heat_demand: true
      enforce_power_balance: true

      # Network constraints
      max_pipe_velocity_m_s: 2.5
      min_pressure_bar: 2.0
      max_pressure_bar: 16.0

      # Emissions
      max_co2_emissions_kg_yr: null  # No limit

      # Reliability
      n_minus_1_criterion: false  # Redundancy requirement

  # Solver settings
  solver:
    name: gurobi
    timelimit_s: 3600
    mip_gap: 0.01
```

---

## 🚀 Implementation Roadmap

### Phase 1: Core Schema Migration (Week 1-2)

**Files to Create:**
1. `energis/config/schemas/asset_schema.py`
   ```python
   @dataclass
   class AssetCapacity:
       """Existing + Expansion capacity model."""
       existing_mw: float = 0.0
       expansion_enabled: bool = False
       expansion_min_mw: float = 0.0
       expansion_max_mw: float = 0.0
       capex_eur_per_mw: float = 0.0
       opex_eur_per_mw_yr: float = 0.0
       lifetime_yr: float = 20.0

   @dataclass
   class ComponentAsset:
       """Unified component asset."""
       id: str
       technology: str
       existing: AssetCapacity
       expansion: AssetCapacity
       metadata: Dict[str, Any] = field(default_factory=dict)
   ```

2. `energis/config/schemas/network_schema.py`
   ```python
   @dataclass
   class NetworkNode:
       id: str
       type: str  # producer, consumer, junction
       components: List[str] = field(default_factory=list)
       demand_column: Optional[str] = None
       location: Optional[Dict[str, float]] = None

   @dataclass
   class Pipe:
       id: str
       from_node: str
       to_node: str
       length_m: float
       diameter_mm: float
       insulation_type: str
       existing_installed: bool = False
       expansion_enabled: bool = False

   @dataclass
   class ThermalNetwork:
       id: str
       type: str  # district_heating, cooling, process_heat
       temperature_level: str  # high, medium, low
       supply_temp_bounds_c: Tuple[float, float]
       return_temp_bounds_c: Tuple[float, float]
       nodes: Dict[str, NetworkNode]
       pipes: Dict[str, Pipe]
   ```

**Migration Strategy:**
- Keep old config format working (backward compatibility)
- Add new parsers that convert old → new
- Deprecation warnings for old format

### Phase 2: Network Physics Model (Week 3-4)

**New Module:** `energis/models/network_physics.py`
```python
class HydraulicNetwork:
    """Multi-node hydraulic network with pressure/temperature/delay."""

    def add_mass_balance_constraints(self, model, nodes):
        """Σ m_in = Σ m_out at each node."""
        pass

    def add_enthalpy_balance_constraints(self, model, nodes):
        """Σ (m*h)_in = Σ (m*h)_out at each node."""
        pass

    def add_pressure_drop_constraints(self, model, pipes):
        """ΔP = f(m_flow, diameter, length, roughness)."""
        pass

    def add_temperature_loss_constraints(self, model, pipes):
        """ΔT = f(length, insulation, T_ground, m_flow)."""
        pass

    def add_time_delay_constraints(self, model, pipes):
        """Transport delay: τ = length / velocity."""
        pass
```

### Phase 3: Documentation & Examples (Week 5)

1. Migration guide: `docs/CONFIG_MIGRATION.md`
2. Example configs for each scenario type
3. Validation tool: `energis config validate <file>`

---

## 📊 Comparison: Old vs New

| Aspect | Old Config | New Config |
|--------|-----------|------------|
| **Brownfield/Greenfield** | Binary flag `brownfield_mode` | Unified `existing` + `expansion` |
| **Repetition** | Copy-paste HP1, HP2, HP3, HP4 | Reference technology template |
| **Network** | Single-bus simplification | Multi-node graph with physics |
| **Temperature** | Single level | Multi-level networks |
| **Pipes** | No explicit pipes | Explicit pipe segments |
| **Pressure** | Not modeled | Pressure balance at nodes |
| **Time Delay** | Not modeled | Transport lag modeled |
| **Clarity** | Overlapping concepts | Clear separation |

---

## ✅ Benefits

1. **No Brownfield/Greenfield Distinction:** Every asset is the same data structure
2. **Less Repetition:** Technology templates are reusable
3. **Network-Ready:** Supports arbitrary network topologies
4. **Physics-Based:** Proper enthalpy, pressure, mass balances
5. **Future-Proof:** Easy to add new network features (valves, heat exchangers, etc.)
6. **Type-Safe:** Dataclass validation catches errors early

---

## 🎯 Next Steps

1. **Review this proposal** - Feedback on schema design
2. **Create dataclass schemas** - Implement `asset_schema.py`, `network_schema.py`
3. **Write migration tool** - Convert old configs to new format
4. **Implement network physics** - Multi-node hydraulic model
5. **Update documentation** - User guide for new config format

---

**Status:** PROPOSAL - Awaiting Review
**Author:** Claude Sonnet 4.5
**Date:** 2026-02-16
