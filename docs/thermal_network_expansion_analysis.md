# Thermal Network Modeling Expansion: Analysis & Development Plan

**Project:** EnerGIS Heat Planning Framework
**Date:** 2025-12-10
**Status:** Strategic Analysis & Roadmap

---

## Executive Summary

This document provides a comprehensive analysis for expanding the EnerGIS framework to include detailed thermal-hydraulic network modeling, enabling optimization of district heating systems with explicit pipe networks, pumps, pressure constraints, and temperature/pressure losses.

**Key Recommendations:**
1. **Phased approach** starting with simplified linear pipe models within existing Pyomo MILP framework
2. **Native MILP integration** preferred over coupling with external simulation tools (TESPy)
3. **YAML-based network definition** extending current configuration system
4. **Three development phases:** Basic Pipes → Hydraulic Constraints → Full Thermo-Hydraulic

**Expected Benefits:**
- Realistic network topology optimization (pipe routing & sizing)
- Pressure and flow limit enforcement
- Temperature loss accounting across distribution networks
- Pump sizing and placement optimization
- Better brownfield/greenfield scenario analysis

---

## 1. Current State Analysis

### 1.1 Existing Modeling Approach

**Architecture:** Nodal bus abstraction without explicit network topology

```
Current Model:
┌─────────────┐
│   Heat      │
│  Sources    │──┐
│ (HP, Gen)   │  │
└─────────────┘  │
                 ├──► [HEAT BUS] ──► Demand + Storage
┌─────────────┐  │    (Single Node)
│  Storage    │──┘
└─────────────┘
```

**Limitations:**
- ❌ No pipe representation (length, diameter, material)
- ❌ No pressure constraints or pump requirements
- ❌ No spatial network topology
- ❌ No flow-dependent losses (pressure drop, heat loss)
- ❌ Cannot optimize network layout or pipe sizing
- ✅ Simple bus loss factors (constant percentage)
- ✅ Fast MILP optimization (minutes for annual planning)

### 1.2 Stadtbach Brownfield Case

**Current Representation:**
- 4 heat pumps (HP1-HP4) with waste heat recovery → Single heat bus
- 7 existing generators → Single heat bus
- Optional storage → Single heat bus
- Demand profile → Single aggregated load

**Missing Spatial Elements:**
- No representation of physical distances between components
- No pipe network connecting sources to consumers
- No pump stations or pressure boosting
- No differentiation between supply/return temperatures

---

## 2. Literature & Framework Review

### 2.1 TESPy (Thermal Engineering Systems in Python)

**Overview:**
- Part of oemof framework family
- Equation-based thermodynamic simulation
- Non-linear solver (Newton-Raphson method)

**Capabilities:**
- ✅ Detailed component models (pipes, pumps, heat exchangers, valves)
- ✅ Coupled thermal-hydraulic simulation
- ✅ Pressure drop calculations (Darcy-Weisbach, local losses)
- ✅ Temperature-dependent fluid properties
- ✅ Heat losses with ambient temperature coupling
- ✅ District heating network examples available

**Limitations for Our Use Case:**
- ❌ **Non-linear simulation** (not optimization)
- ❌ No native MILP integration - requires external coupling
- ❌ Computational overhead for large networks
- ❌ Iterative simulation-optimization workflow needed

**Integration Pattern (used in oemof ecosystem):**
```
TESPy Simulation → Extract Characteristics → oemof.solph Optimization (Pyomo)
     ↓                      ↓                           ↓
  Detailed              COP curves,                 MILP with
  Thermo-Hydraulics    Pressure drops           linearized constraints
```

**Verdict:** ⚠️ Useful for **validation** and **detailed design**, but **too complex** for integrated optimization loop.

### 2.2 PyPSA (Python for Power System Analysis)

**Thermal Network Approach:**
- ✅ High-level abstraction via "Link" components
- ✅ Linear losses (percentage-based)
- ✅ Heat transport with efficiency factors
- ✅ Integrated with Pyomo MILP optimization

**Limitations:**
- ❌ No hydraulic physics (pressure, flow velocity)
- ❌ No temperature-dependent losses
- ❌ No pipe diameter optimization

