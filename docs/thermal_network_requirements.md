# Anforderungen: TESpy-inspirierte Thermische Netzwerk-Erweiterung

## Übersicht
Erweiterung des EnerGIS-Frameworks um detaillierte thermisch-hydraulische Netzwerkmodellierung für Fernwärmenetze, Dampfnetze und Multi-Temperatur-Systeme.

---

## 1. Topologie & Geometrie

### 1.1 Geografische Modellierung ✅ ERFORDERLICH
- [ ] **Knoten mit Koordinaten**
  - Jeder Knoten hat (x, y) Position in Metern oder geographischen Koordinaten
  - Optional: (z) für Höhenunterschiede (geodätischer Druck)

- [ ] **Rohrlängen aus Distanzen**
  - Automatische Berechnung: `L = sqrt((x1-x2)² + (y1-y2)²)` (Euklidisch)
  - Optional: GIS-basierte Routing-Distanzen (Straßennetz)
  - Optional: Manhattan-Distanz für städtische Gebiete

- [ ] **Höhenunterschiede**
  - Geodätischer Druckterm: `Δp_geo = ρ · g · Δz`

### 1.2 Vorlauf/Rücklauf-Topologie ✅ ERFORDERLICH
- [ ] **2-Leiter-System (Standard Fernwärme)**
  ```
  Vorlauf:  Erzeuger ──────► Verbraucher
  Rücklauf: Erzeuger ◄────── Verbraucher
  ```
  - Separate Rohre: `supply_pipe` und `return_pipe`
  - Constraint: `m_flow_supply = m_flow_return` (steady-state)
  - Unterschiedliche Verluste (Vorlauf heißer → mehr Verlust)

- [ ] **4-Leiter-System (Optional, für bidirektionale Netze)**
  ```
  HT Vorlauf:  ───────►
  HT Rücklauf: ◄───────
  NT Vorlauf:  ───────►
  NT Rücklauf: ◄───────
  ```

### 1.3 Netzwerk-Topologie ✅ ERFORDERLICH
- [ ] **Graph-Repräsentation**
  - Knoten (Nodes): Erzeuger, Verbraucher, Verzweigungen
  - Kanten (Edges): Rohre zwischen Knoten
  - NetworkX-Integration für Topologie-Analyse

- [ ] **Topologie-Typen**
  - Baumstruktur (radial)
  - Vermascht (meshed)
  - Hybride Strukturen

- [ ] **Flussrichtungen**
  - Unidirektional: Feste Richtung
  - Bidirektional: Variable mit Binary-Variable `flow_dir[pipe,t]`

---

## 2. Physikalische Zustandsgrößen

### 2.1 Druck ✅ ERFORDERLICH
- [ ] **Druckvariablen**
  - `p[node, t]`: Absoluter Druck an jedem Knoten [bar]
  - `Δp[pipe, t]`: Druckverlust über Rohr [bar]

- [ ] **Druckgrenzen**
  - `p_min ≤ p[node, t] ≤ p_max`
  - Typisch: 3 bar ≤ p ≤ 16 bar (Fernwärme)
  - Dampfnetze: bis 100 bar

- [ ] **Druckverlust-Modellierung**
  - Darcy-Weisbach: `Δp = λ · (L/D) · (ρ·v²/2)`
  - Umformung auf Massenstrom: `Δp = f(m, L, D, ρ, λ)`
  - **LINEARISIERUNG**: Stückweise linear (PWL) mit SOS2-Variablen

### 2.2 Temperatur ✅ ERFORDERLICH
- [ ] **Temperaturvariablen**
  - `T[node, t]`: Temperatur am Knoten [°C]
  - `T_supply[pipe, t]`: Vorlauftemperatur [°C]
  - `T_return[pipe, t]`: Rücklauftemperatur [°C]

- [ ] **Temperaturgrenzen**
  - Hochtemperatur-Dampf: 120-300°C
  - Fernwärme HT: 80-120°C
  - Fernwärme NT: 40-70°C
  - Min. Spreizung: `T_supply - T_return ≥ ΔT_min` (z.B. 20K)

- [ ] **Temperatur-Mischung bei Knoten**
  - Energiebilanz: `Σ(m_in[i] · T_in[i]) = m_out · T_out`
  - **LINEARISIERUNG**: McCormick Envelopes für bilineare Terme `m·T`

- [ ] **Temperatur entlang Rohr**
  - Punktuelle Verbraucher: `T_out = T_in - Q_load/(m·cp)`
  - Verteilte Verbraucher: Exponentielles Profil, PWL-approximiert
  - Wärmeverluste: `dT/dx = -(U·π·D)/(m·cp) · (T - T_soil)`

### 2.3 Massenstrom ✅ ERFORDERLICH
- [ ] **Massenstrom-Variablen**
  - `m_flow[pipe, t]`: Massenstrom durch Rohr [kg/s]
  - `m_in[node, i, t]`: Zufluss am Knoten von Rohr i
  - `m_out[node, j, t]`: Abfluss am Knoten zu Rohr j

- [ ] **Massenbilanz am Knoten**
  - `Σ m_in[i] = Σ m_out[j] + m_consumed`
  - Bei Verbrauchern: `m_consumed = Q_load / (cp · ΔT)`

- [ ] **Grenzen**
  - `m_min ≤ m_flow ≤ m_max`
  - Minimaler Massenstrom für Turbulenz (Re > 4000)
  - Maximaler Massenstrom aus Rohrquerschnitt

---

## 3. Komponenten

### 3.1 Rohre (Pipes) ✅ ERFORDERLICH

#### Variablen
```python
m_flow[t]        # Massenstrom [kg/s]
p_in[t]          # Eingangsdruck [bar]
p_out[t]         # Ausgangsdruck [bar]
T_in[t]          # Eingangstemperatur [°C]
T_out[t]         # Ausgangstemperatur [°C]
Q_loss[t]        # Wärmeverlust [MW]
D_nominal        # Nennweite [mm] - INVESTITIONSVARIABLE (diskret)
```

#### Parameter
```python
L                # Länge [m] - aus Geografie
λ                # Rohrreibungszahl (Moody) - abhängig von Re, k/D
U                # Wärmedurchgangskoeffizient [W/(m²·K)]
k                # Absolute Rauheit [mm] - Material-abhängig
```

#### Constraints
1. **Druckverlust** (linearisiert)
   ```python
   # Darcy-Weisbach: Δp = λ · (L/D) · (ρ·v²/2)
   # Mit v = m/(ρ·A) und A = π·D²/4:
   # Δp = f · L · m² / (2·ρ·A²·D) mit f = λ
   #
   # LINEARISIERUNG: PWL mit 5-10 Segmenten über m_flow-Bereich
   p_in[t] - p_out[t] == PWL(m_flow[t], pressure_drop_curve)
   ```

2. **Wärmeverlust**
   ```python
   # Verlust an Erdreich
   Q_loss[t] == U · π · D · L · (T_avg[t] - T_soil) / 1e6  # in MW

   # Mit T_avg = (T_in + T_out) / 2
   # Für Linearität: T_avg durch T_in approximieren oder PWL
   ```

3. **Energiebilanz**
   ```python
   # Temperaturabfall durch Verluste
   m_flow[t] · cp · (T_in[t] - T_out[t]) == Q_loss[t]

   # LINEARISIERUNG: Falls m_flow·T_out bilinear → McCormick Envelopes
   ```

4. **Durchmesser-Investition**
   ```python
   # Diskrete Auswahl aus Katalog
   D_nominal = Σ DN_i · build_DN[i]  # mit Σ build_DN[i] ≤ 1

   # Standard-Nennweiten: DN 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300, 400, 500, 600
   ```

#### Rohr-Typen
- [ ] **Standard-Rohr** (oben beschrieben)
- [ ] **Vorlauf-Rohr** (höhere Temperatur, mehr Verluste)
- [ ] **Rücklauf-Rohr** (niedrigere Temperatur, weniger Verluste)
- [ ] **Isoliertes Rohr** (variable Isolationsdicke als Investment)

---

### 3.2 Pumpen (Pumps) ✅ ERFORDERLICH

#### Variablen
```python
m_flow[t]        # Massenstrom [kg/s]
Δp[t]            # Druckerhöhung [bar]
P_el[t]          # Elektrische Leistung [MW]
η[t]             # Wirkungsgrad [-]
is_on[t]         # Binary: Pumpe an/aus
```

#### Parameter
```python
Δp_max           # Maximale Druckerhöhung [bar]
m_flow_max       # Maximaler Durchfluss [kg/s]
pump_curve[]     # Kennlinie H(Q)
efficiency_curve[] # η(Q)
```

#### Constraints
1. **Hydraulische Leistung**
   ```python
   # P_hydraulic = V̇ · Δp = (m/ρ) · Δp
   P_hyd[t] = (m_flow[t] / ρ) · Δp[t] / 1e6  # in MW
   ```

