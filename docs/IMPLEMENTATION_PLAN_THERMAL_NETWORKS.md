# Thermal Network Implementation Plan - EnerGIS

**Version:** 1.0 (Brownfield Focus with Temperature Modeling)
**Start Date:** 2025-12-10
**Target:** Stadtbach with Real Pipe Data

---

## Executive Summary

This plan implements thermal network modeling for EnerGIS with focus on:
- ✅ **Brownfield optimization** (Stadtbach with known pipe layout)
- ✅ **Temperature-dependent losses** (outdoor temperature coupling)
- ✅ **Supply/return separation** (2-pipe model)
- ✅ **Real pipe data integration** (diameters, lengths from GIS)
- ✅ **Dashboard visualization** (network topology, flows, temperatures)
- ✅ **MILP optimization** (fast solve times, no simulation coupling)

**Timeline:** 6-8 weeks for full brownfield capability

---

## 1. Implementation Phases

### Phase 1: Foundation (Week 1-2) ⭐ START HERE
- Core pipe component with temperature-dependent losses
- Node component for network topology
- System builder integration
- Basic YAML configuration

**Deliverable:** Simple 3-node network runs and optimizes

### Phase 2: Stadtbach Integration (Week 3-4)
- Load real pipe data from your GIS
- Demand splitting utility
- Full Stadtbach network configuration
- Results export for dashboard

**Deliverable:** Stadtbach optimizes with realistic network

### Phase 3: Advanced Features (Week 5-6)
- Pressure constraints (optional for brownfield)
- Pump component
- Enhanced temperature modeling
- Validation against historical data

**Deliverable:** Production-ready brownfield optimization

### Phase 4: Dashboard & Visualization (Week 7-8)
- Network topology visualization
- Flow animation
- Temperature heatmaps
- Cost breakdown charts

**Deliverable:** Full dashboard integration

---

## 2. Temperature Modeling Strategy

### 2.1 Temperature Dependencies

**Heat Loss Model:**
```python
Q_loss[pipe, t] = U_effective(T_avg, insulation) × Length × (T_pipe[t] - T_ground[t])

where:
  U_effective = U_base × correction_factor(T_avg)
  T_ground[t] = f(T_outdoor[t], depth, soil_properties)
```

**Ground Temperature Estimation:**
```python
# Simple model (sufficient for planning)
T_ground[t] = T_outdoor[t] × 0.6 + 10°C  # Damped outdoor temp

# Advanced model (optional Phase 3)
T_ground[t, depth] = T_annual_avg + amplitude × exp(-depth/δ) × sin(ωt - depth/δ)
  where δ = sqrt(2α/ω) = thermal penetration depth
```

**Temperature Propagation:**
```python
# Supply pipe: loses heat
T_supply_out[t] = T_supply_in[t] - Q_loss[t] / (m_dot[t] × c_p)

# Return pipe: gains heat from ground (if T_return < T_ground)
T_return_out[t] = T_return_in[t] + Q_exchange[t] / (m_dot[t] × c_p)
```

### 2.2 Supply Temperature Optimization

**Variable Supply Temperature:**
- Winter (high outdoor demand): T_supply = 90-95°C (minimize diameter needs)
- Summer (low demand): T_supply = 70-80°C (minimize heat losses)
- Trade-off: Higher temp → less losses per MW, but higher base losses

**Implementation:**
```python
# Option 1: Fixed seasonal temperatures (simple)
T_supply[t] = 90°C if month(t) in [Nov-Mar] else 80°C

# Option 2: Demand-dependent (better)
T_supply[t] = T_min + (T_max - T_min) × (demand[t] / demand_max)

# Option 3: Optimized (Phase 3)
T_supply[t] = decision variable with bounds [70, 95]°C
```

---

## 3. Component Architecture

### 3.1 PipePairComponent (NEW)

**Purpose:** Models one pipe segment with supply + return

**Variables:**
```python
# Flow (kg/s)
m_dot_supply[t]    # Supply flow (producer → consumer)
m_dot_return[t]    # Return flow (consumer → producer)

# Temperature (°C)
T_supply_in[t], T_supply_out[t]
T_return_in[t], T_return_out[t]

# Heat (MW)
Q_delivered[t]     # Net heat delivered to consumers
Q_loss_supply[t]   # Heat loss from supply pipe
Q_loss_return[t]   # Heat loss from return pipe

# Investment (if enabled)
diameter_choice[d] # Binary for each diameter option
build             # Binary: build this pipe or not
```