**Verdict:** Similar abstraction level to current EnerGIS approach.

### 2.3 oemof.DHNx (District Heating Network Extension)

**Approach:**
- ✅ Adds pipe transformers to energy system models
- ✅ Linearized heat loss models
- ✅ Insulation thickness and material selection
- ✅ GIS integration for network geometry
- ✅ Pyomo-based optimization

**Key Feature:** Pipes as "transformers" with:
- Input flow (heat at source)
- Output flow (heat at sink minus losses)
- Investment decisions (pipe diameter, insulation)

**Verdict:** ✅ **Closest match** to our requirements - similar architecture to EnerGIS.

### 2.4 Recent Academic Approaches

**MILP Formulations for District Heating:**

1. **Pipe Sizing with Integer Variables**
   - Discrete diameter choices: d ∈ {DN50, DN80, DN100, DN150, ...}
   - Binary variables for each pipe-diameter combination
   - CAPEX = f(diameter, length)

2. **Linearized Pressure Drop**
   - Darcy-Weisbach: ΔP = f × (L/D) × (ρv²/2)
   - Linearization: ΔP ≈ K × ṁ² or piecewise linear segments
   - Constraint: Σ(pressure drops in loop) = 0

3. **Temperature Propagation**
   - Heat loss per pipe: Q_loss = U × A × (T_pipe - T_ambient)
   - Linear approximation: T_out = T_in - ΔT_loss(length, insulation)

4. **Computational Challenges**
   - Large networks (1000+ nodes): 15+ minutes solve time
   - Integer variables create symmetries → need efficient formulations
   - Two-phase approaches: MILP for topology → NLP for detailed hydraulics

---

## 3. Integration Approaches: Options Analysis

### Option A: External TESPy Coupling (Simulation-Optimization Loop)

```
┌─────────────────────────────────────────────────┐
│  OUTER LOOP: EnerGIS Pyomo Optimization         │
│  - Optimize capacities, pipe diameters, flow    │
│  - Uses simplified linear constraints           │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  INNER LOOP: TESPy Simulation                   │
│  - Validate pressure/temperature with detailed  │
│    non-linear physics                           │
│  - Return violations → penalize in optimization │
└─────────────────────────────────────────────────┘
```

**Pros:**
- ✅ High-fidelity validation
- ✅ Detailed component modeling
- ✅ Can use existing TESPy libraries

**Cons:**
- ❌ Complex coupling architecture
- ❌ Slow convergence (iterative loop)
- ❌ Risk of infeasibility (MILP solution rejected by TESPy)
- ❌ Two separate model definitions to maintain

**Recommendation:** ⚠️ Only if detailed non-linear validation is critical.

---

### Option B: Native MILP Pipe Components (Recommended)

```
┌─────────────────────────────────────────────────┐
│  Single Pyomo MILP Model                        │
│  ┌───────────────┐  ┌──────────────┐           │
│  │  Heat Sources │  │ Pipe Network │           │
│  │  (existing)   │──┤ (new)        │           │
│  └───────────────┘  │ - Pipes      │           │
│                     │ - Pumps      │           │
│                     │ - Nodes      │           │
│                     └──────────────┘           │
│  Constraints:                                   │
│  - Energy balances (existing)                   │
│  - Pressure balances (new)                      │
│  - Flow limits (new)                            │
│  - Temperature losses (new, linearized)         │
└─────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Single unified optimization
- ✅ Guaranteed feasibility
- ✅ Fast solve times (MILP solvers are mature)
- ✅ Consistent with existing architecture
- ✅ Easier to maintain and extend

**Cons:**
- ❌ Linearization approximations needed
- ❌ Less detailed than TESPy simulation
- ❌ Need to implement pipe physics from scratch

**Recommendation:** ✅ **Preferred approach** for integration with planning optimization.

---

### Option C: Hybrid Approach

```
Phase 1: Perfect Forecast with native MILP pipes
    ↓
Phase 2: Rolling Horizon operations
    ↓