2. **Elektrische Leistung**
   ```python
   P_el[t] = P_hyd[t] / η[t]

   # LINEARISIERUNG: η(m_flow) durch PWL approximieren
   η[t] = PWL(m_flow[t], efficiency_curve)
   ```

3. **Pumpenkennlinie**
   ```python
   # Typisch: H = a - b·Q² (parabolisch)
   # LINEARISIERUNG: PWL mit 5-10 Stützstellen
   Δp[t] ≤ PWL(m_flow[t], pump_curve)
   ```

4. **On/Off Logik**
   ```python
   m_flow[t] ≤ m_flow_max · is_on[t]
   Δp[t] ≤ Δp_max · is_on[t]

   # Optional: Mindestdurchfluss
   m_flow[t] ≥ m_flow_min · is_on[t]
   ```

5. **Energieverbrauch → Electricity Bus**
   ```python
   electricity_bus.add_input(P_el[t])
   ```

#### Pumpen-Typen
- [ ] **Kreiselpumpe** (Standard, variable Drehzahl)
- [ ] **Netzpumpe** (zentral, große Leistung)
- [ ] **Hausanschlusspumpe** (dezentral, kleine Leistung)

---

### 3.3 Thermische Knoten (Thermal Nodes) ✅ ERFORDERLICH

#### Variablen
```python
p[t]             # Druck am Knoten [bar]
T[t]             # Temperatur am Knoten [°C]
m_in[i, t]       # Massenströme eingehend von Rohr i
m_out[j, t]      # Massenströme ausgehend zu Rohr j
```

#### Parameter
```python
node_type        # "producer", "consumer", "junction"
T_level          # Temperaturniveau (für Multi-Netz)
coords           # (x, y, z) geografische Position
```

#### Constraints
1. **Massenbilanz**
   ```python
   Σ m_in[i, t] == Σ m_out[j, t] + m_consumed[t]
   ```

2. **Energiebilanz / Temperaturmischung**
   ```python
   # Bei Verzweigung (junction):
   Σ(m_in[i,t] · T_in[i,t]) == Σ(m_out[j,t] · T[t])

   # LINEARISIERUNG mit McCormick Envelopes:
   # Einführung Hilfsvariable w[i,t] = m_in[i,t] · T_in[i,t]
   # Mit bounds: m_min ≤ m ≤ m_max, T_min ≤ T ≤ T_max
   #
   # McCormick Inequalities:
   w ≥ T_min · m + m_min · T - T_min · m_min
   w ≥ T_max · m + m_max · T - T_max · m_max
   w ≤ T_min · m + m_max · T - T_min · m_max
   w ≤ T_max · m + m_min · T - T_max · m_min
   ```

3. **Druckkonsistenz**
   ```python
   # Bei Verzweigung: Gleicher Druck für alle ausgehenden Rohre
   p_out[j, t] == p[t] for all j
   ```

#### Node-Typen
- [ ] **Producer Node**: Einspeisepunkt (CHP, Kessel, etc.)
- [ ] **Consumer Node**: Entnahmepunkt (Gebäude, Industrie)
- [ ] **Junction Node**: Reine Verzweigung ohne Produktion/Verbrauch
- [ ] **Interface Node**: Übergang zwischen Temperatur-Ebenen

---

### 3.4 Wärmeerzeuger (Heat Producers) ✅ ERFORDERLICH

#### Integration mit Netz
```python
# Erzeugter Wärmestrom wird in Netz eingespeist
Q_produced[t] = m_inject[t] · cp · (T_supply - T_return)

# Constraint an Producer Node:
m_out[producer_pipe, t] == m_inject[t]
T_out[producer_pipe, t] == T_supply
```

#### Erzeuger-Typen (bereits existierend)
- [x] Heat Pump (heat_pump.py)
- [x] CHP / Thermal Generator (thermal_gen.py)
- [x] Power-to-Heat (p2h.py)
- [x] Thermal Storage (storage.py, stratified_storage.py)

#### Neu zu erstellen
- [ ] **Steam Boiler** (Dampferzeuger)
- [ ] **Waste Heat Recovery Unit** (Abwärmenutzung)

---

### 3.5 Wärmeverbraucher (Heat Consumers) ✅ ERFORDERLICH

#### 3.5.1 Punktueller Verbraucher (Point Load)

#### Variablen
```python
Q_demand[t]      # Wärmebedarf [MW] - exogen (Zeitreihe)
m_extract[t]     # Entnommener Massenstrom [kg/s]
T_return_local[t] # Rücklauftemperatur vom Verbraucher [°C]
```

#### Constraints
```python
# Wärmebedarf decken
Q_demand[t] == m_extract[t] · cp · (T_supply - T_return_local[t])

# Massenbilanz am Consumer Node
m_in[supply_pipe, t] == m_extract[t]
m_out[return_pipe, t] == m_extract[t]

# Temperaturen
T_in[supply_pipe, t] == T_supply
T_out[return_pipe, t] == T_return_local[t]

# Rücklauftemperatur-Grenzen
T_return_min ≤ T_return_local[t] ≤ T_return_max
```

#### 3.5.2 Verteilter Verbraucher (Distributed Load)

**Konzept:** Last verteilt über Rohrlänge (z.B. Wohnstraße mit vielen Anschlüssen)

#### Modellierung Option A: Diskretisierung

```python
# Rohr in N Segmente unterteilen
for segment in range(N):
    L_segment = L_total / N
    q_line[segment, t] = Q_total[t] / L_total  # [MW/m]

    # Temperaturabfall pro Segment
    # dT = -(q_line · L_segment) / (m · cp)
    T[segment+1, t] = T[segment, t] - (q_line[segment,t] * L_segment) / (m_flow[t] * cp)

    # Druckverlust pro Segment (wie Standard-Rohr)
    Δp_segment[segment, t] = f(m_flow[t], L_segment, D)
```

**LINEARISIERUNG:**
- Term `q/m` ist wieder bilinear → McCormick Envelopes
- Oder: Annahme konstanter m_flow → dann linear

#### Modellierung Option B: Analytisch mit PWL

```python
# Kontinuierliche Lastverteilung mit exponentieller Lösung:
# T(x) = T_soil + (T_in - T_soil) · exp(-U·π·D·x / (m·cp)) - ...
#
# LINEARISIERUNG: PWL-Approximation der Exponentialfunktion
T_out[t] = T_in[t] - f_PWL(m_flow[t], Q_total[t], L, U, D)
```

#### Empfehlung
**Option A** für MILP (einfacher zu implementieren, robuster)

---

### 3.6 Dampf-Komponenten (Steam Components) ⚠️ ERWEITERT

#### 3.6.1 Dampfturbine (Steam Turbine)

#### Variablen
```python
m_steam[t]       # Dampf-Massenstrom [kg/s]
p_in[t]          # Eingangsdruck [bar]
p_out[t]         # Ausgangsdruck [bar]
T_in[t]          # Eingangstemperatur [°C]
h_in[t]          # Eingangs-Enthalpie [kJ/kg]
h_out[t]         # Ausgangs-Enthalpie [kJ/kg]
P_el[t]          # Elektrische Leistung [MW]
η_is[t]          # Isentroper Wirkungsgrad
```

#### Constraints
```python
# Isentrope Enthalpieänderung
Δh_is = h_in[t] - h_out_isentropic(p_in[t], p_out[t])

# Reale Enthalpieänderung
Δh_real = η_is · Δh_is

# Elektrische Leistung
P_el[t] = m_steam[t] · Δh_real / 1000  # in MW

# LINEARISIERUNG:
# Wasserdampftafeln → PWL-Approximation
# h_out_isentropic(p_in, p_out) → 2D-PWL über (p_in, p_out) Grid
```

#### Dampftafel-Linearisierung
```python
# Stützstellen für (p, T) → h Mapping:
pressure_grid = [1, 5, 10, 20, 40, 80, 100]  # bar
temp_grid = [100, 150, 200, 250, 300, 350]   # °C

# 2D-PWL mit SOS2-Variablen in beiden Dimensionen
# Oder: Vorberechnete Look-up Table für alle (p_in, p_out) Kombinationen
```

#### 3.6.2 Dampferzeuger (Steam Generator)

```python
# Input: Brennstoff oder Elektrizität
# Output: Dampf bei (p_out, T_out, h_out)

Q_fuel[t]        # Brennstoffleistung [MW]
m_steam[t]       # Dampfproduktion [kg/s]
p_out[t]         # Ausgangsdruck [bar]
h_out[t]         # Ausgangs-Enthalpie [kJ/kg]
η_boiler         # Kesselwirkungsgrad

# Constraint
m_steam[t] · h_out[t] / 1000 == η_boiler · Q_fuel[t]
```

#### 3.6.3 Kondensator (Condenser)

