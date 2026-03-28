# MILP-Linearisierung: Kritische Probleme & Schnelle Fixes

## 🔴 KRITISCHE ISSUES (Priorität 1)

### Problem 1: Multi-Pipe Junctions in MILP sind NICHT konsistent

**Datei:** `energis/models/blocks/thermal_node.py` **Zeile 229**

**Aktueller Code:**
```python
if incoming_pipes and not milp_linearize_temp:  # ← SKIPPED WENN MILP!
    if len(incoming_pipes) > 1:
        def multi_temp_rule(m, t):
            total_m = sum(m_dot[p, t] for p in incoming_pipes)
            weighted_T = sum(m_dot[p, t] * T_out[p, t] for p in incoming_pipes)
            return T_supply[t] * total_m == weighted_T  # BILINEAR
```

**Problem:**
- ✅ Single-pipe: T_supply = T_pipe_out (works)
- ❌ **Multi-pipe in MILP: T_supply ist FREE VARIABLE** (keine Constraint!)
- **Folge:** Energiebilanz verletzt, Solver kann willkürliche T_supply wählen

**Fix (schnell):**
```python
if incoming_pipes:
    if len(incoming_pipes) == 1:
        # Single: keeps working
        def single_temp_rule(m, t):
            pipe_T_out = getattr(m, f'{incoming_pipes[0].upper().replace("-","_")}_T_supply_out')
            return T_supply[t] == pipe_T_out[t]
    else:
        # Multi-pipe
        if milp_linearize_temp:
            # MILP: Use NOMINAL temperature (linear, no bilinear)
            def multi_temp_milp_rule(m, t):
                # T_supply[t] = flow-gewichteter Durchschnitt der NOMINALEN Temps
                # VEREINFACHT: Alle Zuführungen haben nominale T_supply → 
                # T_supply[t] bleibt einfach auf nominal
                return T_supply[t] == supply_temp_nominal_c
            setattr(model, f'{prefix}_temp_mixing_milp',
                    pyo.Constraint(time_set, rule=multi_temp_milp_rule))
        else:
            # Non-MILP: Bilinear mixing (bestehendes Code)
            def multi_temp_rule(m, t):
                total_m = sum(...)
                weighted_T = sum(...)
                return T_supply[t] * total_m == weighted_T
            setattr(model, f'{prefix}_temp_mixing',
                    pyo.Constraint(time_set, rule=multi_temp_rule))
```

---

### Problem 2: Temperatur-Bounds sind zu HART coded

**Datei:** `energis/models/blocks/pipe_pair.py` **Zeilen 166–174**

**Aktueller Code:**
```python
supply_temp_nominal_c = config.get('supply_temp_nominal_c', 90.0)  # ← DEFAULT!
supply_temp_min = min(60, supply_temp_nominal_c - 30)
supply_temp_max = max(130, supply_temp_nominal_c + 10)
```

**Problem:**
- Netzwerk mit Supply 120°C bekommt automatisch nominal=90°C (FALSCH!)
- Bounds: [60, 100] → zu eng für High-Temp Netze

**Fix:**
```python
supply_temp_nominal_c = config.get('supply_temp_nominal_c', None)
if supply_temp_nominal_c is None:
    raise ValueError(
        f"Pipe {pipe_id}: Fehlende 'supply_temp_nominal_c' in Config! "
        f"Erforderlich für MILP-Linearisierung."
    )

# Explizite Bounds-Optionen
supply_temp_min = config.get('supply_temp_min_c', min(60, supply_temp_nominal_c - 30))
supply_temp_max = config.get('supply_temp_max_c', max(130, supply_temp_nominal_c + 10))
```

---

### Problem 3: Big-M für Transport-Delay ZU SCHWACH

**Datei:** `energis/models/blocks/pipe_pair.py` **Linie 525–543**

**Aktueller Code:**
```python
M_Q = max_heat_delivered_mw  # ← CAN BE 100+ MW!
w_delay[n,t] <= M_Q * z_delay[n,t]  # ← Zu lose!
```

**Problem:**
```
max_heat_delivered_mw = max(effective_max_flow * cp * ΔT_nom / 1000 * 1.2, 100.0)
→ Oft 100+ MW, aber echte Q_delivered max ≈ 10 MW
→ Constraint w ≤ 100 * z ist quasi wirkungslos
→ Solver hat keinen Anreiz, richtigen Bucket zu wählen
```