Phase 3: Post-optimization TESPy validation (offline)
```

**Pros:**
- ✅ Best of both worlds
- ✅ Fast optimization, detailed validation
- ✅ Can refine designs based on TESPy feedback

**Cons:**
- ❌ Still requires maintaining two models
- ❌ Manual iteration needed for design refinement

**Recommendation:** ✅ **Best for production systems** - optimize with MILP, validate with TESPy.

---

## 4. Proposed MILP Pipe Modeling Approach

### 4.1 Component Architecture

**New Components to Add:**

1. **PipeComponent**
   - Connects two nodes (from_node, to_node)
   - Variables: mass_flow[t], diameter, length (fixed)
   - Constraints: pressure drop, heat loss, flow limits

2. **PumpComponent**
   - Variables: power[t], on[t], capacity
   - Constraints: pressure boost, flow relationship

3. **NodeComponent** (extends Bus)
   - Variables: pressure[t], temperature[t]
   - Constraints: mass balance, pressure balance

### 4.2 Mathematical Formulation

#### Pressure Drop Linearization

**Non-linear (Darcy-Weisbach):**
```
ΔP = f × (L/D) × (ρv²/2) = K × ṁ²
```

**MILP Approximation Options:**

**Option 1: Piecewise Linear**
```python
# Define breakpoints for mass flow
ṁ_segments = [0, 10, 20, 40, 80, 100] kg/s

# For each segment i:
ΔP[i] = slope[i] × ṁ[i]

# SOS2 (Special Ordered Set Type 2) constraints
# Only adjacent segments can be active
```

**Option 2: Linear Overestimation**
```python
# Conservative upper bound
ΔP ≤ K_max × ṁ  # where K_max from max expected flow

# Valid for design optimization (ensures feasibility)
```

**Option 3: Fixed Diameter with Flow-Pressure Lookup**
```python
# For each discrete diameter choice d:
# Pre-calculate: ΔP(ṁ) table
# Use piecewise linear representation
```

#### Pipe Diameter Selection

```python
# Binary variables for discrete diameters
model.pipe_diameter_choice = pyo.Var(
    model.pipes,
    model.diameter_options,  # DN50, DN80, DN100, ...
    domain=pyo.Binary
)

# Exactly one diameter per pipe
model.one_diameter = pyo.Constraint(
    model.pipes,
    rule=lambda m, p: sum(m.pipe_diameter_choice[p, d]
                          for d in m.diameter_options) == 1
)

# CAPEX calculation
CAPEX_pipe[p] = sum(
    diameter_choice[p, d] × length[p] × unit_cost[d]
    for d in diameter_options
)

# Pressure drop linked to diameter choice
ΔP[p, t] = sum(
    diameter_choice[p, d] × pressure_drop_coeff[d] × flow[p, t]
    for d in diameter_options
)
```

#### Temperature Loss Model

**Simplified Linear Model:**
```python
# Heat loss proportional to pipe length and temp difference
Q_loss[p, t] = U_value[p] × length[p] × (T_supply[t] - T_ambient)

# Temperature drop
T_out[p, t] = T_in[p, t] - Q_loss[p, t] / (ṁ[p, t] × c_p)

# Linearization: use average flow or piecewise segments
```

**Investment-Dependent Insulation:**
```python
# Binary choice: standard vs. enhanced insulation
U_value[p] = U_standard × standard_choice[p]
           + U_enhanced × enhanced_choice[p]

CAPEX_insulation[p] = extra_cost × enhanced_choice[p] × length[p]
```

#### Pressure Balance Constraints

**Node Pressure Balance:**
```python
# At each node n, time t:
P[n, t] = P[source]
        - sum(ΔP[p, t] for p in pipes_to_node[n])
        + sum(ΔP_pump[pump, t] for pump in pumps_at_node[n])

# Min/max pressure limits
P_min ≤ P[n, t] ≤ P_max
```

**Loop Constraints (Kirchhoff for Pressure):**
```python
# For each closed loop in network:
sum(ΔP[p] for p in loop) = 0  # (considering flow direction)
```

#### Pump Modeling

```python
# Pump power consumption
P_el[pump, t] = (ṁ[pump, t] × ΔP_pump[pump, t]) / (ρ × η_pump)