```python
# Dampf → Kondensat
m_steam_in[t]    # Dampf-Massenstrom [kg/s]
m_water_out[t]   # Kondensat-Massenstrom [kg/s]
Q_cooling[t]     # Abgeführte Wärme [MW]

# Massenbilanz
m_steam_in[t] == m_water_out[t]

# Energiebilanz
Q_cooling[t] = m_steam_in[t] · (h_steam - h_water) / 1000

# h_steam, h_water aus Dampftafeln (PWL)
```

---

### 3.7 Wärmeübertrager (Heat Exchangers) ✅ ERFORDERLICH

**Anwendung:** Kopplung zwischen Netzen mit unterschiedlichen Temperaturniveaus

```
Hochtemp-Netz (120°C) ─────► │         │ ◄───── Niedertemp-Netz (60°C)
                              │   HEX   │
                              │         │ ────► Niedertemp-Netz (55°C)
Hochtemp-Netz (70°C)  ◄───── │         │
```

#### Variablen
```python
# Primärseite (hot side)
m_hot[t]         # Massenstrom [kg/s]
T_hot_in[t]      # Eingangstemperatur [°C]
T_hot_out[t]     # Ausgangstemperatur [°C]

# Sekundärseite (cold side)
m_cold[t]        # Massenstrom [kg/s]
T_cold_in[t]     # Eingangstemperatur [°C]
T_cold_out[t]    # Ausgangstemperatur [°C]

Q_transfer[t]    # Übertragene Wärme [MW]
```

#### Constraints
```python
# Energiebilanz primär
Q_transfer[t] == m_hot[t] · cp_hot · (T_hot_in[t] - T_hot_out[t])

# Energiebilanz sekundär
Q_transfer[t] == m_cold[t] · cp_cold · (T_cold_out[t] - T_cold_in[t])

# Pinch-Point (minimale Temperaturdifferenz)
T_hot_out[t] - T_cold_out[t] ≥ ΔT_pinch  # z.B. 5K

# Effectiveness-NTU Methode (vereinfacht, linearisiert)
# ε = Q_actual / Q_max
# Q_max = min(m_hot·cp_hot, m_cold·cp_cold) · (T_hot_in - T_cold_in)
#
# LINEARISIERUNG: ε als Parameter (konstant) oder PWL über m-Verhältnis
```

---

## 4. Multi-Temperatur-Netze ✅ ERFORDERLICH

### 4.1 Netzwerk-Hierarchie

```
┌─────────────────────────────────────────────────┐
│  Hochtemperatur-Dampfnetz (250°C, 40 bar)      │
│  - Dampfturbinen                                │
│  - Prozessdampf (Industrie)                     │
└─────────────┬───────────────────────────────────┘
              │ HEX
              ↓
┌─────────────────────────────────────────────────┐
│  Mitteltemperatur-Fernwärme (90°C, 6 bar)      │
│  - CHP-Anlagen                                  │
│  - Großverbraucher                              │
└─────────────┬───────────────────────────────────┘
              │ HEX
              ↓
┌─────────────────────────────────────────────────┐
│  Niedertemperatur-Fernwärme (55°C, 3 bar)      │
│  - Wärmepumpen                                  │
│  - Niederenergiehäuser                          │
└─────────────────────────────────────────────────┘
```

### 4.2 Implementierung

#### Definition der Netze
```yaml
# config: networks.yaml
networks:
  - id: "steam_hp"
    name: "Hochdruck-Dampfnetz"
    medium: "water_steam"
    T_supply: 250
    T_return: 180
    p_nominal: 40
    p_min: 30
    p_max: 50

  - id: "dh_ht"
    name: "Fernwärme Hochtemperatur"
    medium: "water_liquid"
    T_supply: 90
    T_return: 50
    p_nominal: 6
    p_min: 3
    p_max: 10

  - id: "dh_lt"
    name: "Fernwärme Niedertemperatur"
    medium: "water_liquid"
    T_supply: 55
    T_return: 35
    p_nominal: 3
    p_min: 2
    p_max: 6
```

#### Interface-Knoten zwischen Netzen
```python
# Heat Exchanger verbindet zwei Netze
hex_steam_to_dh = HeatExchangerBlock(
    primary_network="steam_hp",
    secondary_network="dh_ht",
    Q_max=50  # MW
)

# Constraint: Wärmestrom von HT-Netz zu MT-Netz
Q_steam_to_dh[t] ≥ 0  # Nur abwärts in Temperaturniveau
```

### 4.3 Bus-System für Multi-Netz

#### Erweiterte Bus-Struktur
```python
# Jedes Netz hat separate Buses für Vorlauf/Rücklauf
buses = {
    # Hochdruck-Dampf
    "steam_hp_supply": Bus(type=BusType.HEAT, T_level=250),
    "steam_hp_return": Bus(type=BusType.HEAT, T_level=180),

    # Fernwärme HT
    "dh_ht_supply": Bus(type=BusType.HEAT, T_level=90),
    "dh_ht_return": Bus(type=BusType.HEAT, T_level=50),

    # Fernwärme NT
    "dh_lt_supply": Bus(type=BusType.HEAT, T_level=55),
    "dh_lt_return": Bus(type=BusType.HEAT, T_level=35),
}
```

#### Erzeuger-Zuordnung
```python
# CHP kann in beide Netze einspeisen
chp_1 = ThermalGenerator(
    outputs=[
        Flow(bus="steam_hp_supply", Q_max=30),  # Dampf-Auskopplung
        Flow(bus="dh_ht_supply", Q_max=20),     # Fernwärme-Auskopplung
    ]
)

# Wärmepumpe nur in NT-Netz
hp_1 = HeatPump(
    output=Flow(bus="dh_lt_supply", Q_max=5)
)
```

---

## 5. Wärmeverluste ✅ ERWEITERT

### 5.1 Rohr-Wärmeverluste

#### Detailliertes Modell
```python
# Wärmedurchgang durch mehrschichtige Isolation:
# Q_loss = U · A · (T_pipe - T_soil)
#
# Mit U = 1 / (R_total)
# R_total = R_pipe + R_insulation + R_soil

# Thermischer Widerstand Isolierung (zylindrisch):
# R_ins = ln(D_outer / D_inner) / (2·π·λ_ins)

# Parameter
D_inner          # Innendurchmesser [m]
t_insulation     # Isolationsdicke [m] - INVESTITIONSVARIABLE
λ_insulation     # Wärmeleitfähigkeit Isolation [W/(m·K)]
T_soil[t]        # Erdreichtemperatur [°C] - zeitabhängig (Winter/Sommer)

# Variable
Q_loss[pipe, t]  # Wärmeverlust [MW]

# Constraint
D_outer = D_inner + 2 · t_insulation
R_ins = ln(D_outer / D_inner) / (2·π·λ_ins)
U = 1 / (R_pipe + R_ins + R_soil)

Q_loss[t] = U · π · D_outer · L · (T_pipe[t] - T_soil[t]) / 1e6
```

#### Vereinfachtes Modell (linear)
```python
# Vorberechnung eines effektiven U-Werts pro Isolationsklasse
insulation_classes = {
    "poor": {"U": 0.8, "cost": 100},      # EUR/m
    "standard": {"U": 0.4, "cost": 150},
    "good": {"U": 0.2, "cost": 200},
    "excellent": {"U": 0.1, "cost": 300},
}

# Binary-Variable für Auswahl
select_insulation[pipe, class] = pyo.Var(domain=Binary)

# Constraint: Genau eine Klasse auswählen
Σ select_insulation[pipe, class] == 1

# U-Wert aus Auswahl
U[pipe] = Σ select_insulation[pipe, class] · U_class
```

### 5.2 Zeitabhängige Verluste

#### Erdreichtemperatur-Modell
```python
# Sinusförmiges Jahresprofil
T_soil[t] = T_soil_mean + T_soil_amplitude · sin(2·π·(t - t_phase) / 8760)

# Parameter (Deutschland typisch):
T_soil_mean = 10       # °C
T_soil_amplitude = 5   # °C
t_phase = 2190         # h (Maximum im Sommer)
```

#### Auswirkung
```python
# Winter: T_soil = 5°C → höhere Verluste (ΔT = 85K bei 90°C Vorlauf)
# Sommer: T_soil = 15°C → niedrigere Verluste (ΔT = 75K)
```

---

## 6. Linearisierung aller nichtlinearen Terme ✅ KRITISCH

### 6.1 Übersicht nichtlinearer Terme

| **Term** | **Wo?** | **Methode** | **Genauigkeit** |
|----------|---------|-------------|-----------------|
| `m²` | Druckverlust | PWL + SOS2 | ±2% (10 Segmente) |
| `m · T` | Wärmestrom, Mischung | McCormick | Exakt innerhalb Bounds |
| `m · Δp` | Pumpenleistung | PWL beide Variablen | ±3% |
| `ln(D)` | Thermischer Widerstand | Diskrete Auswahl | Exakt |
| `exp(-x)` | Verteilte Last | PWL | ±1% (15 Segmente) |
| `η(m)` | Pumpen-Wirkungsgrad | PWL + SOS2 | ±1% |
| `h(p,T)` | Dampf-Enthalpie | 2D-PWL | ±2% |

