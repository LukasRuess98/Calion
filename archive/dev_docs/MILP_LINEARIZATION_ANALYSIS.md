# MILP-Linearisierungscode Analyse – EnerGIS

Gründliche Analyse der Linearisierungsstrategien für bilineare Terme im MILP-Modus.

---

## 1. TEMPERATURE VARIABLES IN MILP MODE

### 1.1 pipe_pair.py (Lines 197–220)

**Code-Snippet:**
```python
milp_linearize = config.get('milp_linearize', False)

if milp_linearize:
    # Fix temperatures at nominal values → all T×m_dot products become linear
    T_supply_in = pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True)
    T_supply_out = pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True)
    T_return_in = pyo.Param(time_set, initialize=return_temp_nominal_c, mutable=True)
    T_return_out = pyo.Param(time_set, initialize=return_temp_nominal_c, mutable=True)
else:
    # Full nonlinear mode (requires QP/NLP solver)
    T_supply_in = pyo.Var(time_set, bounds=(supply_temp_min, supply_temp_max))
    T_supply_out = pyo.Var(time_set, bounds=(supply_temp_min, supply_temp_max))
    T_return_in = pyo.Var(time_set, bounds=(return_temp_min, return_temp_max))
    T_return_out = pyo.Var(time_set, bounds=(return_temp_min, return_temp_max))
```

**Bounds Definition (Lines 161–174):**
```python
supply_temp_nominal_c = config.get('supply_temp_nominal_c', 90.0)
return_temp_nominal_c = config.get('return_temp_nominal_c', 50.0)

supply_temp_min = min(60, supply_temp_nominal_c - 30)
supply_temp_max = max(130, supply_temp_nominal_c + 10)
return_temp_min = 30
return_temp_max = max(90, return_temp_nominal_c + 20)
```

**Issues Identified:**

| Problem | Severity | Impact |
|---------|----------|--------|
| Hardcoded fallback nominal (90/50°C) if not in config | **MEDIUM** | MILP params fixed at 90/50 if not specified → energy balance incorrect |
| Asymmetric bounds (min fixed, max depends on nominal) | **MEDIUM** | Return temp range [30, max(90, retnom+20)] may be too restrictive |
| supply_temp_max can be as low as 100°C (if nominal=90) | **MEDIUM** | For high-temp networks (>110°C), bounds too tight |

**Recommendations:**

```python
# IMPROVED VARIANT:
supply_temp_nominal_c = config.get('supply_temp_nominal_c', None)
if supply_temp_nominal_c is None:
    raise ValueError("supply_temp_nominal_c REQUIRED for MILP mode (configure globally or per-pipe)")

supply_temp_min = config.get('supply_temp_min_c', min(60, supply_temp_nominal_c - 30))
supply_temp_max = config.get('supply_temp_max_c', max(130, supply_temp_nominal_c + 10))
return_temp_min = config.get('return_temp_min_c', 30)
return_temp_max = config.get('return_temp_max_c', max(90, return_temp_nominal_c + 20))
```

---

### 1.2 thermal_node.py (Lines 140–160)

**Code-Snippet:**
```python
milp_linearize_temp = config.get('milp_linearize', False)

if milp_linearize_temp and node_type in ('consumer', 'junction'):
    setattr(model, f'{prefix}_T_supply',
            pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True))
else:
    setattr(model, f'{prefix}_T_supply',
            pyo.Var(time_set, bounds=(supply_temp_min, supply_temp_max)))
```

**Key Behavior:**
- **Producer nodes**: T_supply ALWAYS remains Var (no linearization)
- **Consumer/Junction nodes in MILP mode**: T_supply → Param (fixed)
- **Return temperature**: Can be Param (profile) OR Var (load-dependent) independently

**Issue: Inconsistent Treatment**
- Producer T_supply varies → can propagate different temps to pipes
- Consumer T_supply fixed → violates enthalpy balance if multiple incoming pipes!
- **Result:** Multi-pipe junctions with MILP mode are over-constrained or infeasible

---