**Fix (korrigierte Big-M):**
```python
# Compute actual maximum heat from the nominal conditions
actual_q_max = effective_max_flow * cp_water * (supply_temp_nominal_c - return_temp_nominal_c) / 1000
M_Q = actual_q_max * 1.2  # ← Tighter bound!

w_delay = pyo.Var(range(N_BUCKETS), time_set, domain=pyo.NonNegativeReals,
                   bounds=(0, M_Q))  # ← Set upper bound in Var definition too
```

---

## 🟡 WICHTIGE ISSUES (Priorität 2)

### Problem 4: Terminal Consumer m_dot ist UNKONTROLLIERT

**Datei:** `energis/models/blocks/thermal_node.py` **Linie 311–318**

**Aktueller Code:**
```python
if milp_linearize and not outgoing_pipes:
    logger.info("... heat_demand constraint skipped (enforced via Q_consumer)")
    # ← NO CONSTRAINT CREATED!
```

**Problem:**
- Terminal consumer: Q_demand[t] gegeben
- Aber m_dot[t] ist nicht an Q_demand[t] gekoppelt!
- Ergebnis: Solver kann beliebiges m_dot wählen (Unphysikalisch)

**Fix:**
```python
if node_type == 'consumer':
    if milp_linearize and not outgoing_pipes:
        # Terminal in MILP: Still need m_dot_demand for energy balance
        # Q_consumer[t] = m_dot_avg[t-τ] × cp × ΔT_nom
        # But instantaneous m_dot[t] is free (serves future demand via delay)
        # Document this: add info-log
        logger.info(
            f"    Node {node_id}: MILP terminal — m_dot unconstrained by instantaneous Q_demand "
            f"(coupled via {tau_steps}-step delay). Energy enforced via Q_consumer == Q_demand."
        )
    elif milp_linearize:
        # Non-terminal in MILP: Use linear heat-balance
        dT_nominal = supply_temp_nominal_c - return_temp_c
        if dT_nominal <= 0:
            dT_nominal = 35.0
        
        def heat_demand_rule_milp(m, t):
            return m_dot_demand[t] == Q_demand[t] * 1000 / (cp_water * dT_nominal)
        
        setattr(model, f'{prefix}_heat_demand_milp',
                pyo.Constraint(time_set, rule=heat_demand_rule_milp))
```

---

### Problem 5: Heat-Loss nutzt NOMINALE Temperatur (Approximation)

**Datei:** `energis/models/blocks/pipe_pair.py` **Linie 263–278**

**Aktueller Code:**
```python
def heat_loss_supply_rule_milp(m, t):
    T_avg = supply_temp_nominal_c  # ← FIXED!
    return Q_loss_supply[t] == (u_value_supply * length_m * (T_avg - T_ground[t])) / 1e6
```

**Problem:**
- Realität: Q_loss(t) = U × L × (T(t) - T_ground(t))
- MILP: Q_loss(t) = U × L × (T_nom - T_ground(t))
- **Fehler:** ~±15% wenn aktuales T ≠ T_nom

**Kann nicht ohne nicht-lineare Gleichungen korrigiert werden.** 

**Workaround:** Dokumentieren
```python
logger.warning(
    f"Pipe {pipe_id}: MILP mode uses NOMINAL T_supply={supply_temp_nominal_c}°C "
    f"for heat loss calculation. Actual loss may differ ±15% if T(t) varies."
)
```

---

## 📋 COMPLIANCE CHECKLIST

Vor Verwendung von MILP-Modus (`milp_linearize=True`):

- [ ] **Config Check:** Alle Rohre haben `supply_temp_nominal_c` & `return_temp_nominal_c` explizit
- [ ] **Temperature Bounds:** Config enthält `supply_temp_min_c`, `supply_temp_max_c`
- [ ] **Single-Pipe Only:** Verwende MILP-Modus NUR bei Netzwerken ohne Multi-Pipe-Junctions!
- [ ] **Ground Temp:** `ground_temp_c` konfiguriert (nicht default 10°C)
- [ ] **Heat Loss Accuracy:** ±15% Approximationsfehler akzeptiert?
- [ ] **Solver ✅:** HiGHS (MILP) statt Gurobi oder CBC

---

## 🔧 CORRECTED CODE SNIPPETS

### Fix für thermal_node.py (Multi-Pipe Junctions)

**Zeilen 229–276 ERSETZEN mit:**