### 6.2 Detaillierte Methoden

#### 6.2.1 Stückweise lineare Approximation (PWL) mit SOS2

**Anwendung:** Univariate nichtlineare Funktionen (z.B. `y = f(x)` mit `f(x) = x²`)

**Methode:**
```python
# Gegeben: y = x² mit x ∈ [0, 10]

# 1. Stützstellen definieren
x_points = [0, 2, 4, 6, 8, 10]
y_points = [0, 4, 16, 36, 64, 100]  # = x²

# 2. SOS2-Variablen (Special Ordered Set Type 2)
λ = pyo.Var(range(len(x_points)), domain=pyo.NonNegativeReals)

# 3. Constraints
# x = Σ λ[i] · x_points[i]
# y = Σ λ[i] · y_points[i]
# Σ λ[i] = 1
# λ ist SOS2 (maximal 2 aufeinanderfolgende λ[i] dürfen > 0 sein)

model.x_approx = pyo.Constraint(expr=x == sum(λ[i] * x_points[i] for i in range(len(x_points))))
model.y_approx = pyo.Constraint(expr=y == sum(λ[i] * y_points[i] for i in range(len(x_points))))
model.λ_sum = pyo.Constraint(expr=sum(λ[i] for i in range(len(x_points))) == 1)
model.λ_sos2 = pyo.SOSConstraint(var=λ, sos=2)
```

**Anwendung auf Druckverlust:**
```python
# Δp = a · m²
m_range = [0, 1, 2, 5, 10, 20, 50]  # kg/s
Δp_values = [a * m**2 for m in m_range]  # bar

# PWL-Approximation
Δp[pipe, t] = PWL_SOS2(m_flow[pipe, t], m_range, Δp_values)
```

#### 6.2.2 McCormick Envelopes

**Anwendung:** Bilineare Terme `w = x · y`

**Methode:**
```python
# Gegeben: w = x · y
# Bounds: x_min ≤ x ≤ x_max, y_min ≤ y ≤ y_max

# 4 lineare Inequalities (konvexe Hülle):
w ≥ x_min · y + y_min · x - x_min · y_min
w ≥ x_max · y + y_max · x - x_max · y_max
w ≤ x_min · y + y_max · x - x_min · y_max
w ≤ x_max · y + y_min · x - x_max · y_min
```

**Anwendung auf Temperaturmischung:**
```python
# Gegeben: Q = m · cp · (T_in - T_out)
# Mit konstantem cp: Q = m · ΔT
# Hilfsvariable: w = m · ΔT

# Bounds
m_min, m_max = 0, 100     # kg/s
ΔT_min, ΔT_max = 10, 60   # K

# McCormick
w = pyo.Var()
model.mc1 = pyo.Constraint(expr=w >= m_min * ΔT + ΔT_min * m - m_min * ΔT_min)
model.mc2 = pyo.Constraint(expr=w >= m_max * ΔT + ΔT_max * m - m_max * ΔT_max)
model.mc3 = pyo.Constraint(expr=w <= m_min * ΔT + ΔT_max * m - m_min * ΔT_max)
model.mc4 = pyo.Constraint(expr=w <= m_max * ΔT + ΔT_min * m - m_max * ΔT_min)

# Energiebilanz
Q[t] = cp * w / 1000  # MW
```

**WICHTIG:** Bounds müssen zur Laufzeit bekannt sein. Falls bounds zu konservativ → schlechte Approximation.

#### 6.2.3 2D Stückweise Linear (für Dampftafeln)

**Anwendung:** `z = f(x, y)` (z.B. Enthalpie h = f(p, T))

**Methode:**
```python
# 2D-Grid
p_points = [1, 5, 10, 20, 40]  # bar
T_points = [100, 150, 200, 250]  # °C
h_table = [[h(p,T) for T in T_points] for p in p_points]  # kJ/kg

# Bilineare Interpolation (nicht-konvex!) → Triangulation
# Oder: Separable Programming mit SOS2 in beiden Dimensionen

# Lambda-Variablen für p und T
λ_p = pyo.Var(range(len(p_points)), domain=pyo.NonNegativeReals)
λ_T = pyo.Var(range(len(T_points)), domain=pyo.NonNegativeReals)

# Constraints
p = sum(λ_p[i] * p_points[i] for i in range(len(p_points)))
T = sum(λ_T[j] * T_points[j] for j in range(len(T_points)))

# Enthalpie als separable Approximation (nicht exakt, aber konvex)
# h ≈ h_p(p) + h_T(T) - h_0
# Mit univariaten PWL für h_p und h_T

# ALTERNATIVE: Look-up Table vorberechnen
# Für alle (p_i, T_j) Kombinationen → 1D-PWL über Index
```

**Empfehlung für MILP:**
- Steam tables vorberechnen für diskrete (p, T) Kombinationen
- 1D-PWL über Index mit SOS2

#### 6.2.4 Pumpenleistung (bilinear m · Δp)

**Option A: McCormick** (wenn m und Δp beide Variablen)
```python
P_hyd = m · Δp / ρ
# McCormick mit bounds
```

**Option B: PWL über m** (wenn Δp aus Kennlinie folgt)
```python
# Da Δp = f(m) aus Pumpenkurve bekannt:
# P_el(m) = (m · f(m)) / (ρ · η(m))
#
# Vorberechnung: P_el_curve = [P_el(m_i) for m_i in m_range]
# PWL-SOS2 über m

P_el[t] = PWL_SOS2(m_flow[t], m_range, P_el_curve)
```

**Option B ist effizienter!**

---

## 7. Investitionsoptimierung ✅ ERFORDERLICH

### 7.1 Rohr-Investitionen

#### Variablen
```python
build_pipe[i, j]             # Binary: Baue Rohr zwischen i und j?
DN_selection[i, j, DN_k]     # Binary: Wähle Nennweite DN_k?
insulation_class[i, j, c]    # Binary: Wähle Isolationsklasse c?
```

#### Constraints
```python
# 1. Rohr existiert nur wenn gebaut
m_flow[i, j, t] ≤ m_max · build_pipe[i, j]

# 2. Genau eine Nennweite (falls gebaut)
sum(DN_selection[i, j, DN_k] for DN_k in DN_catalog) == build_pipe[i, j]

# 3. Durchmesser aus Auswahl
D[i, j] = sum(DN_selection[i, j, DN_k] · DN_k for DN_k in DN_catalog)

# 4. Genau eine Isolationsklasse
sum(insulation_class[i, j, c] for c in classes) == build_pipe[i, j]
```

#### Kosten
```python
# CAPEX
CAPEX_pipe[i, j] = sum(
    DN_selection[i, j, DN_k] · (
        fixed_cost[DN_k] +                          # EUR (Armaturen)
        length[i, j] · var_cost_per_m[DN_k]         # EUR/m (Rohr)
    )
    for DN_k in DN_catalog
) + sum(
    insulation_class[i, j, c] · length[i, j] · insulation_cost[c]
    for c in classes
)

# OPEX (Wärmeverluste)
OPEX_pipe[i, j] = sum(Q_loss[i, j, t] · heat_cost[t] for t in time)
```

### 7.2 Pumpen-Investitionen

```python
build_pump[location]                    # Binary: Baue Pumpe?
pump_size[location, size_k]             # Binary: Wähle Größe?

# Kosten
CAPEX_pump = sum(
    pump_size[loc, k] · (fixed_cost[k] + var_cost[k])
    for loc in locations for k in sizes
)

OPEX_pump = sum(P_el[loc, t] · electricity_cost[t] for loc in locations for t in time)
```

### 7.3 Multi-Period Investment

```python
# Investitionen in verschiedenen Perioden (z.B. 2025, 2030, 2035)
build_pipe[i, j, period]     # Binary: Baue in Periode p?

# Constraint: Einmal gebaut bleibt gebaut
build_pipe[i, j, p] ≤ sum(build_pipe[i, j, p'] for p' in periods if p' ≤ p)

# NPV (Net Present Value)
discount_factor[p] = 1 / (1 + discount_rate)**year[p]
NPV = sum(
    discount_factor[p] · (CAPEX[p] + OPEX[p])
    for p in periods
)
```

---

## 8. Solver-Anforderungen ✅

### 8.1 MILP-Formulierung

**Alle Constraints MÜSSEN linear sein!**

Checklist:
- [x] Keine `x²` Terme → PWL
- [x] Keine `x·y` Terme → McCormick oder PWL
- [x] Keine `exp()`, `ln()`, `sin()` → PWL oder diskret
- [x] Keine `if-then-else` → Binary + Big-M
- [x] Keine `min()`, `max()` → Binary + Constraints

### 8.2 Gurobi-spezifische Features