# Pump capacity constraint
ΔP_pump[pump, t] ≤ ΔP_rated × on[pump, t]
ṁ[pump, t] ≤ ṁ_max × on[pump, t]

# Investment decision
on[pump, t] ≤ build[pump]
CAPEX_pump[pump] = build[pump] × cost_per_unit[pump]
```

### 4.3 Network Topology Representation

**Two Approaches:**

#### Approach 1: Fixed Topology (Brownfield Focus)

```yaml
# configs/networks/stadtbach_network.yaml
network:
  nodes:
    - id: central_plant
      type: source
      x: 0
      y: 0

    - id: district_1
      type: consumer
      x: 1200  # meters
      y: 500
      demand_profile: district_1_demand

    - id: district_2
      type: consumer
      x: 2000
      y: 800
      demand_profile: district_2_demand

  pipes:
    - id: pipe_1
      from: central_plant
      to: junction_1
      length: 1200  # meters
      diameter_options: [DN100, DN150, DN200]
      insulation_options: [standard, enhanced]

    - id: pipe_2
      from: junction_1
      to: district_1
      length: 300
      diameter_options: [DN50, DN80, DN100]

  pumps:
    - id: pump_main
      location: central_plant
      investment:
        enabled: true
        capacity_max_bar: 10
        capex_eur_per_kw: 500
```

**Pros:**
- ✅ Simple to implement
- ✅ Suitable for Stadtbach brownfield case
- ✅ Optimize pipe sizes on existing routes

#### Approach 2: Topology Optimization (Greenfield)

```python
# Allow optimization to choose which pipes to build
model.pipe_build = pyo.Var(model.potential_pipes, domain=pyo.Binary)

# Flow can only exist if pipe is built (Big-M)
model.flow_gate = pyo.Constraint(
    model.potential_pipes, model.t,
    rule=lambda m, p, t: m.flow[p, t] <= M_FLOW × m.pipe_build[p]
)

# CAPEX only charged if built
CAPEX[p] = pipe_build[p] × (length[p] × unit_cost + connection_cost)
```

**Pros:**
- ✅ Optimizes network layout
- ✅ Identifies best routes for new pipes

**Cons:**
- ❌ Computationally intensive (many binary variables)
- ❌ May need geographic constraints (GIS integration)

---

## 5. YAML Configuration Design

### 5.1 Extended Configuration Structure

```yaml
# configs/systems/stadtbach_with_network.system.yaml

# Existing components (unchanged)
heat_pumps:
  - id: HP1
    location: central_plant  # NEW: spatial reference
    wrg_source_column: WRG1_T_K
    investment:
      enabled: true
      capacity_min_mw: 5.0
      capacity_max_mw: 100.0

generators:
  hkw:
    enabled: true
    location: central_plant  # NEW: spatial reference
    cap_th_mw: 75.0

# NEW: Network definition
thermal_network:
  enabled: true
  topology_file: networks/stadtbach_network.yaml

  parameters:
    supply_temperature_c: 90
    return_temperature_c: 50
    ambient_temperature_c: 10
    min_node_pressure_bar: 2.0
    max_node_pressure_bar: 10.0
    max_flow_velocity_m_s: 2.5  # Prevents erosion

  pipe_catalog:
    DN50:
      diameter_mm: 50
      capex_eur_per_m: 400
      u_value_w_per_m_k: 0.35  # Standard insulation
      u_value_enhanced_w_per_m_k: 0.20
      enhancement_cost_eur_per_m: 100

    DN100:
      diameter_mm: 100
      capex_eur_per_m: 650
      u_value_w_per_m_k: 0.30
      max_pressure_bar: 16

  pump_catalog:
    standard:
      capex_eur_per_kw: 500
      efficiency: 0.75
      lifetime_years: 15
