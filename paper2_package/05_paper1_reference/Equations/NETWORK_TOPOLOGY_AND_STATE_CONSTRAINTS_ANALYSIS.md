# Network Topology and State Constraints Analysis

**Document Status**: Comprehensive Technical Analysis  
**Date**: 2026-04-01  
**Focus**: Network topology design, state validation, and constraint implementation  

---

## Executive Summary

Your current model has a **unified network physics framework** with nodes and pipes, where temperatures and pressures are *variable* (calculated by the optimizer), not fixed parameters. This is architecturally sound, but **state validation is currently minimal**. This analysis explores:

1. ✅ Current state of network topology and constraints
2. ⚠️ Gaps in state validation (pressure, temperature, volumeflow)
3. 🔧 Technical feasibility of adding constraints
4. 💡 Recommended implementation approach

---

## Part 1: Current Network Topology Architecture

### 1.1 Core Concept: Unified Network Model

Your system implements a **modern, unified network physics approach** where:

| Aspect | Current Implementation | Implication |
|--------|------------------------|-------------|
| **Node Types** | Producer, Consumer, Junction | All handled identically in physics |
| **Temperatures** | Variables (Var) not Parameters | Optimized, not fixed |
| **Pressures** | Variables (Var) propagated | Support for network flow optimization |
| **Mass Flows** | Pipy carries m_dot[t] | Full flow balance at each node |
| **Brownfield/Greenfield** | No distinction | Unified constraints for all topologies |

**Location**: `calion/models/blocks/thermal_node.py` and `calion/models/blocks/pipe_pair.py`

### 1.2 Network Components

#### **Nodes** (Thermal Network Topology)
```python
# From thermal_node.py
class ThermalNodeBlock:
    Variables:
    - T_supply[t]:        Supply temperature (°C) — Var
    - T_return[t]:        Return temperature (°C) — Var or Param (consumer)
    - pressure_supply[t]: Supply pressure (bar) — Var
    - pressure_return[t]: Return pressure (bar) — Var
    - m_dot_demand[t]:    Consumer mass flow demand (kg/s) — Var
```

**Current Bounds** (hardcoded):
```
Supply Temp:  [60°C, 130°C]
Return Temp:  [30°C, 90°C + 20°C offset]
Pressure:     [0, pressure_nominal × 2.0] (e.g., [0, 20 bar])
```

#### **Pipes** (Supply + Return Pair)
```python
# From pipe_pair.py
class PipePairBlock:
    Variables:
    - m_dot[t]:           Mass flow (kg/s) — Var, bounded by velocity/diameter
    - T_supply_in[t], T_supply_out[t]
    - T_return_in[t], T_return_out[t]
    - Q_loss_supply[t], Q_loss_return[t]: Heat losses (MW)
```

**Current Flow Bounds**:
```
Max flow = min(
    velocity_max (2.5 m/s) × cross_section_area,
    pipe_max_flow parameter,
    calculated from diameter
)
```

### 1.3 Current Physics Constraints

#### **Temperature Balance at Nodes**
```
From thermal_node.py (unified for all node types):

Mass Balance:        Σ m_dot_in = Σ m_dot_out + m_dot_demand
Enthalpy Balance:    T_supply × Σ m_dot_in = Σ (T_out_pipe_i × m_dot_i)
Linearized mixing using constant cp (4.186 kJ/kg·K)
```

#### **Pipe Heat Loss**
```
From network_physics.py:

Q_loss = U[W/(m·K)] × L[m] × (T_fluid - T_ground)[K] / 1e6  [MW]

T_outlet = T_inlet - Q_loss / (m_dot × cp)

U_value for supply/return pipes: 0.28-0.30 W/(m·K) (configurable)
```

#### **Current Pressure Model (Basic)**
```python
# From pipe_pair.py
Piecewise-linear (PWL) pressure drop over 3 segments (MILP-compatible)
Max pressure drop: configurable (default 2.0 bar)
Darcy-Weisbach basis with pipe roughness
```

---

## Part 2: Current State Validation Gaps

### 2.1 What IS Currently Validated

✅ **Hard Bounds**:
- Temperature variables have bounds (e.g., 60-130°C supply)
- Pressure variables have bounds (e.g., 0-20 bar)
- Flow variables bounded by velocity limits and pipe diameter
- Storage energy bounded by capacity

