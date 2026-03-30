# MILP-Linearisierung: Mathematische Analyse

## Bilineare Terme in CALION

### Type 1: Konvektion (m_dot × T Produkte)

Überall wo Massenfluss × Temperatur auftritt:

| Constraint | Formel | MILP? | Code Location |
|-----------|--------|-------|---------------|
| Heat delivered | $Q = \dot{m} \cdot c_p \cdot (T_{in} - T_{out})$ | ❌ | pipe_pair.py:350 |
| Heat demand | $Q_d = \dot{m}_d \cdot c_p \cdot \Delta T$ | ❌ | thermal_node.py:328 |
| Temp drop supply | $\dot{m} \cdot c_p \cdot (T_{s,in} - T_{s,out}) = Q_{loss}$ | ❌ | pipe_pair.py:323 |
| Network mixing | $T_{node} \cdot \sum \dot{m}_{in} = \sum \dot{m}_{in} \cdot T_{out}$ | ❌ | thermal_node.py:269 |

**MILP-Linearisierung:** Setze alle $T$ = konstant $\rightarrow$ $\dot{m} \cdot c_p \cdot T_{nom} = $ LINEAR

### Type 2: Temperatur-Abhängige Verluste

| Constraint | Formel | MILP? | Lösung |
|-----------|--------|-------|--------|
| Heat loss | $Q_L = U \cdot L \cdot (T_{avg} - T_{ground})$ | Ja* | Fix $T_{avg} = T_{nom}$ |
| Velocity² (pressure) | $\Delta P \propto v^2 = (\dot{m}/A)^2$ | Nein | PWL (3 Segmente) ✅ |

*Nur wenn $T_{avg}$ ist Var (non-MILP)

---

## Detaillierte Constraint-Analyse

### 1. Wärmeverlust im Rohr

**Physik:**
$$Q_{loss}(t) = U \cdot L \cdot \frac{(T_{in}(t) + T_{out}(t))}{2} - T_{ground}(t)$$

**MILP-Variante (pipe_pair.py, Line 267-270):**
$$Q_{loss}(t) = U \cdot L \cdot (T_{nom} - T_{ground}(t)) / 10^6$$

**Problem:**
- Wenn $T(t) \neq T_{nom}$ → Fehler in Q_loss
- Z.B. T = 70°C (statt nom 90°C) → Q_loss ↓ 20%

**Numerisches Beispiel:**
```
U = 0.28 W/(m·K), L = 1000 m
T_nom = 90°C, T_ground = 10°C

Q_loss(nom) = 0.28 × 1000 × (90-10) / 1e6 = 0.0224 MW = 22.4 kW

Wenn real T = 70°C:
Q_loss(actual) = 0.28 × 1000 × (70-10) / 1e6 = 0.0168 MW = 16.8 kW
→ Fehler: -25% !
```

**Akzeptanz:** Nur wenn ΔT < 10% um nominal erwartet

---

### 2. Wärmebedarfsdeckung

**Non-MILP (bilinear):**
$$Q_d(t) = \dot{m}_d(t) \cdot c_p \cdot [T_{supply}(t) - T_{return}(t)]$$

**MILP-Ersatz:**
$$\dot{m}_d(t) = \frac{Q_d(t) \cdot 1000}{c_p \cdot (T_{s,nom} - T_{r,nom})}$$

**Fehler bei Temp-Abweichung:**

Wenn real ΔT ≠ nominal ΔT → Massenfluss falsch berechnet

Beispiel:
```
Q_d = 2 MW, c_p = 4.186 kJ/(kg·K)
Nominal: ΔT_nom = 90 - 50 = 40 K → ṁ = 2000 / (4.186 × 40) = 11.95 kg/s
Aktuell: ΔT_real = 90 - 55 = 35 K → ṁ_real = 2000 / (4.186 × 35) = 13.68 kg/s
→ Fehler: +14% in m_dot!
```

---

### 3. Netzwerk-Vermischung (Multi-Pipe Junction)

**Physik (Enthalpie-Balance):**
$$T_{node}(t) = \frac{\sum_i \dot{m}_{in,i}(t) \cdot T_{in,i}(t)}{\sum_i \dot{m}_{in,i}(t)}$$

**Äquivalent (Pyomo-Constraint):**
$$T_{node}(t) \cdot \sum_i \dot{m}_{in,i}(t) = \sum_i \dot{m}_{in,i}(t) \cdot T_{in,i}(t)$$