```python
# SOS2-Constraints (native support)
model.sos_constraint = pyo.SOSConstraint(var=λ, sos=2)

# Indicator Constraints (effizienter als Big-M)
# IF build_pipe[i,j] == 0 THEN m_flow[i,j,t] == 0
model.indicator = pyo.Constraint(
    expr=pyo.implies(build_pipe[i,j] == 0, m_flow[i,j,t] == 0)
)

# Piecewise Linear (automatisch)
model.pwl = pyo.Piecewise(
    y, x,  # Variablen
    pw_pts=x_points,
    pw_constr_type='EQ',
    f_rule=y_points
)
```

### 8.3 Performance-Optimierung

```python
# Warm Start (Rolling Horizon)
# Vorherige Lösung als Start für nächstes Fenster
for var in model.component_objects(pyo.Var):
    for index in var:
        var[index].value = previous_solution[var.name][index]

# Relative Gap Toleranz
solver.options['MIPGap'] = 0.01  # 1% Optimalität

# Time Limit
solver.options['TimeLimit'] = 3600  # 1 Stunde

# Threads
solver.options['Threads'] = 8
```

---

## 9. Konfiguration & Daten ✅

### 9.1 Netzwerk-Topologie (YAML)

```yaml
# config/network_topology.yaml
nodes:
  - id: "CHP_01"
    type: "producer"
    coords: {x: 0, y: 0, z: 0}
    networks: ["dh_ht_supply", "dh_ht_return"]

  - id: "District_A"
    type: "consumer"
    coords: {x: 2000, y: 1500, z: 5}
    networks: ["dh_ht_supply", "dh_ht_return"]
    demand_profile: "profiles/district_a_heat.csv"

  - id: "Junction_01"
    type: "junction"
    coords: {x: 1000, y: 800, z: 2}

pipes:
  - id: "pipe_001"
    from: "CHP_01"
    to: "Junction_01"
    network: "dh_ht_supply"
    length: 1280.6  # m (auto-calculated from coords if omitted)
    invest: true
    DN_options: [100, 150, 200, 250]

  - id: "pipe_001_return"
    from: "Junction_01"
    to: "CHP_01"
    network: "dh_ht_return"
    length: 1280.6
    invest: true
    DN_options: [100, 150, 200, 250]

pumps:
  - id: "pump_main_01"
    at_node: "CHP_01"
    network: "dh_ht_supply"
    invest: true
    sizes: ["small", "medium", "large"]
```

### 9.2 Technologie-Kataloge

```yaml
# config/tech_catalog_pipes.yaml
pipe_catalog:
  DN100:
    diameter_inner: 0.1      # m
    diameter_outer: 0.125    # m
    roughness: 0.05          # mm (Stahl)
    cost_per_m: 150          # EUR/m

  DN150:
    diameter_inner: 0.15
    diameter_outer: 0.175
    roughness: 0.05
    cost_per_m: 220

insulation_catalog:
  standard:
    U_value: 0.4             # W/(m²·K)
    cost_per_m: 50           # EUR/m

  premium:
    U_value: 0.2
    cost_per_m: 120
```

```yaml
# config/tech_catalog_pumps.yaml
pump_catalog:
  small:
    m_flow_nominal: 10       # kg/s
    Δp_max: 5                # bar
    efficiency_curve:
      m_flow: [0, 5, 10, 15]
      eta: [0.3, 0.75, 0.80, 0.70]
    cost_fixed: 5000         # EUR
    cost_variable: 500       # EUR/kW

  medium:
    m_flow_nominal: 50
    Δp_max: 8
    efficiency_curve:
      m_flow: [0, 20, 50, 80]
      eta: [0.3, 0.78, 0.85, 0.75]
    cost_fixed: 15000
    cost_variable: 400
```

### 9.3 Zeitreihen

```csv
# profiles/district_a_heat.csv
timestamp,Q_demand_MW
2024-01-01 00:00,2.5
2024-01-01 01:00,2.3
2024-01-01 02:00,2.1
...
```

```csv
# profiles/soil_temperature.csv
hour_of_year,T_soil_C
1,8.2
2,8.2
3,8.1
...
```

---

## 10. Validierung & Tests ✅

### 10.1 Physikalische Konsistenz

```python
# Test 1: Massenbilanz an jedem Knoten
def test_mass_balance(solution):
    for node in nodes:
        m_in = sum(solution['m_flow'][pipe] for pipe in node.incoming)
        m_out = sum(solution['m_flow'][pipe] for pipe in node.outgoing)
        m_consumed = solution['m_consumed'][node]
        assert abs(m_in - m_out - m_consumed) < 1e-6

# Test 2: Energiebilanz an jedem Knoten
def test_energy_balance(solution):
    for node in nodes:
        E_in = sum(solution['m_flow'][p] * cp * solution['T_in'][p] for p in node.incoming)
        E_out = sum(solution['m_flow'][p] * cp * solution['T_out'][p] for p in node.outgoing)
        Q_consumed = solution['Q_demand'][node]
        assert abs(E_in - E_out - Q_consumed) < 1e-3  # MW

# Test 3: Druckpfad-Konsistenz
def test_pressure_path(solution):
    for pipe in pipes:
        assert solution['p_in'][pipe] >= solution['p_out'][pipe]  # Druckverlust ≥ 0
```

### 10.2 Linearisierungs-Genauigkeit

```python
# Test: PWL-Approximation Genauigkeit
def test_pwl_accuracy():
    m_test = np.linspace(0, 100, 1000)
    Δp_exact = a * m_test**2
    Δp_approx = pwl_approximation(m_test)

    relative_error = abs(Δp_exact - Δp_approx) / Δp_exact
    assert max(relative_error) < 0.02  # < 2% Fehler
```

### 10.3 Vergleich mit TESpy (optional)

```python
# Validierung gegen TESpy-Simulation
def test_vs_tespy():
    # 1. Löse mit EnerGIS (MILP)
    solution_milp = solve_energis(config)

    # 2. Extrahiere Topologie & Parameter
    tespy_network = convert_to_tespy(solution_milp)

    # 3. Simuliere mit TESpy (nichtlinear)
    solution_tespy = tespy_network.solve('design')

    # 4. Vergleiche
    for pipe in pipes:
        # Massenstrom
        assert abs(solution_milp['m'][pipe] - solution_tespy.results[pipe]['m']) < 0.1  # kg/s

        # Temperatur
        assert abs(solution_milp['T_out'][pipe] - solution_tespy.results[pipe]['T_out']) < 1  # K

        # Druck
        assert abs(solution_milp['p_out'][pipe] - solution_tespy.results[pipe]['p_out']) < 0.1  # bar
```

---

## 11. Erweiterung: Kältenetze & Wärmerückgewinnung ✅

### 11.1 Kältenetze (District Cooling)

**Motivation:** Moderne Energiesysteme benötigen sowohl Wärme als auch Kälte (Klimatisierung, Prozess-Kühlung, Rechenzentren).

#### Neue Netzwerk-Typen
- [ ] **Cooling Network Definition**
  - `network_type: "cooling"` (zusätzlich zu "heating")
  - Typische Parameter: T_supply = 6-8°C, T_return = 12-16°C
  - Gleiche physikalische Modellierung wie Wärmenetze
  - Unterschied: Wärmegewinne statt Verluste (Umgebung wärmer als Netz)

#### Kälte-Komponenten
- [ ] **Chiller (Kältemaschine)**
  - Kompressionskältemaschine (elektrisch): Q_cold = COP · P_el
  - Absorptionskältemaschine (thermisch): Q_cold / Q_heat_in
  - COP temperaturabhängig: COP = f(T_evap, T_cond)
  - Linearisierung: 2D-PWL für COP(T_evap, T_cond)
  - Investment in Chiller-Größe
  - Datei: `energis/models/blocks/cooling/chiller.py`

- [ ] **Cooling Tower (Rückkühler)**
  - Verdunstungskühlung (wet) oder Trockenkühlung (dry)
  - Wärmeabfuhr an Umgebung
  - Kühlgrenze: T_wetbulb (wet) oder T_ambient (dry)
  - Lüfterleistung: P_fan = α · Q_reject (α ≈ 0.01-0.03)
  - Datei: `energis/models/blocks/cooling/cooling_tower.py`

- [ ] **Free Cooling Unit**
  - Natürliche Kältequellen: Grundwasser, Fluss/See, Außenluft
  - Wärmeübertrager zwischen Quelle und Kältenetz
  - Verfügbarkeit abhängig von T_source[t]
  - Minimale Betriebskosten (nur Pumpen)
  - Binary: is_active[t] (nur bei ausreichend niedriger T_source)
  - Datei: `energis/models/blocks/cooling/free_cooling.py`

### 11.2 Wärmerückgewinnung (Heat Recovery)

**Motivation:** Nutzung von Abwärme aus Prozessen, Rechenzentren, Kühlung für Wärmenetze.

#### Heat Recovery Unit
- [ ] **Abwärmequellen**
  - Industrieprozesse (80-200°C): Direkte Einspeisung möglich
  - Rechenzentren (30-50°C): Wärmepumpe erforderlich
  - Abwasser (20-30°C): Wärmepumpe mit niedrigem COP
  - Kühlprozesse: Variable Temperaturen