**Key Constraints:**
```python
# Mass balance
m_dot_supply[t] == m_dot_return[t]  # (for single pipe without branches)

# Heat loss (temperature-dependent)
Q_loss_supply[t] == U_eff × L × (T_supply_avg[t] - T_ground[t])

# Temperature drop
T_supply_out[t] == T_supply_in[t] - Q_loss_supply[t] / (m_dot[t] × c_p)

# Flow-heat relationship
Q_delivered[t] == m_dot[t] × c_p × (T_supply_out[t] - T_return_in[t])
```

### 3.2 ThermalNodeComponent (NEW)

**Purpose:** Connection point for multiple pipes and components

**Variables:**
```python
# Temperature at node
T_supply[t]        # Supply temperature (mixed if multiple inflows)
T_return[t]        # Return temperature from consumers

# Pressure (Phase 3)
P_supply[t]        # Supply pressure [bar]
P_return[t]        # Return pressure [bar]

# Demand (if consumer node)
Q_demand[t]        # Heat demand at this node [MW]
```

**Key Constraints:**
```python
# Mass balance at node
sum(m_dot_in[pipe, t]) == sum(m_dot_out[pipe, t]) + m_dot_local_demand[t]

# Temperature mixing (if multiple inflows)
T_mixed[t] × sum(m_dot_in) == sum(T_in[pipe, t] × m_dot_in[pipe, t])

# Demand satisfaction
Q_demand[t] == m_dot_local[t] × c_p × (T_supply[t] - T_return[t])
```

### 3.3 NetworkManager (NEW)

**Purpose:** Coordinates all network components

**Responsibilities:**
- Parse network topology YAML
- Create pipe and node components
- Connect components to heat sources (HPs, generators)
- Connect components to demand zones
- Aggregate costs for objective function

---

## 4. YAML Configuration Design

### 4.1 Stadtbach Network Configuration