## 2. HEAT LOSS CONSTRAINTS

### 2.1 MILP Linearization (pipe_pair.py, Lines 263–278)

**Heat Loss Formula (MILP):**
```python
def heat_loss_supply_rule_milp(m, t):
    T_avg = supply_temp_nominal_c  # FIXED NOMINAL
    return Q_loss_supply[t] == (u_value_supply * length_m * (T_avg - T_ground[t])) / 1e6

def heat_delivered_rule_milp(m, t):
    dT = supply_temp_nominal_c - return_temp_nominal_c
    return Q_delivered[t] * 1000 == m_dot[t] * cp_water * dT
```

**Analysis:**
- ✅ Both constraints are purely LINEAR (m_dot × constant)
- ✅ No bilinear products m_dot × T(t)
- ❌ **Heat loss ignores actual T_supply – assumes nominal always**  
  - Real loss: Q_loss ∝ (T(t) - T_ground(t)) can vary significantly
  - MILP approximation: Frozen at design point
  - **Error:** ~±20% when actual T_supply ≠ nominal

**What gets Linearized:**
- ❌ m_dot × T products → **ELIMINATED** (temp fixed)
- ✅ m_dot × constant → stays linear
- ✅ pressure drop (already PWL) → unchanged

---

### 2.2 Non-MILP Heat Loss (Lines 290–310)

**Heat Loss Formula (Non-MILP):**
```python
def heat_loss_supply_rule(m, t):
    T_avg = (T_supply_in[t] + T_supply_out[t]) / 2.0
    return Q_loss_supply[t] == (u_eff * length_m * (T_avg - T_ground[t])) / 1e6
```

**Temperature Drop (Bilinear):**
```python
def temp_drop_supply_rule(m, t):
    return m_dot[t] * cp_water * (T_supply_in[t] - T_supply_out[t]) == Q_loss_supply[t] * 1000
```

**Bilinear Products:**
- ❌ m_dot[t] × (T_in - T_out): **BILINEAR** – needs QP/NLP solver

---

## 3. MULTI-PIPE MIXING (TEMPERATURE)

### 3.1 MILP Mode – thermal_node.py (Lines 229–276)

**Code:**
```python
if incoming_pipes and not milp_linearize_temp:
    if len(incoming_pipes) == 1:
        # Single pipe: simple equality
        return T_supply[t] == T_pipe_out[t]
    else:
        # Multi-pipe: bilinear enthalpy balance
        def multi_temp_rule(m, t):
            total_m = sum(m_dot[p, t] for p in incoming_pipes)
            weighted_T = sum(m_dot[p, t] × T_out[p, t] for p in incoming_pipes)
            return T_supply[t] * total_m == weighted_T
```

**CRITICAL ISSUE: In MILP mode, the multi-pipe constraint is:**
```
NOT CREATED AT ALL! (if incoming_pipes and not milp_linearize_temp) → skipped
```

**Consequence:**
- ✅ Removes bilinear m_dot × T mixing
- ❌ **Node temperature unconstrained** if milp_linearize=True
- ❌ Consumer T_supply = Param (fixed nominal) → bypasses mixing entirely
- ⚠️ **Energy imbalance**: Pipe outlet temps unlinked to node supply temp

**No Replacement Constraint for Multi-Pipe MILP:**
```python
# MISSING: For MILP junctions with multiple inputs, should have:
# T_supply[t] == weighted average of T_in[t] (or fixed linear combination)
# But currently: NOTHING
```

---

### 3.2 Single-Pipe Case – Works Correctly

**Code:**
```python
if len(incoming_pipes) == 1:
    return T_supply[t] == pipe_T_out[t]  # Simple equality
```

✅ **Correct:** Temperature continuity maintained even in MILP mode.

---

## 4. HEAT DEMAND LINEARIZATION

### 4.1 thermal_node.py (Lines 308–330)

**MILP Mode (Terminal Consumer):**
```python
if milp_linearize and not outgoing_pipes:
    # SKIPPED ENTIRELY — demand enforced via Q_consumer == Q_demand elsewhere
    logger.info("... heat_demand constraint skipped (enforced via Q_consumer)")
```