- [ ] **Integration**
  - **Fall A:** T_waste hoch → Direkter Wärmeübertrager ins Wärmenetz
  - **Fall B:** T_waste niedrig → Wärmepumpe zur Temperaturanhebung
  - Binary: use_heatpump[t] abhängig von T_waste vs. T_heat_net
  - Energiebilanz: Q_recovered = ε_HEX · m_waste · cp · ΔT
  - Datei: `energis/models/blocks/heat_recovery/heat_recovery_unit.py`

### 11.3 Wärme-Kälte-Kopplung

**Systemintegration:**
```
Wärmepumpe (zentral)
├─ Verdampfer @ Kältenetz (8°C) → Kälte für Klimatisierung
└─ Kondensator @ Wärmenetz (55°C) → Wärme für Heizung

Quellen:
- Free Cooling (Grundwasser)
- Chiller (Backup)
- Abwärme (Rechenzentrum, Industrie)
```

#### Erweiterte Wärmepumpen-Modellierung
- [ ] **Bidirektionale Wärmepumpe**
  - mode[t] ∈ {0, 1}: 0 = Heizen, 1 = Kühlen
  - Heizmodus: Kälte-Quelle → Wärme-Senke
  - Kühlmodus: Wärme-Quelle → Kälte-Senke (reversibel)
  - Unterschiedliche COP/EER je Modus

- [ ] **Multi-Netz-Anbindung**
  - heat_network: ID des Wärmenetzes
  - cold_network: ID des Kältenetzes
  - Flows zu beiden Netzen registrieren
  - Erweitere existierende HeatPumpBlock

### 11.4 Physikalische Besonderheiten Kältenetz

**Unterschiede zu Wärmenetzen:**

| **Aspekt** | **Wärmenetz** | **Kältenetz** |
|------------|---------------|---------------|
| Vorlauftemperatur | 55-120°C | 6-12°C |
| Wärmeverluste | Nachteilig | Vorteilhaft! (Kühlung durch Umgebung) |
| Energiebilanz Rohr | T_out < T_in | T_out > T_in (Erwärmung) |
| Isolierung | Hochwertig | Reduziert (Kondensat-Schutz) |

**Modellierung:**
```python
# Wärmegewinne bei Kältenetz (Vorzeichen!)
Q_gain[t] = U · π · D · L · (T_ambient - T_pipe[t])  # > 0

# Energiebilanz
m · cp · (T_out[t] - T_in[t]) = Q_gain[t]
# T_out > T_in (statt T_out < T_in bei Wärme)
```

**WICHTIG:** Gleiche Gleichungen, nur Vorzeichen beachten!

### 11.5 Neue Kataloge & Konfiguration

**Chiller-Katalog:**
```yaml
# config/catalogs/chillers.yaml
chiller_catalog:
  compression_small:
    Q_cold_nominal: 1  # MW
    COP_nominal: 5
    COP_curve:  # 2D über (T_evap, T_cond)
      T_evap: [4, 6, 8, 10]
      T_cond: [25, 30, 35, 40]
      COP_values: [[5.5, 5.0, 4.5, 4.0], ...]
    cost_fixed: 200000  # EUR
    cost_variable: 150000  # EUR/MW
```

**Multi-Netz-Konfiguration:**
```yaml
# config/networks/heating_cooling_system.yaml
networks:
  - id: "heat_net"
    network_type: "heating"
    T_supply: 55
    T_return: 35

  - id: "cold_net"
    network_type: "cooling"
    T_supply: 8
    T_return: 12

  - id: "waste_heat_net"
    network_type: "heating"
    T_supply: 35
    T_return: 25

interfaces:
  - component: "heat_pump_central"
    connects: ["cold_net", "heat_net"]
  - component: "heat_recovery_datacenter"
    connects: ["waste_heat_net", "heat_net"]
```

### 11.6 Implementierungsaufwand

**Zusätzlich zu Basis-Implementierung:**

| **Komponente** | **Zeilen** | **Aufwand** |
|----------------|------------|-------------|
| Chiller | ~350 | 4 Tage |
| Cooling Tower | ~250 | 2 Tage |
| Free Cooling | ~300 | 3 Tage |
| Heat Recovery Unit | ~400 | 4 Tage |
| HeatPump Extension | ~100 | 2 Tage |
| Tests | - | 2 Tage |
| Kataloge | ~200 | 1 Tag |
| **SUMME** | **~1600** | **18 Tage ≈ 3 Wochen** |

**Zeitrahmen Cooling & Heat Recovery: 3 Wochen** (zusätzlich zur Basis)

---

## 12. Erweiterung: Saisonale Wärmespeicher ✅

### 12.1 Motivation & Anwendung

**Problem:** Erneuerbare Energie (Solar, Wind) ist saisonal verfügbar, aber Wärmebedarf ist im Winter am höchsten.

**Lösung:** Große saisonale Speicher (50.000+ m³) zum Ausgleich zwischen Sommer und Winter.

```
Sommer:                    Winter:
Solar → [PTES] → Verluste  [PTES] → Wärmenetz
        ↓                   ↑
     Ladung              Entladung
```

**Typische Anwendungen:**
- Solare Fernwärme mit Sommerüberschuss
- Wärmepumpen mit niedrigen Strompreisen im Sommer
- Industrielle Abwärme-Speicherung
- Campus-Energiesysteme

### 12.2 Erdbeckenspeicher (Pit Thermal Energy Storage - PTES)

#### Beschreibung
Große isolierte Becken im Erdreich gefüllt mit Wasser.

**Technische Parameter:**
- Volumen: 50.000 - 200.000 m³
- Temperatur: 40-95°C
- Speicherdauer: Wochen bis Monate
- Verlustrate: 5-15% pro Monat
- Reale Projekte: Dronninglund (Dänemark), Marstal (Dänemark)

#### Variablen
```python
# Monatliche Zeitschritte (statt stündlich)
months = 12

SOC[month]               # State of Charge [m³ gespeichert]
E_stored[month]          # Energieinhalt [MWh]
T_storage[month]         # Durchschnittstemperatur [°C]
Q_charge[month]          # Ladeleistung [MWh/Monat]
Q_discharge[month]       # Entladeleistung [MWh/Monat]
Q_loss[month]            # Wärmeverlust [MWh/Monat]

# Investment
build_ptes               # Binary: Baue PTES?
V_max                    # Maximales Volumen [m³] - diskret
```

#### Parameter
```python
# Geometrie
A_surface                # Oberfläche [m²] = f(V_max)
depth                    # Tiefe [m] = f(V_max)

# Thermische Eigenschaften
ρ = 971.8                # Dichte Wasser [kg/m³] @ 90°C
cp = 4.19                # Spezifische Wärmekapazität [kJ/(kg·K)]
U_ptes = 0.3             # Wärmedurchgangskoeffizient [W/(m²·K)]

# Umgebung
T_soil[month]            # Erdreichtemperatur [°C] - saisonal

# Grenzen
T_min = 40               # °C
T_max = 95               # °C
Q_charge_rate_max = V_max · 0.1  # Max. 10% des Volumens pro Monat
Q_discharge_rate_max = V_max · 0.1
```

#### Constraints

1. **Energiebilanz**
   ```python
   # Dynamik (monatlich)
   E_stored[month+1] = E_stored[month]
                       + Q_charge[month]
                       - Q_discharge[month]
                       - Q_loss[month]

   # Anfangsbedingung
   E_stored[1] = E_stored[12]  # Zyklisch
   ```

2. **Energieinhalt aus Temperatur**
   ```python
   # E = m · cp · ΔT
   E_stored[month] = SOC[month] · ρ · cp · (T_storage[month] - T_ambient) / 1000
   # in MWh
   ```

3. **Wärmeverluste**
   ```python
   # Verluste an Erdreich (temperaturabhängig)
   Q_loss[month] = U_ptes · A_surface · (T_storage[month] - T_soil[month])
                   · hours_per_month / 1000

   # Mit hours_per_month = 730 (ca.)
   # Beispiel: A_surface ≈ (V_max / depth)^(2/3) für zylindrisches Becken
   ```

4. **Kapazitätsgrenzen**
   ```python
   # State of Charge
   0 ≤ SOC[month] ≤ V_max

   # Temperatur
   T_min ≤ T_storage[month] ≤ T_max

   # Lade-/Entladerate
   0 ≤ Q_charge[month] ≤ Q_charge_rate_max
   0 ≤ Q_discharge[month] ≤ Q_discharge_rate_max
   ```

5. **Investment-Logik**
   ```python
   # Nur aktiv wenn gebaut
   SOC[month] ≤ V_max · build_ptes
   Q_charge[month] ≤ Q_charge_rate_max · build_ptes
   Q_discharge[month] ≤ Q_discharge_rate_max · build_ptes

   # Diskrete Größenauswahl
   V_max ∈ {0, 50000, 100000, 200000}  # m³

   # Oder: Kontinuierlich mit Mindestgröße
   V_max ≥ 50000 · build_ptes
   V_max ≤ 200000 · build_ptes
   ```