```yaml
# configs/networks/stadtbach_network.yaml

metadata:
  name: Stadtbach District Heating Network
  description: Real brownfield network with existing pipes
  source: GIS data 2024
  coordinate_system: EPSG:25832  # UTM Zone 32N

parameters:
  # Temperature settings
  supply_temp_nominal_c: 90
  supply_temp_summer_c: 80
  return_temp_nominal_c: 50
  supply_temp_optimization: false  # Phase 1: fixed, Phase 3: variable

  # Environmental
  ground_temp_model: simple  # simple, detailed
  soil_thermal_conductivity: 1.5  # W/(m·K)
  pipe_burial_depth_m: 1.2

  # Hydraulic (Phase 3)
  min_pressure_bar: 2.0
  max_pressure_bar: 10.0
  max_velocity_m_s: 2.5

# Central plant location
central_plant:
  node_id: plant_central
  coordinates: {x: 0, y: 0, elevation: 445}
  components:
    heat_pumps: [HP1, HP2, HP3, HP4]
    generators: [hkw, gtost, ava]
    storage: [tes_main]

# Consumer zones (demand split from total)
consumer_zones:
  - node_id: zone_north
    name: "Nordviertel"
    coordinates: {x: 1500, y: 800, elevation: 455}
    demand_fraction: 0.35  # 35% of total Stadtbach demand
    return_temp_c: 50

  - node_id: zone_south
    name: "Südviertel"
    coordinates: {x: 1800, y: -400, elevation: 440}
    demand_fraction: 0.40
    return_temp_c: 50

  - node_id: zone_east
    name: "Ostviertel"
    coordinates: {x: 2500, y: 200, elevation: 448}
    demand_fraction: 0.25
    return_temp_c: 50

# Pipe network (from your GIS data)
pipes:
  # Main distribution pipes
  - id: main_north
    from_node: plant_central
    to_node: zone_north
    length_m: 1700
    elevation_change_m: 10  # Uphill

    # Existing pipe properties
    existing: true
    current_diameter_supply_mm: 200
    current_diameter_return_mm: 200
    installation_year: 2010

    # Insulation properties
    insulation_type: standard
    u_value_supply_w_per_m_k: 0.28
    u_value_return_w_per_m_k: 0.30  # Return typically worse

    # Investment options (brownfield: can upgrade)
    upgrade_options:
      enabled: true
      diameter_options: [200, 250, 300]  # Keep existing or upgrade
      insulation_options: [standard, enhanced]
      enhanced_u_value: 0.18
      upgrade_cost_eur_per_m: 200  # Cost to upgrade

  - id: main_south
    from_node: plant_central
    to_node: zone_south
    length_m: 1850
    elevation_change_m: -5  # Downhill

    existing: true
    current_diameter_supply_mm: 200
    current_diameter_return_mm: 150
    installation_year: 2008
    insulation_type: standard
    u_value_supply_w_per_m_k: 0.30
    u_value_return_w_per_m_k: 0.35

    upgrade_options:
      enabled: true
      diameter_options: [200, 250]
      insulation_options: [standard, enhanced]
      enhanced_u_value: 0.18
      upgrade_cost_eur_per_m: 180

  - id: main_east
    from_node: plant_central
    to_node: zone_east
    length_m: 2500
    elevation_change_m: 3

    existing: true
    current_diameter_supply_mm: 150
    current_diameter_return_mm: 150
    installation_year: 2012
    insulation_type: enhanced  # Already upgraded
    u_value_supply_w_per_m_k: 0.20
    u_value_return_w_per_m_k: 0.22

    upgrade_options:
      enabled: false  # Don't upgrade this one

# Pipe catalog (for new pipes or upgrades)
pipe_catalog:
  DN150:
    diameter_mm: 150
    diameter_inner_mm: 140
    capex_eur_per_m: 850
    u_value_standard: 0.30
    u_value_enhanced: 0.18
    max_pressure_bar: 16
    roughness_mm: 0.05

  DN200:
    diameter_mm: 200
    diameter_inner_mm: 187
    capex_eur_per_m: 1100
    u_value_standard: 0.28
    u_value_enhanced: 0.17
    max_pressure_bar: 16
    roughness_mm: 0.05

  DN250:
    diameter_mm: 250
    diameter_inner_mm: 235
    capex_eur_per_m: 1400
    u_value_standard: 0.26
    u_value_enhanced: 0.16
    max_pressure_bar: 16
    roughness_mm: 0.05

  DN300:
    diameter_mm: 300
    diameter_inner_mm: 282
    capex_eur_per_m: 1750
    u_value_standard: 0.24
    u_value_enhanced: 0.15
    max_pressure_bar: 16
    roughness_mm: 0.05
```

### 4.2 System Configuration Integration

```yaml
# configs/systems/stadtbach_with_network.system.yaml

# Import existing heat pump and generator configs
extends: stadtbach_baseline.system.yaml

# Enable thermal network
thermal_network:
  enabled: true
  topology_file: networks/stadtbach_network.yaml

  # Time-varying temperatures
  use_outdoor_temperature: true
  outdoor_temp_column: T_outdoor  # From Import_Data.xlsx

  # Output options
  export_network_results: true
  export_pipe_flows: true
  export_temperatures: true
  export_for_dashboard: true  # NEW: Dashboard-ready JSON
```

---

## 5. Dashboard Visualization Requirements

### 5.1 New Dashboard Views

**A) Network Topology View**
```
[Geographic Layout]
├── Nodes (circles)
│   ├── Plant (green, large)
│   ├── Consumers (blue, sized by demand)
│   └── Junctions (gray, small)
├── Pipes (lines)
│   ├── Color: Temperature (gradient red→blue)
│   ├── Width: Flow rate (thicker = more flow)
│   └── Style: Dashed if upgraded
└── Interactive
    ├── Click node → Show demand/production
    ├── Click pipe → Show losses, temp drop
    └── Time slider → Animate flows
```

**B) Temperature Profile Chart**
```
Y-axis: Temperature (°C)
X-axis: Distance from plant (m)
Lines:
  - Supply temperature (red line, decreasing)
  - Return temperature (blue line)
  - Ground temperature (brown dashed)
  - Demand temperature (markers at consumer nodes)
```

**C) Network Performance Dashboard**
```
KPIs:
  - Total heat delivered: X MWh
  - Total heat losses: Y MWh (Z%)
  - Average supply temp: 87°C
  - Peak flow rate: 150 kg/s
  - Pipe upgrade recommendations: ✓ 2 pipes

Charts:
  - Heat loss by pipe segment (bar chart)
  - Temperature vs outdoor temp (scatter)
  - Flow duration curve (sorted)
  - Investment vs. losses saved (Pareto)
```