**Issue: Logic Chain**
1. Transport delay: Q_consumer[t] = Q_delivered[t - τ]
2. Demand: Q_demand[t] must equal Q_consumer[t]  
3. **But:** No constraint linking m_dot_demand → Q_delivered
4. **Result:** Pipe flow m_dot[t] unconstrained by instantaneous demand

**MILP Mode (Passthrough Consumer):**
```python
def heat_demand_rule_milp(m, t):
    dT_nominal = supply_temp_nominal_c - return_temp_c
    return m_dot_demand[t] == Q_demand[t] * 1000 / (cp_water * dT_nominal)
```

✅ **Correct:** Linear relation m_dot_demand = f(Q_demand, nominal ΔT)

**Non-MILP Mode:**
```python
def heat_demand_rule(m, t):
    return Q_demand[t] * 1000 == m_dot_demand[t] * cp_water * (T_supply[t] - T_return[t])
```

❌ **Bilinear:** m_dot × (T_supply - T_return)

---

## 5. TRANSPORT DELAY – BIG-M LINEARIZATION

### 5.1 3-Bucket SOS2 Structure (pipe_pair.py, Lines 465–545)

**Binary Selector (Line 493):**
```python
z_delay[n, t] ∈ {0,1}  for n ∈ {0,1,2} (one bucket per timestep)
```

**Flow Bounds per Bucket (Lines 486–488):**
```
Bucket 0 (high):   m_dot ∈ [m_mid, m_max]     → τ₁ shortest
Bucket 1 (medium): m_dot ∈ [m_min, m_mid]     → τ₂ 
Bucket 2 (low):    m_dot ∈ [0, m_min]         → τ₃ longest
where: m_min = 0.1 × m_max, m_mid = (m_min + m_max) / 2
```

**Big-M Values:**
```python
M_FLOW_BIG = effective_max_flow * 1.1   # ← Reasonable, ~10% slack
M_Q = max_heat_delivered_mw             # ← Can be UNBOUNDED
```

**Linearization Constraints (Lines 523–543):**

| Constraint | Formula | Big-M Size | Issue |
|------------|---------|-----------|-------|
| Selector sum | Σz_delay[n,t] = 1 | — | ✅ SOS2 enforcement |
| Flow lower bound | m_dot[t] ≥ m_lower × z[n,t] | — | ✅ Correct |
| Flow upper bound | m_dot[t] ≤ m_upper + M_FLOW × (1-z[n,t]) | 1.1×M_max | ✅ Reasonable |
| w coupling (upper) | w[n,t] ≤ Q_delayed[t-τ] | — | ✅ Couples w to Q |
| w-z coupling | w[n,t] ≤ M_Q × z[n,t] | `max_heat_mw` | ⚠️ TOO LOOSE? |
| w coupling (lower) | w[n,t] ≥ Q_delayed[t-τ] - M_Q×(1-z[n,t]) | `max_heat_mw` | ⚠️ TOO LOOSE? |

### 5.2 M_Q Value Analysis

**Current:**
```python
max_heat_delivered_mw = max(effective_max_flow * cp_water * delta_t_nom / 1000 * 1.2, 100.0)
→ Can be 10x–100x flow-dependent!
```

**Issue:** If max_heat_delivered_mw >> actual Q values, Big-M constraints become weak:
- `w[n,t] ≤ M_Q × z[n,t]` nearly always satisfied for any z choice
- Solver has little incentive to select correct bucket
- Numerical instability

**Better:** Use tighter bounds
```python
M_Q = 1.1 * max(Q_delivered[t] for t in time_set)  # Tighter!
```

---

## 6. POTENTIAL PROBLEMS & CONFLICTS

### Problem 1: Empty/Missing Temperature Bounds

| Scenario | Issue | Consequence |
|----------|-------|-------------|
| Config missing `supply_temp_nominal_c` | Falls back to 90°C | Heat network with different nominal temp gets wrong bounds |
| Config missing `ground_temp_c` | Falls back to 10°C | Heat loss under/over-estimated |
| `supply_temp_max < supply_temp_min` | Logic error | Solver infeasible |