6. **Kopplung mit Wärmenetz**
   ```python
   # Laden: Wärme aus Netz in Speicher
   Q_charge[month] = Σ(Q_to_storage[day] for day in month)

   # Entladen: Wärme aus Speicher ins Netz
   Q_discharge[month] = Σ(Q_from_storage[day] for day in month)

   # Tägliche Detaillierung (optional):
   # Falls tägliche Auflösung erforderlich:
   SOC_daily[day+1] = SOC_daily[day] + ΔQ_daily[day]
   # Dann: SOC[month] = average(SOC_daily[day] for day in month)
   ```

#### Kosten
```python
# CAPEX
CAPEX_ptes = build_ptes · (
    cost_fixed                                    # EUR (Planung, Genehmigung)
    + V_max · cost_per_m3                        # EUR/m³ (Aushub, Isolierung)
    + A_surface · cost_lining_per_m2             # EUR/m² (Abdichtung)
)

# Typische Werte:
# cost_fixed = 500,000 EUR
# cost_per_m3 = 50-100 EUR/m³
# cost_lining_per_m2 = 50 EUR/m²

# OPEX
OPEX_ptes = V_max · cost_maintenance_per_m3_year  # EUR/Jahr
# Typisch: 0.5-1 EUR/(m³·Jahr)

# Wärmeverluste gehen in Gesamt-OPEX ein (Opportunitätskosten)
```

#### LINEARISIERUNG

**Bilineare Terme:**
- `SOC[month] · T_storage[month]` in Energieinhalt
- `T_storage[month] - T_soil[month]` ist linear (beide Parameter/Variablen)

**Methode:**
```python
# McCormick Envelopes für E_stored = SOC · ΔT

# Bounds
SOC_min, SOC_max = 0, V_max
T_min, T_max = 40, 95

# Hilfsvariable w = SOC · T_storage
# 4 McCormick-Inequalities:
w ≥ T_min · SOC + SOC_min · T_storage - T_min · SOC_min
w ≥ T_max · SOC + SOC_max · T_storage - T_max · SOC_max
w ≤ T_min · SOC + SOC_max · T_storage - T_min · SOC_max
w ≤ T_max · SOC + SOC_min · T_storage - T_max · SOC_min

# Dann: E_stored[month] = ρ · cp · (w - SOC · T_ambient) / 1000
```

**Vereinfachung (Alternative):**
```python
# Annahme: Temperatur folgt direkt aus SOC (Schichtung)
# T_storage ≈ f(SOC/V_max)  # Monotone Funktion
# → PWL-Approximation

# Stützstellen
SOC_frac_pts = [0, 0.25, 0.5, 0.75, 1.0]
T_storage_pts = [40, 55, 70, 82, 95]  # °C

# PWL mit SOS2
T_storage[month] = PWL_SOS2(SOC[month]/V_max, SOC_frac_pts, T_storage_pts)
```

---

### 12.3 Aquifer Thermal Energy Storage (ATES)

#### Beschreibung
Grundwasser als saisonaler Speicher mit Warm- und Kaltbohrloch.

```
Warm:  Bohrloch_warm ↔ Aquifer ↔ Bohrloch_kalt
Kalt:  Umkehrung
```

**Technische Parameter:**
- Kapazität: 10-100 GWh
- ΔT: 5-15 K
- Recovery Efficiency: 60-90% (geologieabhängig)
- Tiefe: 50-300 m
- Typische Anwendung: Großstädte, Campus

#### Variablen
```python
# Zwei "Speicherseiten"
T_warm_well[month]       # Temperatur warmes Bohrloch [°C]
T_cold_well[month]       # Temperatur kaltes Bohrloch [°C]
E_stored_warm[month]     # Energie im warmen Bereich [MWh]
E_stored_cold[month]     # Energie im kalten Bereich [MWh]

Q_charge[month]          # Wärme ins warme Bohrloch [MWh/Monat]
Q_discharge[month]       # Wärme aus warmem Bohrloch [MWh/Monat]
m_flow_charge[month]     # Massenstrom beim Laden [kg/s avg]
m_flow_discharge[month]  # Massenstrom beim Entladen [kg/s avg]

# Investment
build_ates               # Binary: Baue ATES?
num_well_pairs           # Anzahl Bohrlochpaare [diskret]
```

#### Parameter
```python
# Geologische Eigenschaften
aquifer_thickness = 50   # m (Mächtigkeit)
porosity = 0.3           # Porosität
thermal_conductivity     # W/(m·K) (Gestein)
η_recovery = 0.7         # Recovery Efficiency [-]

# Grenzen
T_warm_min = 15          # °C
T_warm_max = 25          # °C
T_cold_min = 5           # °C
T_cold_max = 15          # °C
m_flow_max_per_well = 20 # kg/s
```

#### Constraints

1. **Energiebilanz Warm-Seite**
   ```python
   # Ladung: Wärme rein
   Q_charge[month] = m_flow_charge[month] · cp
                     · (T_in_charge - T_warm_well[month])
                     · hours_per_month / 1000

   # Entladung: Wärme raus
   Q_discharge[month] = m_flow_discharge[month] · cp
                        · (T_warm_well[month] - T_return)
                        · hours_per_month / 1000
   ```

2. **Dynamik**
   ```python
   # Vereinfachtes Modell
   E_stored_warm[month+1] = E_stored_warm[month]
                            + Q_charge[month]
                            - Q_discharge[month] / η_recovery
                            - Q_loss_underground[month]

   # Untergrund-Verluste (geologieabhängig)
   Q_loss_underground[month] = α · E_stored_warm[month]
   # Mit α ≈ 0.05-0.1 (5-10% pro Monat)
   ```

3. **Temperatur-Grenzen**
   ```python
   T_warm_min ≤ T_warm_well[month] ≤ T_warm_max
   T_cold_min ≤ T_cold_well[month] ≤ T_cold_max

   # Mindestdifferenz (für Effizienz)
   T_warm_well[month] - T_cold_well[month] ≥ ΔT_min  # z.B. 5K
   ```

4. **Kapazität**
   ```python
   # Maximale Energie abhängig von Anzahl Bohrungen
   E_max = num_well_pairs · E_per_well_pair

   # Mit E_per_well_pair aus Geologie:
   # E = V_aquifer · ρ · cp · ΔT
   # V_aquifer = A_influence · aquifer_thickness · porosity
   ```

5. **Investment**
   ```python
   # Anzahl Bohrlochpaare
   num_well_pairs ∈ {1, 2, 3, 4, 5}

   # Nur wenn gebaut
   num_well_pairs ≥ 1 · build_ates
   num_well_pairs ≤ 5 · build_ates
   ```

#### Kosten
```python
# CAPEX
CAPEX_ates = build_ates · cost_fixed
             + num_well_pairs · (
                 2 · cost_per_borehole                # 2 Bohrungen pro Paar
                 + cost_pumps
                 + cost_heat_exchanger
             )

# Typische Werte:
# cost_fixed = 200,000 EUR (Genehmigung, Planung)
# cost_per_borehole = 100,000-300,000 EUR (abhängig von Tiefe)
# cost_pumps = 50,000 EUR
# cost_heat_exchanger = 30,000 EUR

# OPEX
OPEX_ates = P_pump_total · electricity_cost  # Pumpen-Energieverbrauch
```

#### LINEARISIERUNG

**Ähnlich wie PTES:** McCormick für bilineare Terme `m_flow · T`.

**Vereinfachung:**
```python
# Falls T_warm_well nur schwach variiert:
# T_warm_well ≈ const. → dann linear

# ODER: Vorberechnung von Betriebspunkten
# (T_warm, T_cold, m_flow) → Q_charge/discharge
# → Lookup-Table → PWL
```

---

### 12.4 Integration mit Wärmenetz

#### Zeitliche Auflösung

**Problem:** Netzwerkmodell arbeitet stündlich (8760 h/a), aber saisonale Speicher sind monatlich sinnvoller.

**Lösung:**

```python
# Hybrid-Modell:

# Stündliche Variablen (Netz, Komponenten)
T = pyo.RangeSet(1, 8760)  # Stunden

# Monatliche Variablen (Saisonalspeicher)
M = pyo.RangeSet(1, 12)    # Monate

# Kopplung:
# Q_charge_monthly[month] = Σ(Q_to_storage[hour] for hour in month)

# Mapping hour → month
month_of_hour = {
    1: 1, 2: 1, ..., 744: 1,      # Januar
    745: 2, ..., 1416: 2,          # Februar
    ...
}

# Constraint
for month in M:
    hours_in_month = [h for h in T if month_of_hour[h] == month]

    model.charge_aggregation[month] = pyo.Constraint(
        expr=Q_charge_monthly[month] == sum(Q_to_storage[h] for h in hours_in_month)
    )
```

**Alternative:** Representative Days