### 5.2 Export Format

**JSON Structure for Dashboard:**
```json
{
  "metadata": {
    "scenario": "stadtbach_2024",
    "timestamp": "2024-12-10T10:30:00",
    "solver_time_s": 127.3
  },
  "network_topology": {
    "nodes": [
      {
        "id": "plant_central",
        "type": "plant",
        "coordinates": {"x": 0, "y": 0},
        "production_mwh": 45230.5
      },
      {
        "id": "zone_north",
        "type": "consumer",
        "coordinates": {"x": 1500, "y": 800},
        "demand_mwh": 15830.7,
        "demand_fraction": 0.35
      }
    ],
    "pipes": [
      {
        "id": "main_north",
        "from": "plant_central",
        "to": "zone_north",
        "length_m": 1700,
        "diameter_current_mm": 200,
        "diameter_optimized_mm": 200,
        "upgrade_recommended": false,
        "total_heat_loss_mwh": 234.5,
        "avg_flow_kg_s": 87.3
      }
    ]
  },
  "time_series": {
    "resolution": "hourly",
    "pipe_flows": {
      "main_north": [12.3, 15.7, ...],  // 8760 values
      "main_south": [18.5, 21.2, ...]
    },
    "temperatures": {
      "plant_supply": [90.0, 90.0, ...],
      "zone_north_supply": [88.2, 88.5, ...],
      "zone_north_return": [50.0, 50.0, ...]
    },
    "heat_losses": {
      "main_north": [0.034, 0.041, ...],  // MW
      "total": [0.098, 0.115, ...]
    }
  },
  "investment_results": {
    "pipe_upgrades": [
      {
        "pipe_id": "main_north",
        "action": "none",
        "cost_eur": 0
      }
    ],
    "total_investment_eur": 0,
    "annual_savings_eur": 0
  }
}
```

---

## 6. Implementation Tasks

### Week 1-2: Core Components

**Task 1.1: PipePairComponent** (Priority 1) ⭐
- [ ] Create `energis/models/blocks/pipe_pair.py`
- [ ] Implement temperature-dependent heat loss
- [ ] Add outdoor temperature coupling
- [ ] Support supply/return separation
- [ ] Unit tests

**Task 1.2: ThermalNodeComponent** (Priority 1) ⭐
- [ ] Create `energis/models/blocks/thermal_node.py`
- [ ] Implement mass balance
- [ ] Temperature mixing logic
- [ ] Demand connection
- [ ] Unit tests

**Task 1.3: NetworkManager** (Priority 1) ⭐
- [ ] Create `energis/models/network_manager.py`
- [ ] Parse network YAML
- [ ] Coordinate component creation
- [ ] Connect to system_builder
- [ ] Integration tests

**Task 1.4: System Builder Integration** (Priority 1) ⭐
- [ ] Modify `energis/models/system_builder.py`
- [ ] Add network initialization
- [ ] Connect sources to network
- [ ] Connect demand zones
- [ ] Update objective function

### Week 3-4: Stadtbach Integration

**Task 2.1: Data Preparation** (Priority 2)
- [ ] Script to load your GIS pipe data
- [ ] Demand splitting utility
- [ ] Create stadtbach_network.yaml
- [ ] Validate data consistency

**Task 2.2: Full System Configuration** (Priority 2)
- [ ] Create stadtbach_with_network.system.yaml
- [ ] Configure all pipes from GIS
- [ ] Set up consumer zones
- [ ] Add outdoor temperature data

**Task 2.3: Results Export** (Priority 2)
- [ ] Implement dashboard JSON export
- [ ] Create visualization data structures
- [ ] Add network results to output
- [ ] Validation against historical data

### Week 5-6: Advanced Features

**Task 3.1: Pressure Modeling** (Priority 3)
- [ ] Add pressure variables to nodes
- [ ] Implement linearized pressure drop
- [ ] Pressure balance constraints
- [ ] Min/max pressure limits

**Task 3.2: Pump Component** (Priority 3)
- [ ] Create `energis/models/blocks/pump.py`
- [ ] Pressure boost modeling
- [ ] Electricity consumption
- [ ] Investment optimization

