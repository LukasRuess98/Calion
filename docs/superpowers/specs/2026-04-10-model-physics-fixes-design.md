# Design Spec: Model Physics Fixes
**Date:** 2026-04-10
**Branch:** feature/refactoring-framework-cleanup
**Target journal:** Energy Conversion and Management

---

## Scope

Four targeted fixes to improve physical realism of the Calion district heating
optimization framework, motivated by a critical model review. LMTD approximation
and constant fluid properties are explicitly documented as accepted simplifications
(standard in district heating literature).

---

## Fix 1 — Distributed Pump Model (PWL, per Pipe)

### Problem
Pressure variables `pressure_supply[t]` and `pressure_return[t]` at nodes have
no physical link to the pipe pressure drops. The optimizer can set arbitrary
pressure values. Pump electricity consumption is absent from the cost model.

### Design

**New variable per pipe** (in `pipe_pair.py`):
```
P_pump[t] ∈ [0, P_pump_max]  [MW]
```

**PWL approximation** using the same 3 breakpoints already used for Darcy-Weisbach:

```
At each breakpoint m_i (i = 0,1,2,3):
  ΔP_i  = k_flow × m_i²                        [bar]  (from existing PWL logic)
  P_pump_i = ΔP_i × m_i × 1e5 / (ρ × η × 1e6) [MW]

Slopes and intercepts interpolated between breakpoints → pure PWL in m_dot.
```

Reuses existing `pwl_seg[t,s]` and `pwl_flow[t,s]` binaries. No new binary
variables required.

**Pump efficiency:** `η_pump = 0.70` (default, configurable via `pump_efficiency`
in pipe YAML config).

**Nodal pressure balance** (new method `_link_pressures()` in `network_manager.py`):
```
Supply direction (producer → consumer):
  p_supply_to[t] = p_supply_from[t] + ΔP_pump[t] - ΔP_supply_pipe[t]

Return direction (consumer → producer):
  p_return_from[t] = p_return_to[t] - ΔP_return_pipe[t]

At producer node:
  p_supply_producer[t] = p_return_producer[t] + ΔP_pump[t]
```

**Electricity bus:** `P_pump[t]` added to `el_in` list in `ComponentAssembler`.

**Backwards compatibility:** If `effective_max_flow == 0` or pipe has no PWL
segment (fallback path), `P_pump` is fixed to 0.

### Files changed
- `calion/models/blocks/pipe_pair.py` — new variable + PWL constraints + nodal pressure
- `calion/models/network_manager.py` — `_link_pressures()` method
- `calion/models/component_assembler.py` — add `P_pump` to `el_in`

### Config additions
```yaml
pipes:
  - id: pipe_1
    pump_efficiency: 0.70        # optional, default 0.70
    pump_enabled: true           # optional, default true if PWL active
```

---

## Fix 2 — COP with Heating-Curve Supply Temperature

### Problem
`COP_wrg(t)` is pre-computed using a fixed nominal sink temperature
`Tsink_out_K`. When the optimizer varies `T_supply[t]` (via the heating curve),
the COP does not respond. For planning models with variable supply temperatures,
this underestimates WP efficiency at lower supply temperatures.

### Design

**No changes to the optimizer** (COP remains a `pyo.Param` — MILP-compatible).

**Change in `component_assembler.py`:** Before calling `calculate_cop_series()`,
compute the heating-curve supply temperature series using
`network_physics.calculate_supply_temperature_series()` and pass it as the
`y_column` to the COP calculator.

```python
# component_assembler.py — assemble_heat_pumps()
if outdoor_temp_series is not None:
    T_supply_series = calculate_supply_temperature_series(
        T_outdoor_series=outdoor_temp_series,
        T_supply_min_c=hp_cfg.get('supply_temp_min_c', 80.0),
        T_supply_max_c=hp_cfg.get('supply_temp_max_c', 120.0),
    )
    # inject as sink temperature series into cop config
    cop_cfg_augmented = {**cop_cfg, 'sink_temp_series': T_supply_series}
else:
    cop_cfg_augmented = cop_cfg
```

**In `cop_calculator.py`:** `_calculate_analytical()` and
`_calculate_from_table()` accept an optional `sink_temp_series` list that
overrides `Tsink_out_K` when provided.

**Result:** `COP(t) = f(T_source(t), T_supply_heizkurve(t))` — varies with both
source and sink temperature, but remains a pre-computed parameter series.

### Files changed
- `calion/models/cop_calculator.py` — accept `sink_temp_series` override
- `calion/models/component_assembler.py` — compute + inject heating curve series

### Config additions
```yaml
heat_pumps:
  cop:
    use_heating_curve_sink_temp: true   # optional, default true if outdoor_temp_C present
    supply_temp_min_c: 80.0
    supply_temp_max_c: 120.0
```

---

## Fix 3 — Transport Delay Warm-up Initial Condition

### Problem
For `t < τ_n` (warm-up period), `Constraint.Skip` leaves `w_delay[n,t]`
completely unconstrained. The optimizer freely assigns any value, making the
first `τ` timesteps physically meaningless.

### Design

Replace `Constraint.Skip` with an upper bound from a configurable initial
pipe heat flow parameter:

```python
# pipe_pair.py — w_ub_q_rule
if i < tau_steps[n]:
    Q_init = config.get('Q_pipe_initial_mw', 0.0)
    return w_delay[n, t] <= Q_init   # was: Constraint.Skip
```

**Default `Q_pipe_initial_mw = 0.0`** (conservative: network starts cold).
For warm-start scenarios (operational optimization), the user sets this to
the pre-period steady-state pipe flow.

The lower bound `w_lb_rule` already skips warm-up timesteps — no change needed
there (lower bound of 0 from variable domain is correct for cold start).

### Files changed
- `calion/models/blocks/pipe_pair.py` — `w_ub_q_rule` modification only

### Config additions
```yaml
pipes:
  - id: pipe_1
    Q_pipe_initial_mw: 0.0    # optional, default 0.0
```

---

## Fix 4 — Minimum Uptime/Downtime for Heat Pump

### Problem
Binary `y[t]` can switch every timestep. Real heat pumps have minimum
run/stop times (compressor protection). Without these constraints, the
optimizer overstates flexibility and may produce solutions with unrealistic
cycling.

### Design

**New binary variables** per heat pump:
```
u[t] ∈ {0,1}  — startup  (y[t-1]=0 → y[t]=1)
v[t] ∈{0,1}  — shutdown (y[t-1]=1 → y[t]=0)
```

**Constraints** (standard unit-commitment, Carrión & Arroyo 2006):
```
(1) y[t] - y[t-1] = u[t] - v[t]          ∀t > 1
(2) u[t] + v[t] ≤ 1                        ∀t
(3) Σ_{k=t-L+1}^{t} u[k] ≤ y[t]           ∀t  (min uptime L timesteps)
(4) Σ_{k=t-D+1}^{t} v[k] ≤ 1 - y[t]       ∀t  (min downtime D timesteps)
```

Boundary handling: for `t < L` or `t < D`, the sum is taken over available
timesteps only (standard practice).

**Backwards compatible:** If `min_uptime_h = 0` and `min_downtime_h = 0`
(defaults), constraints (3) and (4) reduce to `0 ≤ y[t]` (trivially satisfied)
and `u`, `v` variables are omitted entirely to avoid bloating the model.

### Files changed
- `calion/models/blocks/heat_pump.py` — new variables + 4 constraints

### Config additions
```yaml
assets:
  HP1:
    type: heat_pump
    min_uptime_h: 4      # optional, default 0 (disabled)
    min_downtime_h: 2    # optional, default 0 (disabled)
```

---

## Fix 5 — LMTD (Accepted Simplification, No Code Change)

Arithmetic mean temperature `T_avg = (T_in + T_out) / 2` is retained.
The LMTD would introduce `ln()` into the Pyomo model, breaking MILP/QP
compatibility. For district heating networks with moderate pipe lengths
(<2 km) and typical temperature drops (<5 K), the error is <2%.

**Action:** Add explicit acknowledgement to paper (see Paper Update section).

---

## Paper Update — Affected Sections

### New equations to add

**Pump model (Fix 1):**
```latex
P_{\mathrm{pump},p}(t) \approx \sum_{k=1}^{3} \left(s_k^P \cdot \dot{m}_p(t) + b_k^P\right) \cdot z_{p,k}(t) \quad [\text{MW}]
```
where slopes `s_k^P` and intercepts `b_k^P` are pre-computed from Darcy-Weisbach
breakpoints and pump efficiency η.

Nodal pressure balance:
```latex
p_j^{\mathrm{sup}}(t) = p_j^{\mathrm{ret}}(t) + \Delta p_{\mathrm{pump},p}(t) - \Delta p_{\mathrm{pipe},p}^{\mathrm{sup}}(t)
```

**COP (Fix 2):**
Add explicit statement: `COP_wrg(t) = f(T_source(t), T_supply,hc(t))` where
`T_supply,hc(t)` is the heating-curve supply temperature (pre-computed parameter).

**Min uptime/downtime (Fix 4):**
Add unit-commitment constraints (1)–(4) with reference to Carrión & Arroyo (2006).

### New section: Model Assumptions and Limitations

| Assumption | Justification | Expected error |
|---|---|---|
| Arithmetic mean for pipe heat loss | MILP compatibility; standard in literature | <2% for L<2km, ΔT<5K |
| Constant fluid properties (cp, ρ) | Variation <6% over operating range | <6% mass flow |
| Perfect foresight | Planning model standard | N/A |
| Pre-computed COP parameter | MILP compatibility | Corrected via heating curve |
| Radial network topology | Scope: greenfield planning | Ring topologies: future work |

---

## Implementation Order

1. Fix 3 (Warm-up) — 30 min, isolated change, no dependencies
2. Fix 4 (Min uptime/downtime) — 1h, isolated to heat_pump.py
3. Fix 2 (COP heating curve) — 1h, cop_calculator + assembler
4. Fix 1 (Pump model) — 3h, most complex, touches 3 files
5. Paper update — after all code fixes validated

---

## Out of Scope

- Ring/loop network topologies (bidirectional flow)
- LMTD (incompatible with MILP)
- Temperature-dependent fluid properties
- Stochastic/rolling-horizon optimization