**Fix (show in Recommendations):** Require explicit bounds in config schema.

---

### Problem 2: Multi-Pipe Junction MILP Inconsistency

| Condition | Behavior | Impact |
|-----------|----------|--------|
| Single incoming pipe + MILP | T_supply = T_pipe_out (OK) | ✅ Correct |
| Multiple pipes + MILP | **No constraint** (missing!) | ❌ Temperature free, energy imbalance |
| Multiple pipes + non-MILP | Bilinear mixing | ✅ Correct (but needs QP solver) |

**Evidence (thermal_node.py line 229):**
```python
if incoming_pipes and not milp_linearize_temp:  # ← SKIPS mixing if milp_linearize=True!
```

---

### Problem 3: Terminal Consumer Demand Not Enforced

| Scenario | Status | Issue |
|----------|--------|-------|
| Terminal consumer + MILP | m_dot_demand constraint SKIPPED | ❌ Flow unconstrained by demand |
| Terminal consumer + delay | Q_consumer = Q_delivered[t-τ] | ✅ Delayed demand enforced|
| But pipe flow m_dot[t]? | **Unconstrained by Q_demand[t]** | ⚠️ Mass/energy inconsistency |

**Expected:** m_dot[t] should satisfy instantaneous energy balance OR be linked to future demand via delay.

---

### Problem 4: Big-M Bounds Too Large

**In transport delay** (w_delay coupling):
- M_Q can be 100+ MW
- Constraints like `w ≤ M_Q × z` become nearly vacuous
- Solver doesn't strongly prefer correct bucket selection

**Example:** If actual Q_max = 10 MW but M_Q = 100 MW:
- `w ≤ 100 × z`: allows w → 100 MW even if actual max = 10 MW
- Big-M becomes ineffective

---

### Problem 5: Inconsistent Return Temperature in MILP

**thermal_node.py (lines 155–170):**
```python
# Return temp can be:
# (a) Fixed Param (load-independent)
# (b) Var with load-dependent bounds (needs bilinear coupling!)
# (c) Var free (full optimization)
```

**In MILP with option (b):** Return temp load-dependence requires missing constraint.

---

## 7. CODE ISSUES SUMMARY TABLE

| File | Lines | Issue | Type | Severity |
|------|-------|-------|------|----------|
| pipe_pair.py | 166–174 | Hardcoded temp bounds fallback | Logic | MEDIUM |
| pipe_pair.py | 263–278 | Heat loss frozen at nominal T | Accuracy | MEDIUM |
| thermal_node.py | 140–160 | Producer T always Var, consumer Param | Inconsistency | HIGH |
| thermal_node.py | 229–276 | Multi-pipe mixing skipped in MILP | Missing constraint | HIGH |
| thermal_node.py | 308–330 | Terminal consumer m_dot unconstrained | Missing relation | MEDIUM |
| pipe_pair.py | 525–543 | M_Q too loose for Big-M constraints | Numerical | MEDIUM |
| thermal_node.py | 155–170 | Return temp load-dependence unlinked | Incomplete | LOW |

---

## 8. RECOMMENDED FIXES

### Fix 1: Require explicit temperature bounds

**File:** pipe_pair.py (line 166)

```python
# BEFORE:
supply_temp_nominal_c = config.get('supply_temp_nominal_c', 90.0)

# AFTER:
supply_temp_nominal_c = config.get('supply_temp_nominal_c', None)
if supply_temp_nominal_c is None:
    raise ValueError(
        f"Pipe {pipe_id}: MILP mode requires explicit 'supply_temp_nominal_c' "
        f"in config (must be ≠ default 90°C)"
    )
```

---

### Fix 2: Enforce linear temperature mixing for MILP multi-pipe junctions

**File:** thermal_node.py (lines 229–280)