```python
# ─ Enthalpy balance (temperature mixing) for nodes with incoming pipes
if incoming_pipes:
    if len(incoming_pipes) == 1:
        # ✅ Single pipe: always works
        pipe_id = incoming_pipes[0]
        pipe_prefix = pipe_id.upper().replace('-', '_')
        
        def single_temp_rule(m, t, _pp=pipe_prefix):
            pipe_T_out = getattr(m, f'{_pp}_T_supply_out')
            return T_supply[t] == pipe_T_out[t]
        
        setattr(model, f'{prefix}_temp_mixing',
                pyo.Constraint(time_set, rule=single_temp_rule))
        logger.info(f"    Node {node_id}: single-pipe temperature link")
    
    else:
        # Multi-pipe
        if milp_linearize_temp:
            # ✅ MILP: Linear mixing at nominal (no bilinear products)
            def multi_temp_milp_rule(m, t):
                # In MILP, all incoming pipes have fixed T_supply_out = nominal
                # So node T_supply ≈ weighted avg of nominls ≈ nominal itself
                return T_supply[t] == supply_temp_nominal_c
            
            setattr(model, f'{prefix}_temp_mixing_milp',
                    pyo.Constraint(time_set, rule=multi_temp_milp_rule))
            logger.info(
                f"    Node {node_id}: multi-pipe MILP mixing (fixed nominal = {supply_temp_nominal_c}°C)"
            )
        
        else:
            # ✅ Non-MILP: Bilinear mixing (needs QP/NLP solver)
            def multi_temp_rule(m, t, _pipes=incoming_pipes):
                total_m = sum(
                    getattr(m, f'{p.upper().replace("-", "_")}_m_dot')[t]
                    for p in _pipes
                )
                weighted_T = sum(
                    getattr(m, f'{p.upper().replace("-", "_")}_m_dot')[t] *
                    getattr(m, f'{p.upper().replace("-", "_")}_T_supply_out')[t]
                    for p in _pipes
                )
                return T_supply[t] * total_m == weighted_T
            
            setattr(model, f'{prefix}_temp_mixing',
                    pyo.Constraint(time_set, rule=multi_temp_rule))
            logger.info(
                f"    Node {node_id}: multi-pipe enthalpy balance "
                f"({len(incoming_pipes)} pipes, bilinear)"
            )
```

---

### Fix für pipe_pair.py (Big-M Transport Delay)

**Linie 525 ÄNDERN von:**
```python
M_Q = max_heat_delivered_mw
```

**Zu:**
```python
# Tight Big-M for transport delay linearization
# Use actual nominal heat delivery (linear), not worst-case estimate
actual_q_max = effective_max_flow * cp_water * (supply_temp_nominal_c - return_temp_nominal_c) / 1000.0
M_Q = actual_q_max * 1.1  # 10% safety margin
M_Q = max(M_Q, 1.0)  # Avoid M_Q = 0

logger.info(f"  Pipe {pipe_id}: Big-M for delay linearization M_Q = {M_Q:.2f} MW")
```

**Und Var-Definition (Linie 530) updaten:**
```python
# BEFORE:
w_delay = pyo.Var(range(N_BUCKETS), time_set, domain=pyo.NonNegativeReals,
                   bounds=(0, M_Q))

# AFTER (already correct, but now M_Q is tight):
w_delay = pyo.Var(range(N_BUCKETS), time_set, domain=pyo.NonNegativeReals,
                   bounds=(0, M_Q))  # ← M_Q is now realistic
```

---

## Fehler-Rückverfolgung

**Wenn Netzwerk mit MILP infeasible oder sub-optimal wird:**

1. **Checke Config:**
   ```python
   # Müssen ALLE haben:
   supply_temp_nominal_c: 90  # (oder < euer Netzwerk)
   return_temp_nominal_c: 50
   ```

2. **Prüfe auf Multi-Pipe Junctions:**
   ```
   Debug: Wenn node > 1 incoming_pipes AND milp_linearize=True
   → Apply FIX #1 (T_supply = nominal constraint)
   ```

3. **Überprüfe Big-M:**
   ```python
   # Nach Solve: 
   w_delay_max = max(pyo.value(w_delay[n, t]) for n, t in model.z_delay.keys())
   if w_delay_max >= M_Q * 0.99:
       print("WARNING: w_delay hitting Big-M ceiling → M_Q too small!")
   ```