**Task 3.3: Enhanced Temperature Model** (Priority 3)
- [ ] Detailed ground temperature model
- [ ] Variable supply temperature optimization
- [ ] Seasonal optimization
- [ ] COP dependency on return temp

### Week 7-8: Dashboard Integration

**Task 4.1: Topology Visualization** (Priority 2)
- [ ] Network graph rendering
- [ ] Interactive node/pipe selection
- [ ] Flow animation
- [ ] Temperature coloring

**Task 4.2: Performance Charts** (Priority 2)
- [ ] Heat loss breakdown
- [ ] Temperature profiles
- [ ] Flow duration curves
- [ ] Investment analysis

**Task 4.3: User Interface** (Priority 2)
- [ ] Network configuration UI
- [ ] Scenario comparison
- [ ] Export/import functionality
- [ ] Help documentation

---

## 7. Effort Estimation

### Developer Time Required

**Phase 1 (Weeks 1-2): Core Implementation**
- Senior developer: 60-80 hours
- Focus: Component architecture, MILP formulation
- Risk: Medium (new component type)

**Phase 2 (Weeks 3-4): Stadtbach Integration**
- Developer: 40-60 hours
- Focus: Data engineering, configuration
- Risk: Low (standard integration)

**Phase 3 (Weeks 5-6): Advanced Features**
- Senior developer: 40-60 hours
- Focus: Hydraulics, optimization
- Risk: Medium (complexity)

**Phase 4 (Weeks 7-8): Dashboard**
- Frontend developer: 40-60 hours
- Focus: Visualization, UI/UX
- Risk: Low (standard web dev)

**Total Effort: 180-260 hours (4.5-6.5 weeks full-time)**

### Skills Required
- Python/Pyomo: ⭐⭐⭐⭐⭐ (critical)
- Thermal engineering: ⭐⭐⭐⭐ (important)
- MILP optimization: ⭐⭐⭐⭐ (important)
- Web development: ⭐⭐⭐ (nice to have)

---

## 8. Success Criteria

### Phase 1 Success
- ✅ 3-node network solves in <1 minute
- ✅ Heat losses match analytical calculation (±5%)
- ✅ Temperature drop calculated correctly
- ✅ All unit tests pass

### Phase 2 Success
- ✅ Full Stadtbach network solves in <15 minutes
- ✅ Pipe diameters optimized correctly
- ✅ Total heat losses realistic (5-10% of delivered)
- ✅ Dashboard JSON exports correctly

### Phase 3 Success
- ✅ Pressure constraints satisfied
- ✅ Pump sizing optimized
- ✅ Variable supply temp reduces costs by 2-5%
- ✅ Validation against TESPy within 10%

### Phase 4 Success
- ✅ Network topology renders correctly
- ✅ Flow animation smooth and intuitive
- ✅ All charts load in <2 seconds
- ✅ User can compare scenarios easily

---

## 9. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Solve time too long | High | Temporal aggregation, decomposition |
| Temperature model inaccurate | Medium | Validation with TESPy, safety margins |
| GIS data quality issues | Medium | Data validation scripts, fallbacks |
| Dashboard integration complex | Low | Use existing frameworks (Plotly, D3.js) |
| User adoption challenges | Medium | Good documentation, training sessions |

---

## 10. Next Steps (This Week)

### Day 1-2: Setup
1. ✅ Review this plan (DONE)
2. Create branch structure
3. Set up testing framework
4. Prepare GIS data template

### Day 3-5: Core Implementation
1. Implement PipePairComponent
2. Implement ThermalNodeComponent
3. Write unit tests
4. Initial integration

### Day 6-7: First Test
1. Create simple 3-node test case
2. Run and debug
3. Validate results
4. Document learnings

---

## 11. Long-Term Vision

### After Phase 4 (Months 3-6)
- Multiple networks (different temperature levels)
- Dynamic network topology optimization
- Real-time operational optimization
- Predictive maintenance integration
- Multi-objective optimization (cost, emissions, reliability)

### Research Opportunities
- Publish Applied Energy paper on MILP network optimization
- Compare with commercial tools (Termis, Netsim)
- Case studies with industry partners
- Open-source contribution to oemof ecosystem

---

**Ready to start? Let's implement Phase 1!** 🚀