**Bilinearität:** $T_{node} \times \dot{m}$ und $\dot{m} \times T_{in}$ sind Produkte

**MILP-Behandlung (aktuell):**
```python
if incoming_pipes and not milp_linearize_temp:
    # → SKIPPED wenn milp_linearize=True!
```

**Fehler:** T_node bleibt FREE VARIABLE → keine physikalische Vermischung!

**Korrektur für MILP:**
```python
# Alle eingehenden Rohre haben T_out = T_nom in MILP
# Also: T_node = weighted_avg(T_nom, T_nom, ...) = T_nom
# → T_node = T_nom constraint hinzufügen
```

---

### 4. Transport-Delay: SOS2 Big-M Linearisierung

**Problem:** $\tau(\dot{m}) = \frac{\rho \cdot A \cdot L}{\dot{m}}$ ist nichtlinear

**Physik:**
$$Q_{consumer}(t) = Q_{delivered}(t - \tau(\dot{m}(t)))$$

**3-Bucket SOS2-Approximation:** Fix $\tau$ zu einer von 3 Werten, je nach $\dot{m}$ Bereich

| Bucket | $\dot{m}$ range | Delay $\tau$ [timesteps] | Reason |
|--------|--------|----------|--------|
| 0 | $[m_{mid}, m_{max}]$ | $\tau_1$ | High flow → short delay |
| 1 | $[m_{min}, m_{mid}]$ | $\tau_2$ | Medium |
| 2 | $[0, m_{min}]$ | $\tau_3$ | Low flow → long delay |

**Delay-Berechnung (network_physics.py, Line 428):**
$$\tau(m) = \text{round}\left(\frac{V_{pipe}}{m \cdot \Delta t_{seconds}}\right)$$

wobei $V_{pipe} = L \cdot \rho \cdot A$ [kg]

**Beispiel:**
```
L = 10 km = 10000 m, D_inner = 100 mm, ρ = 1000 kg/m³
A = π × (0.05)² = 0.00785 m², V = 78500 kg
dt = 1 h = 3600 s

Bei m = 50 kg/s: τ = 78500 / (50 × 3600) = 0.436 h = 26 min ≈ 1 timestep
Bei m = 10 kg/s: τ = 78500 / (10 × 3600) = 2.18 h ≈ 2 timesteps
Bei m = 1 kg/s:  τ = 78500 / (1 × 3600) = 21.8 h ≈ 22 timesteps
```

---

## Big-M Werte und deren Auswirkungen

### B1: W-Delay Coupling (transport delay linearization)

**Constraints:**
```
w[n,t] ≤ Q_delivered[t-τ]              (upper bound to Q)
w[n,t] ≤ M_Q × z[n,t]                  (z-coupling)
w[n,t] ≥ Q_delivered[t-τ] - M_Q×(1-z) (lower bound)
Q_consumer[t] = Σ_n w[n,t]             (sum over buckets)
```

**Effekt von M_Q:**

| M_Q | Impact | Problem |
|-----|--------|---------|
| Too small | Cuts off real values | Infeasible |
| Just right | Constraints tight | Numerically stable |
| Too large (current) | Constraints loose | Solver prefers wrong bucket |

**Aktuell (pipe_pair.py, Zeile 520-525):**
```python
max_heat_delivered_mw = max(
    effective_max_flow * cp_water * delta_t_nom / 1000 * 1.2, 
    100.0  # ← Problem: fallback to 100 MW even for 5 MW network!
)
```

**Besser:**
```python
# Use actual nominal heat delivery
q_nom = effective_max_flow * cp_water * (supply_temp_nominal_c - return_temp_nominal_c) / 1000
M_Q = q_nom * 1.1  # 10% margin above nominal
```

### B2: Flow Big-M (delay bucket selection)

```python
M_FLOW_BIG = effective_max_flow * 1.1  # ✅ Good (10% slack is reasonable)
```

---

### Numerische Stabilität: Condition Number

Big-M Methode kann zu schlecht konditionierten Matrizen führen:

$$\text{cond}(A) \propto M$$

Wenn $M$ zu groß → Solver-Fehler, Numerik-Instabilität

**HiGHS Default-Toleranz:** 1e-6 (streng)

**Empfehlung:** $M$ < 1e6 halten