```

### 5.2 Network Topology File

```yaml
# configs/networks/stadtbach_network.yaml
nodes:
  - id: central_plant
    type: source
    coordinates: {x: 0, y: 0}
    components:
      - HP1
      - HP2
      - HP3
      - HP4
      - hkw
      - ava

  - id: junction_north
    type: junction
    coordinates: {x: 800, y: 600}

  - id: consumer_zone_a
    type: consumer
    coordinates: {x: 1500, y: 800}
    demand_column: demand_zone_a  # From Import_Data.xlsx

  - id: consumer_zone_b
    type: consumer
    coordinates: {x: 2200, y: 400}
    demand_column: demand_zone_b

pipes:
  - id: main_north
    from: central_plant
    to: junction_north
    length_m: 1000
    diameter_options: [DN150, DN200, DN250]
    existing: false  # New pipe to be optimized

  - id: to_zone_a
    from: junction_north
    to: consumer_zone_a
    length_m: 750
    diameter_options: [DN100, DN150]
    existing: true  # Brownfield: existing pipe
    current_diameter: DN100  # Can be upgraded

pumps:
  - id: main_pump
    location: central_plant
    investment:
      enabled: true
      max_head_m: 100
      max_flow_m3_h: 500
```

---

## 6. Implementation Roadmap

### Phase 1: Basic Pipe Modeling (3-4 months)

**Scope:** Add linear pipe components without full hydraulics

**Deliverables:**
1. **PipeComponent class** (`energis/models/blocks/pipe.py`)
   - Variables: flow[t], diameter (discrete choice)
   - Simplified pressure drop (linear in flow)
   - Heat loss (fixed percentage or temperature-based)

2. **NodeComponent enhancement** to Bus
   - Add spatial coordinates
   - Track supply/return temperatures

3. **YAML network configuration**
   - Define nodes, pipes, pumps
   - Pipe catalog with costs and properties

4. **Test case: Stadtbach with 2-3 consumer zones**
   - Split aggregated demand into spatial zones
   - Optimize pipe diameters for existing routes

**Key Constraints:**
```python
# Energy balance at nodes (heat)
sum(Q_in[pipes_to_node]) = demand[node] + sum(Q_out[pipes_from_node])

# Simplified pressure drop
ΔP[pipe, t] = K_pipe × flow[pipe, t]  # Linear approximation

# Pipe diameter selection
CAPEX_pipe = length × cost[diameter]
```

**Success Criteria:**
- ✅ Model solves within 2× current runtime
- ✅ Pipe CAPEX correctly minimized
- ✅ Heat losses reduce with better insulation investment

---

### Phase 2: Hydraulic Constraints (4-6 months)

**Scope:** Add pressure/flow limits and pump optimization

**Deliverables:**
1. **Pressure balance constraints**
   - Node pressure variables
   - Kirchhoff loop constraints
   - Min/max pressure limits

2. **PumpComponent** (`energis/models/blocks/pump.py`)
   - Pressure boost variables
   - Electricity consumption
   - Investment optimization

3. **Piecewise linear pressure drop**
   - Replace linear approximation
   - 3-5 segment piecewise model
   - Better accuracy at varying flows

4. **Flow velocity constraints**
   - Max velocity limits (erosion prevention)
   - Min velocity (settling prevention)

**Key Constraints:**
```python
# Pressure balance
P[node, t] = P[source] - sum(ΔP_pipes) + sum(ΔP_pumps)

# Pressure limits
P_min ≤ P[node, t] ≤ P_max

# Pump power
P_el_pump[t] = (flow[t] × ΔP[t]) / (ρ × η)

# Velocity limits
v_min ≤ (4 × flow[t]) / (π × D² × ρ) ≤ v_max
```

**Test Cases:**
- Stadtbach with varied demand profiles → pump sizing
- Long-distance pipeline case → pressure booster stations

**Success Criteria:**
- ✅ Pumps placed optimally to meet pressure requirements
- ✅ Electricity consumption for pumping minimized
- ✅ No pressure violations under peak demand

---

### Phase 3: Advanced Thermo-Hydraulics (6-8 months)

**Scope:** Temperature propagation, return line modeling

**Deliverables:**
1. **Supply/Return line separation**
   - Separate pipes for supply and return
   - Different temperature levels
   - Asymmetric heat losses

2. **Temperature propagation**
   - Node temperature variables
   - Heat loss as function of (T_supply - T_ambient)
   - Consumer heat exchanger ΔT

3. **Variable supply temperature optimization**
   - Lower temps → less heat loss
   - Higher temps → smaller diameter needs
   - Trade-off optimization

4. **Seasonal ground temperature**
   - Time-varying T_ambient for buried pipes
   - Winter vs. summer heat losses

**Key Constraints:**
```python
# Temperature drop in pipe
T_out[pipe, t] = T_in[pipe, t] - (Q_loss[pipe, t] / (ṁ[pipe, t] × c_p))