```python
# Statt 8760 h: 12 Monate × 3 repräsentative Tage = 36 Tage × 24 h = 864 h
# → Reduktion um Faktor 10, aber weniger Genauigkeit
```

#### Anbindung an Netzwerk

**PTES/ATES als Komponente:**

```python
# Ähnlich wie ThermalStorage, aber:
# - Monatliche statt stündliche Dynamik
# - Größere Kapazität
# - Höhere Verluste

# Flows:
# - Charging Flow: Wärme ins Speicher
#   → Senke am Wärmenetz (z.B. bei Überproduktion Solar)
#
# - Discharging Flow: Wärme aus Speicher
#   → Quelle am Wärmenetz (z.B. bei hoher Nachfrage Winter)
```

**Beispiel-Konfiguration:**

```yaml
# config: seasonal_storage.yaml

seasonal_storage:
  - id: "ptes_solar_1"
    type: "PTES"
    network: "dh_ht"

    # Investment
    invest: true
    V_options: [50000, 100000, 200000]  # m³

    # Parameter
    T_min: 40
    T_max: 95
    U_value: 0.3  # W/(m²·K)

    # Kosten
    cost_fixed: 500000  # EUR
    cost_per_m3: 75     # EUR/m³
    cost_lining_per_m2: 50  # EUR/m²

  - id: "ates_campus_1"
    type: "ATES"
    network: "dh_lt"

    # Investment
    invest: true
    num_well_pairs_options: [1, 2, 3, 4]

    # Geologie
    aquifer_thickness: 50  # m
    porosity: 0.3
    η_recovery: 0.7

    # Kosten
    cost_per_borehole: 200000  # EUR
```

---

### 12.5 Anwendungsbeispiel: Solare Fernwärme mit PTES

**System:**

```
[Solarthermie 10 MW_peak]
         ↓
    [Wärmenetz HT 90°C]
         ↓
    ┌─────────┐
    │  PTES   │ ← Sommer: Überschuss speichern
    │ 100,000 │   Winter: Entladen
    │   m³    │
    └─────────┘
         ↓
   [Verbraucher]
         ↑
    [Gas-Kessel] ← Backup
```

**Optimierungsziel:**

Minimiere: `CAPEX_solar + CAPEX_ptes + CAPEX_boiler + OPEX_total`

Subject to:
- Wärmenachfrage zu jeder Stunde gedeckt
- PTES speichert Sommerüberschuss
- PTES entlädt im Winter
- Gas-Kessel als Backup

**Erwartetes Ergebnis:**

- Solare Deckung: 60-80% (mit PTES) vs. 20-30% (ohne PTES)
- PTES-Größe: 80,000-120,000 m³ (optimal)
- NPV: Positiv bei CAPEX < 80 EUR/m³

---

### 12.6 Validierung & Wissenschaftliche Basis

**Reale Projekte:**

| **Projekt** | **Land** | **Typ** | **Volumen** | **T** | **Solar-Anteil** |
|-------------|----------|---------|-------------|-------|------------------|
| Dronninglund | DK | PTES | 60,000 m³ | 40-80°C | 50% |
| Marstal | DK | PTES | 75,000 m³ | 45-85°C | 55% |
| Brædstrup | DK | PTES | 70,000 m³ | 50-90°C | 60% |
| Utrecht Uni | NL | ATES | ~30 GWh | 10-20°C | - |

**Wissenschaftliche Publikationen:**

- *Applied Energy* 302 (2021): "Seasonal pit thermal energy storage for solar district heating: Design and optimization"
- *Renewable Energy* 198 (2022): "Aquifer thermal energy storage in combination with solar thermal collectors and heat pumps"
- *Energy Conversion and Management* 274 (2022): "Techno-economic analysis of seasonal thermal energy storage for district heating"

---

### 12.7 Implementierungsaufwand

**Zusätzlich zu Basis + Cooling:**

| **Komponente** | **Zeilen** | **Aufwand** |
|----------------|------------|-------------|
| PTES Block | ~400 | 4 Tage |
| ATES Block | ~450 | 5 Tage |
| Monatliche Aggregation | ~150 | 2 Tage |
| Tests | - | 2 Tage |
| Kataloge | ~100 | 1 Tag |
| **SUMME** | **~1100** | **14 Tage ≈ 2 Wochen** |

**Neuer Gesamt-Zeitrahmen: 10-12 Wochen** (statt 8-10 Wochen)

---

## 13. Zusammenfassung: Was ist drin? ✅❌

| **Anforderung** | **Vollständig?** | **Priorität** |
|-----------------|------------------|---------------|
| Vorlauf/Rücklauf-Topologie | ✅ JA | 🔴 HOCH |
| Wärmeverluste (detailliert) | ✅ JA | 🔴 HOCH |
| Linearität aller Constraints | ✅ JA | 🔴 KRITISCH |
| Druck-Modellierung | ✅ JA | 🔴 HOCH |
| Temperatur-Modellierung | ✅ JA | 🔴 HOCH |
| Massenstrom/Durchfluss | ✅ JA | 🔴 HOCH |
| Rohre als Komponenten | ✅ JA | 🔴 HOCH |
| Pumpen als Komponenten | ✅ JA | 🔴 HOCH |
| Pumpen-Energieverbrauch | ✅ JA | 🔴 HOCH |
| Multi-Temperatur-Netze | ✅ JA | 🟡 MITTEL |
| Geografische Abhängigkeiten | ✅ JA | 🔴 HOCH |
| Punktuelle Verbraucher | ✅ JA | 🔴 HOCH |
| Verteilte Verbraucher | ✅ JA | 🟡 MITTEL |
| Dampf-Komponenten | ✅ JA | 🟢 NIEDRIG |
| Investitionsoptimierung | ✅ JA | 🔴 HOCH |
| Validierung & Tests | ✅ JA | 🔴 HOCH |
| **ERWEITERUNG:** Kältenetze | ✅ JA | 🟡 MITTEL |
| Chiller (Kältemaschine) | ✅ JA | 🟡 MITTEL |
| Cooling Tower (Rückkühler) | ✅ JA | 🟡 MITTEL |
| Free Cooling | ✅ JA | 🟡 MITTEL |
| Wärmerückgewinnung | ✅ JA | 🟡 MITTEL |
| Wärme-Kälte-Kopplung | ✅ JA | 🟡 MITTEL |
| **ERWEITERUNG:** Saisonale Speicher | ✅ JA | 🔴 HOCH |
| PTES (Erdbeckenspeicher) | ✅ JA | 🔴 HOCH |
| ATES (Aquifer-Speicher) | ✅ JA | 🔴 HOCH |
| Monatliche Zeitauflösung | ✅ JA | 🔴 HOCH |
| Integration mit Wärmenetz | ✅ JA | 🔴 HOCH |

---

## 14. Nächste Schritte

### Phase 1: Kern-Komponenten (Priorität 🔴)
1. ✅ Pipe Component (Vorlauf/Rücklauf, Druckverlust, Wärmeverlust)
2. ✅ Pump Component (Kennlinien, Energieverbrauch)
3. ✅ Thermal Node (Massenbilanz, Temperaturmischung)
4. ✅ Geographic Topology (Koordinaten, automatische Längenberechnung)
5. ✅ Point Load Consumer

### Phase 2: Erweiterte Features (Priorität 🟡)
6. ✅ Multi-Network Support (Bus-System, Interface Nodes)
7. ✅ Heat Exchanger (Kopplung zwischen Netzen)
8. ✅ Distributed Load Consumer
9. ✅ Detaillierte Wärmeverlust-Modellierung

### Phase 3: Spezialfälle (Priorität 🟢)
10. ✅ Steam Components (Turbine, Boiler, Condenser)
11. ⚠️ Multi-Period Investment Optimization
12. ⚠️ TESpy-Integration für Validierung

### Phase 4: Kältenetze & Wärmerückgewinnung (Priorität 🟡)
13. ✅ Chiller Component (Kompressions- und Absorptionskältemaschine)
14. ✅ Cooling Tower Component (Rückkühlung)
15. ✅ Free Cooling Component (Grundwasser, Außenluft)
16. ✅ Heat Recovery Unit (Abwärme-Integration)
17. ✅ Erweiterte HeatPump (Kältenetz-Anbindung, bidirektional)
18. ✅ Multi-Network Manager Update (Cooling Networks)

### Phase 5: Saisonale Wärmespeicher (Priorität 🔴)
19. ✅ PTES Component (Erdbeckenspeicher)
20. ✅ ATES Component (Aquifer-Speicher)
21. ✅ Monatliche Zeitauflösung (Hybrid-Modell)
22. ✅ Aggregation stündlich → monatlich
23. ✅ Integration mit Wärmenetz
24. ✅ Kataloge für saisonale Speicher

---

**Status:** Vollständige Spezifikation für Wärme- UND Kältenetze PLUS Saisonalspeicher!
**Zeitrahmen:** 10-12 Wochen Implementierung