| Wert | Größe | Risk |
|-----|-------|------|
| $M = 1.1 \times m_{max}$ | 50–200 (typ.) | ✅ Safe |
| $M = 100$ (hardcoded) | 100 | ✅ Safe |
| $M = 1e4$ (BIG_M_GRID_MW) | 10000 | ⚠️ Risky |
| $M = 1e6$ | 1000000 | ❌ Numerically unstable |

**Aktuelles CALION:**
```python
BIG_M_GRID_MW = 1e4  # ← Too large! Only used for grid import/export
M_Q (delay) = max(100, q_nom × 1.2)  # ← Usually < 100, OK
```

---

## Constraint-Matrix: Was ist Linear, Was nicht?

### In Non-MILP Mode (Full Nonlinear)

```
BILINEAR PRODUCTS (need QP/NLP):
  1. m_dot[t] × T_supply[t]             [heat delivered, demand]
  2. m_dot[t] × (T_in - T_out)[t]       [temp drop]
  3. T_supply[t] × Σm_dot_in[t]         [network mixing]
  4. (m_dot/A)² ∝ velocity²             [pressure drop]
  
NON-CONVEX (may have local minima):
  - All of above (except PWL pressure)
```

### In MILP Mode (Fixed Temperatures)

```
LINEAR (HiGHS MILP OK):
  1. m_dot[t] × T_nom                   ✅ Constant
  2. Σ m_dot[t]                         ✅ Flow balance (linear)
  3. Pressure drop (PWL)                ✅ Already PWL
  4. Transport delay (SOS2 + Big-M)     ✅ Binary + linear
  
STILL BILINEAR (need QP or skip):
  - Multi-pipe mixing: T_node × Σm_dot  ❌ SKIPPED (BUG!)
  - Delay: z_delay[n,t] × w_delay      ✅ Big-M linearizes it
```

---

## Fehlerfortpflanzung

Wenn MILP-Approximationen fehlerhaft sind:

### 1. Heat Loss Error → Energy Balance Off

```
True:  Q_out = Q_in - Q_loss(T_real)
MILP:  Q_out = Q_in - Q_loss(T_nom)
Error: ΔQ ≈ U × L × (T_real - T_nom) / 1e6
```

Beispiel: 5 Rohre, je 1 km, ΔT_error = 5°C:
```
Σ ΔQ ≈ 5 × 0.28 × 1000 × 5 / 1e6 = 0.007 MW = 7 kW
→ Energy imbalance 7 kW (kann sich über 100+ timesteps aufsummieren!)
```

### 2. Mass Flow Error → Consumer Undersupply

```
True: ṁ = Q_d / (c_p × ΔT_real)
MILP: ṁ = Q_d / (c_p × ΔT_nom)

Error ≈ Q_d × (ΔT_nom - ΔT_real) / (c_p × ΔT_nom × ΔT_real)
```

Bei ±5% ΔT Abweichung → ±5% Massenfluss Fehler

### 3. Multi-Pipe Mixing Bug → Completely Free T_node

```
Solver: wähle T_node = max (minimizes heat delivery)
Reality: T_node = weighted_avg (physical mixing)
Die Lösung ist UNREALISTISCH
```

---

## Validierungs-Checks Post-Solve

Nach der Optimierung diese Größen überprüfen:

```python
# 1. Temperatur Bounds Check
T_sup_min = min(pyo.value(T_supply[t]) for t in time_set)
T_sup_max = max(pyo.value(T_supply[t]) for t in time_set)
assert T_sup_min >= 60 and T_sup_max <= 130, "T_supply out of bounds!"

# 2. Energy Balance Check
total_in = sum(pyo.value(Q_delivered[t]) for t in time_set) * dt_h
total_demand = sum(pyo.value(Q_consumer[t]) for t in time_set) * dt_h - total_delay_loss
total_loss = sum(...heat losses...) * dt_h
assert abs(total_in - total_demand - total_loss) < 1 MWh, "Energy imbalance!"

# 3. Big-M Utilization Check
w_max = max(pyo.value(w_delay[n,t]) for n,t in model.z_delay.keys())
if w_max > M_Q * 0.95:
    print("WARNING: w_delay near Big-M limit!")

# 4. Network Mixing Check
for node in multi_pipe_nodes:
    T_node = pyo.value(T_supply[node, t])
    T_in_weighted = weighted_avg([T_out[p,t] for p in incoming_pipes])
    assert abs(T_node - T_in_weighted) < 0.1, f"Mixing failed at {node}"
```