```python
# BEFORE (MISSING CONSTRAINT IN MILP):
if incoming_pipes and not milp_linearize_temp:
    if len(incoming_pipes) > 1:
        # Bilinear mixing
        ...

# AFTER (ADD LINEAR MIXING FOR MILP):
if incoming_pipes:
    if len(incoming_pipes) == 1:
        def single_temp_rule(m, t):
            return T_supply[t] == T_pipe_out[t]
        setattr(model, f'{prefix}_temp_mixing', pyo.Constraint(time_set, rule=single_temp_rule))
    
    elif milp_linearize_temp:
        # MILP: Use flow-weighted average (LINEAR) instead of bilinear
        def linear_mix_rule(m, t):
            total_m = sum(m_dot[p, t] for p in incoming_pipes)
            # With fixed T nominal, mixing → simple average or use upstream node nominal
            weighted_T_avg = sum(
                (m_bounds[p][v] if isinstance(m_dot[p, t], pyo.Var) else m_dot[p, t]) * 
                supply_temp_nominal_c  # Use nominal from each connected node
                for p in incoming_pipes
            ) / len(incoming_pipes)  # Simple average in MILP
            return T_supply[t] == weighted_T_avg
        setattr(model, f'{prefix}_temp_mixing_milp', pyo.Constraint(time_set, rule=linear_mix_rule))
    
    else:
        # Non-MILP: Bilinear mixing
        ...
```

---

### Fix 3: Tighten Big-M for transport delay

**File:** pipe_pair.py (line 525)

```python
# BEFORE:
M_Q = max_heat_delivered_mw

# AFTER:
# Use actual maximum heat delivered across all timesteps + margin
Q_series = [pyo.value(Q_delivered[t]) if pyo.value(Q_delivered[t]) else 0 for t in time_set]
M_Q = max(Q_series) * 1.1 if Q_series else max_heat_delivered_mw
# Or better: set after solving once, then re-optimize with better M_Q
```

---

### Fix 4: Enforce terminal consumer demand via m_dot

**File:** thermal_node.py (line 320)

```python
# BEFORE (SKIPPED FOR TERMINAL CONSUMER):
if milp_linearize and not outgoing_pipes:
    logger.info("... heat_demand constraint skipped")

# AFTER (ENFORCE VIA DELAYED DELIVERY):
# Still skip m_dot_demand constraint, but add explicit linking:
# Q_consumer[t] = m_dot_avg × cp × ΔT_nominal
# where m_dot_avg is the flow that was injected τ timesteps ago

# In MILP pass-through: keep existing m_dot_demand constraint
# For terminal: m_dot follows last pipe, Q_consumer delayed by τ
```

---

## 9. VERIFICATION CHECKLIST

- [ ] Config has explicit `supply_temp_nominal_c`, `return_temp_nominal_c`
- [ ] Temperature bounds are realistic: `min < nominal < max`
- [ ] Single-pipe nodes work (equality linking)
- [ ] Multi-pipe nodes: check T_supply ≠ free variable
- [ ] Transport delay buckets: verify τ_steps increase from high→low flow
- [ ] Big-M check: M_Q > max(Q_delivered[t]) over all t
- [ ] No infeasibility at multi-pipe MILP junctions
- [ ] Heat demand satisfied (check Q_consumer vs Q_demand post-solve)

---

## 10. QUICK REFERENCE: MILP vs Non-MILP

| Aspect | MILP Mode | Non-MILP (QP/NLP) | Linearization Method |
|--------|-----------|------------------|----------------------|
| **Temps** | Fixed Param | Var (bounded) | Eliminate m_dot × T |
| **Heat loss** | Q = const × m_dot | Q = f(T_avg, m_dot) | Use nominal T |
| **Mixing** | ❌ MISSING | Bilinear | None (problematic) |
| **Demand** | m_dot = Q / ΔT_nom | m_dot × ΔT = Q | Use nominal ΔT |
| **Delay** | 3-bucket + Big-M | None (direct τ) | SOS2 + Big-M |
| **Pressure** | PWL (3-segment) | Darcy-Weisbach nonlinear | Already MILP |