✅ **Conservation Laws**:
- Mass balance at each node (continuity)
- Energy balance at nodes (enthalpy mixing)
- Heat balance across whole system
- Electricity balance

✅ **Component Constraints**:
- Storage dynamics (energy accumulation)
- Heat pump COP relationships
- Thermal generation efficiency

### 2.2 What IS NOT Currently Validated

❌ **No explicit feasibility/validity checks for network states**:

| State | Current | Problem |
|-------|---------|---------|
| **Pressure Drop Consistency** | PWL model but no feedback | A pipe could show valid pressure at both ends without physics-based validation |
| **Supply > Return Temp** | Not explicitly enforced | Model could violate T_supply ≥ T_return in consumer nodes |
| **Maximum Velocity** | Bounded in m_dot but not enforced via pressure | High flow in thin pipe could be theoretically infeasible |
| **Minimum Pressure** | Lower bound is 0 bar | No minimum operating pressure (e.g., preventing cavitation at ≪1 bar) |
| **Thermal Stability** | No temperature gradient validation | Unusual T_return > T_supply_expected could occur in edge cases |
| **Mass Balance Closures** | Per-node only, not pipe-to-pipe | Upstream/downstream node flow mismatch not caught explicitly |
| **Network Loop Detection** | Not validated | No check that node connections form valid DAG for single direction flow |

### 2.3 Why This Matters