# Heat loss
Q_loss[pipe, t] = U × length × (T_avg[pipe, t] - T_ground[t])

# Consumer heat exchanger
Q_delivered[node, t] = ṁ[node, t] × c_p × (T_supply[node, t] - T_return[node, t])
T_return_min ≤ T_return[node, t] ≤ T_return_max
```

**Test Cases:**
- Long-distance network (5+ km) → significant temp losses
- Low-temperature district heating (LT-DH) scenarios

**Success Criteria:**
- ✅ Temperature losses accurately modeled
- ✅ Supply temp optimization reduces overall costs
- ✅ Return temperature stays within bounds

---

### Phase 4: Topology Optimization (Optional, 8-12 months)

**Scope:** Greenfield network layout optimization

**Deliverables:**
1. **Binary pipe build decisions**
   - Choose which pipes to construct
   - Minimize total CAPEX + OPEX

2. **GIS integration**
   - Import building locations
   - Street network constraints
   - Avoid obstacles (rivers, highways)

3. **Clustering algorithms**
   - Pre-process to reduce problem size
   - Group nearby consumers
   - Generate candidate pipe routes

4. **Multi-period expansion planning**
   - Stage construction over years
   - Demand growth scenarios

**Computational Considerations:**
- Large networks (100+ nodes) may need decomposition
- Heuristics for initial topology generation
- Branch-and-cut acceleration

---

## 7. Technical Recommendations

### 7.1 Linearization Best Practices

**Pressure Drop:**
- Use piecewise linear with 4-5 segments for flows
- Validate against TESPy for key operating points
- Conservative overestimation acceptable for design phase

**Temperature Losses:**
- Start with fixed percentage (Phase 1)
- Upgrade to temperature-dependent (Phase 3)
- Time-varying ambient temperature from weather data

**Pump Efficiency:**
- Use fixed efficiency (0.75) initially
- Can add part-load efficiency curves later (piecewise)

### 7.2 Computational Performance

**Expected Model Size (Stadtbach with 10 nodes, 15 pipes):**
- Continuous variables: ~50,000 (for 8760 hours)
- Binary variables: ~500 (pipe diameters, pumps, existing binaries)
- Constraints: ~100,000
- **Expected solve time:** 5-15 minutes (vs. current 2-5 min)

**Scaling Strategies:**
- Use rolling horizon for operational optimization
- Perfect forecast for design decisions (annual aggregation)
- Temporal clustering: representative weeks instead of full year

### 7.3 Validation Approach

**Three-Level Validation:**

1. **Unit Tests:**
   - Single pipe with known properties
   - Compare ΔP, Q_loss to analytical formulas

2. **Component Tests:**
   - Small network (2-3 nodes) vs. TESPy
   - Verify pressure/temperature within 5%

3. **System Tests:**
   - Stadtbach network vs. existing data
   - Total energy consumption match
   - Peak flow/pressure comparisons

### 7.4 Data Requirements

**New Input Data Needed:**

1. **Network Geometry:**
   - Pipe routes (GIS data or manual definition)
   - Pipe lengths, elevations
   - Existing infrastructure (diameters, age)

2. **Spatial Demand:**
   - Breakdown of aggregated demand by zone/building
   - Hourly profiles per consumer node

3. **Pipe Properties:**
   - Catalog of available diameters (DN50-DN400)
   - Cost per meter (CAPEX)
   - U-values for insulation options
   - Pressure ratings

4. **Ground/Ambient Conditions:**
   - Soil temperature profile (if buried)
   - Ambient air temperature (if above ground)

**Data Sources:**
- Municipal GIS systems
- Pipe manufacturer catalogs (e.g., Logstor, isoplus)
- Existing network documentation (Stadtbach case)

---

## 8. Limitations and Trade-offs

### 8.1 Linearization Approximations

**What We Lose:**
- ❌ Exact pressure drop (quadratic in flow) → piecewise linear approximation
- ❌ Temperature-dependent viscosity effects
- ❌ Transient thermal dynamics (thermal inertia of pipes)
- ❌ Complex fluid property variations

**Mitigation:**
- Use conservative coefficients (slightly overestimate pressure drop)
- Validate with TESPy for critical cases
- Add safety margins in design (10-15% oversizing)

### 8.2 Computational Complexity

**Scaling Limits:**
- Networks with 100+ nodes may need decomposition
- Topology optimization (greenfield) is NP-hard
- Trade-off: accuracy vs. solve time

**Mitigation:**
- Hierarchical decomposition (main trunk → branches)
- Pre-screening of candidate topologies
- Use rolling horizon for operations, aggregated time for design

### 8.3 Model Fidelity vs. Planning Horizon

| Planning Level | Model Detail | Solve Time | Best Approach |
|---------------|--------------|------------|---------------|
| Strategic (20-year) | Low | Minutes | Aggregated zones, annual energy |
| Tactical (1-year) | Medium | 10-30 min | Hourly, simplified hydraulics |
| Operational (1-week) | High | Minutes | Hourly, detailed constraints |

**Recommendation:** Match model complexity to planning horizon.

---

## 9. Comparison to Existing Tools

| Feature | EnerGIS (Current) | + Pipe Model (Proposed) | TESPy | PyPSA |
|---------|-------------------|-------------------------|-------|-------|
| **Optimization** | ✅ MILP | ✅ MILP | ❌ Simulation only | ✅ MILP |
| **Investment Planning** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Pipe Network** | ❌ No | ✅ Yes (linear) | ✅ Yes (detailed) | ⚠️ Abstract |
| **Pressure Constraints** | ❌ No | ✅ Yes | ✅ Yes | ❌ No |
| **Temperature Losses** | ⚠️ Bus loss factor | ✅ Pipe-specific | ✅ Detailed | ⚠️ Link efficiency |
| **Solve Time (annual)** | 2-5 min | 10-30 min* | N/A | 5-15 min |
| **Brownfield Support** | ✅ Yes | ✅ Enhanced | ⚠️ Manual | ✅ Yes |

*Estimated for Stadtbach-scale network (10-20 nodes)

**Key Insight:** Proposed approach fills the gap between "no network" (current) and "detailed simulation" (TESPy).

---

## 10. Development Plan Summary

### Phase 1: Foundation (Months 1-4)
- **Goal:** Add basic pipe components with linear constraints
- **Effort:** 1 developer, 3-4 months
- **Milestone:** Stadtbach with 3 consumer zones, optimized pipe diameters

### Phase 2: Hydraulics (Months 5-10)
- **Goal:** Pressure/flow constraints, pump optimization
- **Effort:** 1 developer, 4-6 months
- **Milestone:** Pump placement optimized, pressure limits enforced

### Phase 3: Thermal Refinement (Months 11-18)
- **Goal:** Supply/return separation, temperature optimization
- **Effort:** 1 developer, 6-8 months (parallel with operations)
- **Milestone:** Variable supply temperature reduces OPEX

### Phase 4: Advanced Features (Months 19-30, Optional)
- **Goal:** Topology optimization, GIS integration
- **Effort:** 1-2 developers, 8-12 months
- **Milestone:** Greenfield network layout optimization

---

## 11. Immediate Next Steps

### Step 1: Stadtbach Network Definition (Week 1-2)
1. Obtain spatial demand breakdown (if available)
   - Alternative: Synthetically split aggregated demand into 3-5 zones
2. Define network topology YAML for Stadtbach
   - Identify 3-5 consumer clusters
   - Estimate pipe lengths from GIS or approximations
3. Research pipe costs and properties
   - German/European pipe manufacturers
   - Standard diameter catalog

### Step 2: Prototype Pipe Component (Week 3-6)
1. Create `energis/models/blocks/pipe.py`
   - Attach method: flow variables, diameter choices
   - Simple linear pressure drop
   - Heat loss as percentage
2. Unit tests with single pipe
3. Integrate with system_builder.py

### Step 3: Simple Test Case (Week 7-8)
1. 3-node system: 1 source, 1 junction, 1 consumer
2. 2 pipes, 1 pump
3. Verify:
   - Energy balance holds
   - Diameter selection minimizes CAPEX
   - Model solves quickly (<1 min)

### Step 4: Extended Stadtbach Case (Week 9-12)
1. Full network with 5-10 nodes
2. Multiple consumer zones
3. Optimize:
   - Heat pump capacities (existing functionality)
   - Pipe diameters (new)
   - Pump sizing (new)
4. Compare to baseline (current bus model)

---

## 12. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Solve time explosion | Medium | High | Temporal aggregation, decomposition |
| Linearization inaccuracy | Medium | Medium | Validation with TESPy, safety margins |
| Data unavailability (Stadtbach network) | High | Medium | Synthetic data generation, assumptions |
| Integration complexity | Low | High | Phased approach, extensive testing |
| User adoption (YAML complexity) | Medium | Low | Good documentation, examples |

---

## 13. Success Metrics

### Technical Metrics:
- ✅ Model solves within 3× current runtime
- ✅ Pressure constraints satisfied at all nodes
- ✅ Temperature losses within 5% of TESPy validation
- ✅ CAPEX predictions within 10% of industry benchmarks

### Business Metrics:
- ✅ Enables brownfield network upgrade analysis
- ✅ Identifies optimal pipe routes for greenfield projects
- ✅ Reduces total system cost (CAPEX + OPEX) by 5-15% through better pipe sizing

---

## 14. Conclusion

**Recommended Path Forward:**
1. ✅ **Implement native MILP pipe modeling** (Option B) as core approach
2. ✅ **Start with Phase 1** (basic pipes) to prove concept on Stadtbach
3. ✅ **Use TESPy for validation** (hybrid approach) but not in optimization loop
4. ✅ **Extend YAML configuration** for network topology
5. ✅ **Phased rollout** to manage complexity and risk

**Expected Timeline:** 12-18 months for Phases 1-3 (full thermo-hydraulic capability)

**Key Differentiator:** EnerGIS will bridge the gap between abstract network models (PyPSA) and detailed simulation (TESPy) by providing **optimization-ready thermal-hydraulic modeling** for district heating planning.

---

## References

### Academic Literature
- [Mathematical modelling and model validation of the heat losses in district heating networks](https://www.sciencedirect.com/science/article/abs/pii/S0360544222033461)
- [Frontiers | A Review of District Heating Systems: Modeling and Optimization](https://www.frontiersin.org/articles/10.3389/fbuil.2016.00022/full)
- [Integral techno-economic design & operational optimization for district heating networks with a Mixed Integer Linear Programming strategy](https://www.sciencedirect.com/science/article/abs/pii/S0360544224024848)
- [Benchmark of mixed-integer linear programming formulations for district heating network design](https://ideas.repec.org/a/eee/energy/v308y2024ics0360544224026598.html)

### Software Frameworks
- [TESPy - Thermal Engineering Systems in Python](https://github.com/oemof/tespy)
- [PyPSA - Python for Power System Analysis](https://pypsa.org/)
- [oemof.DHNx - District Heating Networks](https://oemof.org/libraries/)
- [Combining oemof-solph and TESPy](https://oemof.github.io/heat-pump-tutorial/model/solph-with-tespy.html)

### Technical Resources
- [Open Source District Heating Modeling Tools—A Comparative Study](https://www.mdpi.com/1996-1073/15/21/8277)
- [TESPy District Heating Network Tutorial](https://tespy.readthedocs.io/en/main/basics/district_heating.html)

---

**Document Version:** 1.0
**Author:** EnerGIS Development Team
**Next Review:** After Phase 1 Prototype Completion