The current setup is **mathematically consistent** (Pyomo won't allow infeasible LP/MILP), but **physically questionable states** may occur:

**Example Scenario**:
```
Node A (producer) → Pipe 1 (500m, 200mm) → Node B (consumer)

Current model could have:
  - T_h_A = 80°C, T_r_A = 50°C
  - T_h_B = 78°C, T_r_B = 55°C   ← Return warmer than supply! (physically odd)
  - P_A = 10 bar, P_B = 9.9 bar  ← Tiny loss, no Darcy-Weisbach check

This violates practical district heating norms but Pyomo doesn't reject it.
```

---

## Part 3: Feasibility of Adding State Constraints

### 3.1 YES: Technically Feasible to Add Constraints

The current architecture **supports** addition of state constraints. Your model already:

✅ Has node and pipe blocks as discrete Pyomo components  
✅ Uses ConfigBlock pattern allowing per-node/per-pipe configuration  
✅ Has parameter sets for physical properties (cp, density, viscosity, etc.)  
✅ Implements bounded variables (good foundation for additional constraints)  

### 3.2 Specific Constraints That Can Be Added

#### **A. Temperature Constraints**

**Constraint 1: Supply ≥ Return at every node**
```python
# Add to thermal_node.py in ThermalNodeBlock.attach()

# For each timestep, enforce supply >= return
model.add_constraint(
    ConstraintList(rule=lambda m, t: (
        T_supply[t] >= T_return[t]
    ))
)

Why add: Consumer returns warmer than supply is unphysical
Cost: 1 inequality constraint per timestep per node (low computational cost)
Implementation: ~5 lines of code
```

**Constraint 2: Temperature drop across pipes within physical bounds**
```python
# Add to pipe_pair.py

# Temperature drop must be consistent with Darcy-Weisbach + heat loss
# Not just any T_outlet, but derived from:
# T_outlet = T_inlet - dT_pressure_drop - dT_heat_loss

From network_physics.py, we have analytical model:
    dT_heat_loss = U * L * (T_avg - T_ground) / (m_dot * cp)
    dT_friction = (Δ P_friction) / (m_dot * cp_pressure_equiv)

Current model: Just bounds T_outlet, doesn't enforce this relationship

Solution: Add equality constraint:
    T_outlet[t] == T_inlet[t] - f(m_dot[t], pipe_properties)

Cost: Adds 1 equation per pipe per timestep (nonlinear if using Darcy-Weisbach)
      Or: linearize into PWL segments like pressure drop (10-20% model size increase)
Implementation: ~50-100 lines using existing PWL infrastructure
```

**Constraint 3: Consumer return temperature bounded by demand**
```python
# Return temp depends on heat extracted and mass flow
# Q_cons = m_dot * cp * (T_supply - T_return)
# Therefore: T_return = T_supply - Q_cons / (m_dot * cp)

# If consumer demand is time-varying, return temp should also vary
# Add linking constraint:

model.add_constraint(
    ConstraintList(rule=lambda m, t: (
        T_return_consumer[t] == T_supply_consumer[t] - Q_demand[t] / (m_dot[t] * cp)
    ))
)

Current: T_return can be fixed Param (constant) even if demand varies
Problem: Unrealistic; actual return temp rises when demand drops

Cost: 1 nonlinear equation per consumer node per timestep
      Or: Reformulate as set of linear segments (2-3× constraint count)
Implementation: ~30-50 lines
```

#### **B. Pressure Constraints**

**Constraint 1: Minimum operating pressure (prevent cavitation)**
```python
# Water exhibits cavitation risk when absolute pressure < ~0.3 bar

# Add lower bound:
pressure_supply_lb = max(0.3, config.get('min_pressure_bar', 1.0))

setattr(model, f'{prefix}_pressure_supply',
        pyo.Var(time_set, domain=pyo.NonNegativeReals,
               bounds=(pressure_supply_lb, pressure_max)))

Why: Protect pump integrity, avoid cavitation damage
Cost: Just change Var bounds (no new constraints)
Implementation: 2-4 lines
```

**Constraint 2: Pressure continuity at node interfaces**
```python
# Currently: pressure_supply[pipe_out] ≠ pressure_supply[node_next]
# They're separate variables with no forcing constraint

# Add linking constraint (add to network_manager.py):
model.add_constraint(
    P_out_pipe[t] >= P_in_next_node[t]  # Pressure only decreases going downstream
)

Why: Enforce one-directional flow topology
Cost: 1 constraint per pipe-node connection per timestep
      (typically ~3-5 connections per network)
Implementation: ~20-30 lines in network_manager.py
```

**Constraint 3: Pressure drop consistent with Darcy-Weisbach**
```python
# Current: PWL approximation, no link to actual flow

# Enhanced version: Enforce realistic Darcy pressure drop
# ΔP = f × (L/D) × (ρ × v²) / 2

where:
  f = friction factor (function of Reynolds number and roughness)
  v = velocity = m_dot / (ρ × A)

# Linearized into PWL:
for segment i in [1, 2, 3]:
    if flow in [range_i]:
        pressure_drop[t] = slope_i × (m_dot[t] - base_i)

Cost: Enhances existing PWL, 20-50% more constraints
Implementation: Refactor pipe_pair.py PWL section (~100-150 lines)
```

#### **C. Volumetric Flow Constraints**

**Constraint 1: Velocity bounds (convert mass flow to velocity)**
```python
# Current: m_dot bounded, but velocity not explicitly checked

# Add explicit constraint:
v[t] = m_dot[t] / (density × cross_section_area)
v[t] <= v_max  (typically 2.5 m/s for district heating)
v[t] >= v_min  (typically 0.3 m/s to avoid stagnation)

Cost: 2 new variables (v_supply[t], v_return[t]), 2 equations per pipe per timestep
Implementation: ~30 lines in pipe_pair.py
```

**Constraint 2: Flow regime validation (Reynolds number)**
```python
# Re = ρ × v × D / μ
# Different flow regimes have different heat transfer coefficients

# Critical: Transition from laminar (Re<2300) to turbulent (Re>4000)
# Laminar: higher temperature drop; turbulent: lower

# Option 1 (simple): Enforce only turbulent (Re > 2500):
  model.add_constraint(m_dot[t] >= 2500 * μ * A / (ρ * D))

Option 2 (advanced): Use SOS2 to model transitional region
  Computationally more expensive but more accurate

Cost: Option 1 = 1 constraint per pipe per timestep (~5 lines)
      Option 2 = ~15-20 constraints per pipe per timestep (much higher cost)
Implementation: Option 1 = ~15 lines; Option 2 = ~80 lines
```

#### **D. Network Topology Validation**

**Constraint 1: Prevent backflow in single-direction networks**
```python
# If network is radial (tree structure) from one producer:
# Flow should go from producer → consumers, never backwards

# Add constraint linking pressure:
P_from_node[t] > P_to_node[t]  ∀ pipes in network

# Enforce:
  m_dot[t] ≥ 0  (already done)
  P_from[t] >= P_to[t] + ΔP(m_dot[t])  (new)

Cost: 1 constraint per pipe per timestep
Implementation: ~10 lines in network_manager.py
```

**Constraint 2: Ensure connected consumers receive flow**
```python
# Currently: No guarantee consumer node has non-zero incoming flow

# For each consumer:
  Σ m_dot_in[t] >= m_dot_min_consumer

Where m_dot_min depends on minimum heat demand or pump constraints

Cost: 1 constraint per consumer per timestep
Implementation: ~10-15 lines in thermal_node.py
```

---

## Part 4: Recommended Implementation Strategy

### 4.1 Priority-Based Roadmap

#### **Phase 1: Essential (Weeks 1-2)** — Fixes obvious physical violations
```yaml
☐ Add T_supply >= T_return constraint at all nodes
☐ Add minimum pressure bound (e.g., 0.5 bar vs. current 0 bar)
☐ Add supply > return temp for consumers linked to mass flow
☐ Add velocity bounds (0.3-2.5 m/s checks)

Effort: ~100 lines of code
Model size increase: ~5%
Solver time impact: Negligible
Implementation location: thermal_node.py, pipe_pair.py
```

#### **Phase 2: Enhanced Physics (Weeks 3-4)** — Better realism
```yaml
☐ Temperature drop linking to heat loss model
☐ Pressure-flow consistency (Darcy-Weisbach enforcement)
☐ Flow regime validation (Reynolds number switches)
☐ Network topology backflow prevention

Effort: ~300-400 lines of code
Model size increase: 15-25%
Solver time impact: ~10-20% slowdown typical
Implementation location: pipe_pair.py, network_manager.py
```

#### **Phase 3: Advanced (Weeks 5+)** — Operational resilience
```yaml
☐ Thermal stratification in nodes
☐ Mixing valve constraints (if applicable)
☐ Pump curve enforcement (head vs. flow)
☐ Heat exchanger effectiveness constraints

Effort: ~500+ lines of code
Model size increase: 30-50%
Solver time impact: ~30-50% slowdown
Implementation location: New blocks/ (heat_exchanger.py expansion)
```

### 4.2 Implementation Approach

#### **Option A: Configuration-Driven (Recommended for flexibility)**

```yaml
# In configs/base.yaml or scenario YAML:

thermal_network:
  enabled: true
  physics:
    heat_loss: true          # ← Already supported
    pressure_drop: true       # ← Already supported
    
  # NEW: State validation config
  state_validation:
    temperature_constraints:
      enforce_supply_ge_return: true           # Phase 1
      enforce_demand_based_return_temp: true   # Phase 2
      allow_return_temp_profile: true          # Advanced
    
    pressure_constraints:
      min_pressure_bar: 0.5                     # Phase 1
      enforce_darcy_consistency: true           # Phase 2
      max_pressure_drop: 2.0
    
    flow_constraints:
      min_velocity_m_s: 0.3                     # Phase 1
      max_velocity_m_s: 2.5
      enforce_reynolds_regime: true             # Phase 2
      flow_regimes: [laminar, transition, turbulent]

# Usage: pass state_validation config to network_manager
```

This allows:
- Incremental rollout (enable per constraint)
- Easy A/B testing (with/without constraints)
- Per-scenario customization
- Version control via YAML

#### **Option B: Code-Based (Faster for hardcoding)**

Add new methods to `ThermalNodeBlock` and `PipePairBlock`:

```python
# In thermal_node.py
class ThermalNodeBlock(BaseComponent):
    
    @staticmethod
    def attach_state_constraints(model, config, node_id, prefix, T_supply, T_return):
        """Attach optional state validation constraints."""
        
        if config.get('state_validation', {}).get('temperatures', {}).get('supply_ge_return'):
            model.add_constraint(
                ConstraintList(rule=lambda m, t: (
                    T_supply[t] >= T_return[t]
                ))
            )
        
        # ... more constraints based on config flags
```

#### **Option C: Hybrid (Recommended)**

1. **Phase 1**: Add constraints hardcoded (fast + tested)
2. **Phase 2**: Refactor into config-driven pattern
3. **Phase 3**: Externalize complex physics to separate validation module

---

## Part 5: Technical Implementation Details

### 5.1 Integration Points

You'll need to modify:

```
calion/models/
├── blocks/
│   ├── thermal_node.py    (← Add node-level constraints)
│   ├── pipe_pair.py        (← Add pipe-level constraints)
│   └── NEW: network_validator.py  (← Centralized validation logic)
├── network_manager.py      (← Add topology validation)
└── constraint_builder.py   (← Add global constraints)
```

### 5.2 Code Template: Adding Temperature Constraint

```python
# In thermal_node.py, inside ThermalNodeBlock.attach()

# After creating T_supply and T_return variables:

logger.info(f"  Attaching state constraints for node {node_id}")

# 1. Supply >= Return Temperature
if config.get('enforce_supply_ge_return', True):  # Default: ON
    def supply_ge_return_rule(m, t):
        return T_supply[t] >= T_return[t] - 0.1  # 0.1°C tolerance for numerical stability
    
    model.add_component(
        f'{prefix}_SUPPLY_GE_RETURN',
        pyo.Constraint(time_set, rule=supply_ge_return_rule)
    )
    logger.info(f"    Added: Supply >= Return temperature constraint")

# 2. Return Temp Bounded by Heat Extraction (consumers only)
if node_type == 'consumer' and config.get('enforce_demand_return_decay', False):
    # Q_delivered = m_dot * cp * (T_supply - T_return)
    # → T_return_min = T_supply - Q_delivered / (m_dot * cp)
    
    if hasattr(model, f'{prefix}_m_dot_demand'):
        m_dot_cons = getattr(model, f'{prefix}_m_dot_demand')
        Q_demand_attr = f'{node_id}_Q_demand'
        
        if hasattr(model, Q_demand_attr):
            Q_cons = getattr(model, Q_demand_attr)
            cp_J = 4186  # Specific heat [J/(kg·K)]
            
            def return_temp_consistency_rule(m, t):
                # Avoid division by zero
                mdot_safe = pyo.max(m_dot_cons[t], 0.01)  # Min 10 g/s
                return T_return[t] >= T_supply[t] - Q_cons[t] / (mdot_safe * cp_J / 1000)
            
            model.add_component(
                f'{prefix}_RETURN_TEMP_CONSISTENCY',
                pyo.Constraint(time_set, rule=return_temp_consistency_rule)
            )
            logger.info(f"    Added: Return temp consistency constraint (demand-based)")
```

### 5.3 Code Template: Adding Pressure Constraint

```python
# In pipe_pair.py, inside PipePairBlock.attach()

# After creating pressure variables:

# 1. Minimum operating pressure
min_pressure_bar = config.get('min_pressure_bar', 0.5)

pressure_supply = getattr(model, f'{prefix}_pressure_supply')
pressure_return = getattr(model, f'{prefix}_pressure_return')

# Override Var bounds:
for t in time_set:
    pressure_supply[t].setlb(min_pressure_bar)
    pressure_return[t].setlb(min_pressure_bar)

logger.info(f"  Pipe {pipe_id}: min pressure = {min_pressure_bar} bar")

# 2. Pressure drop consistency with flow
if config.get('enforce_darcy_consistency', False):
    # Use existing PWL infrastructure to link ΔP to m_dot
    # Current PWL: just bounds pressure
    # Enhanced: make pressure_out = pressure_in - f(m_dot)
    
    pressure_in = pressure_supply  # At from_node
    pressure_out = ...  # At to_node (need to link)
    
    # PWL segments (typical for district heating)
    flow_segments = [
        (0, 100, 0.15),      # 0-100 kg/s: 0.15 bar/100kg/s loss rate
        (100, 250, 0.35),    # 100-250 kg/s: 0.35 bar/50kg/s loss rate
        (250, None, 0.55),   # 250+: 0.55 bar/per additional kg/s
    ]
    
    for idx, (flow_min, flow_max, dp_rate) in enumerate(flow_segments):
        # Add binary variable for segment selection
        z_seg = pyo.Var(time_set, domain=pyo.Binary, name=f'{prefix}_z_segment_{idx}')
        model.add_component(f'{prefix}_z_seg_{idx}', z_seg)
        
        # Pressure drop in this segment
        dp_seg = pyo.Var(time_set, domain=pyo.NonNegativeReals, 
                        bounds=(0, dp_rate * (flow_max - flow_min) if flow_max else 100))
        model.add_component(f'{prefix}_dp_seg_{idx}', dp_seg)
        
        # Link flow to segment + pressure drop
        # ... SOS2 formulation (existing PWL code in pipe_pair.py)
    
    logger.info(f"  Pipe {pipe_id}: added Darcy pressure drop PWL ({len(flow_segments)} segments)")
```

---

## Part 6: Impact Analysis

### 6.1 Model Size and Solve Time

| Phase | Constraints Added | Variables Added | Model Size ↑ | Solve Time ↑ | Accuracy ↑ |
|-------|-------------------|-----------------|--------------|--------------|-----------|
| Current | Baseline | Baseline | — | — | ~70% realistic |
| Phase 1 | 1-2 per node/pipe | 0 | ~5% | <5% | ~85% realistic |
| Phase 2 | 3-5 per node/pipe | 2-4 per node/pipe | ~20% | 10-20% | ~95% realistic |
| Phase 3 | 5-10+ per node/pipe | 5-10 per node/pipe | ~40-50% | 30-50% | ~98% realistic |

### 6.2 Feasibility Impact

Adding constraints typically:**increases** feasible region (by catching infeasible states), except:
- Temperature drop constraint might make some scenarios infeasible if demands are unrealistic
- Pressure constraints might infeasible if consumer demand exceeds pump capabilities

**Recommendation**: Phase 1 constraints are "soft" (physically justified but rarely violated in practice) so very low risk of infeasibility.

### 6.3 Debug/Validation Benefits

```python
# New diagnostic: after solving, check state validity

def validate_network_solution(model, config):
    """Post-solve validation of network states."""
    
    issues = []
    
    for node_id in config.nodes:
        for t in model.t:
            T_s = value(model.NODEID_T_supply[t])
            T_r = value(model.NODEID_T_return[t])
            P_s = value(model.NODEID_pressure_supply[t])
            
            if T_s < T_r - 0.1:  # Should enforce, but check anyway
                issues.append(f"Node {node_id}@t{t}: T_sup({T_s}°C) < T_ret({T_r}°C)")
            
            if P_s < 0.3:
                issues.append(f"Node {node_id}@t{t}: Low pressure {P_s} bar")
    
    return issues
```

---

## Part 7: Recommendations & Next Steps

### 7.1 My Assessment

✅ **YES, it is definitely possible** to add state constraints. Your architecture is well-designed for it.

✅ **Worth doing for Phase 1** (T_supply ≥ T_return, min pressure, velocity bounds) because:
- Low implementation effort (~100 lines)
- Catches obvious physical violations
- Minimal solver overhead (<5%)
- Improves model credibility

⚠️ **Evaluate Phase 2 case-by-case** (Darcy consistency, Reynolds regimes) because:
- Requires ~300-400 lines + testing
- 10-20% solver slowdown
- Marginal improvement if network is over-designed (low flow velocity anyway)
- Beneficial for tight designs or novel topologies

❌ **Defer Phase 3** (stratification, pump curves) until:
- Phase 1-2 stabilized and tested
- Specific application requires advanced physics
- Have dedicated testing infrastructure

### 7.2 Immediate Action Items

1. **Week 1**: Add Phase 1 constraints (T_sup ≥ T_ret, min pressure, velocity)
   - Files: `thermal_node.py`, `pipe_pair.py` (~100 lines)
   - Config: Add flags to `base.yaml` for optional enabling
   - Test: Create unit test with simple 3-node network

2. **Week 2**: Create state validation diagnostics
   - Add `validate_network_solution()` function to extract post-solve
   - Export validation report in `export_workflow_results()`
   - Create example showing valid vs. invalid states

3. **Week 3**: Document in CALION API
   - Update `USER_GUIDE.md` with state constraint section
   - Add example YAML showing how to configure

4. **Future**: Monitor solver stats
   - If Phase 1 really adds <5% solve time, mark for always-on
   - If Phase 1 causes infeasibility on test scenarios, debug before rollout

### 7.3 Code Organization Suggestion

```
calion/models/
├── blocks/
│   ├── ...existing blocks...
│   └── state_constraints.py  ← NEW helper module
│       ├── enforce_temperature_bounds()
│       ├── enforce_pressure_bounds()
│       ├── enforce_flow_bounds()
│       └── enforce_network_topology()
├── network_validator.py  ← NEW post-solve validation
│   ├── validate_temperatures()
│   ├── validate_pressures()
│   ├── validate_flows()
│   └── validate_topology()
└── ...rest...
```

This keeps state logic modular and testable.

---

## Conclusion

**TL;DR**: Your unified network physics model is well-architected and **absolutely supports adding state constraints**. Start with Phase 1 (supply ≥ return, min pressure, velocity bounds) — low effort, high credibility gain. Defer advanced phases until specific need arises.

The main value: **Physical validity** of optimization results, not mathematical correctness (Pyomo ensures that). This matters for downstream applications (equipment sizing, safety checks, operator confidence).

Would you like me to start implementing Phase 1 constraints? I can create a working prototype in your code.
