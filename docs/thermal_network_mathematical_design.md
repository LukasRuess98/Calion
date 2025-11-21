# Mathematisches Design-Dokument: Thermische Netzwerk-Erweiterung

## Inhaltsverzeichnis
1. [Notation & Konventionen](#1-notation--konventionen)
2. [Sets & Indices](#2-sets--indices)
3. [Parameter](#3-parameter)
4. [Variablen](#4-variablen)
5. [Constraints](#5-constraints)
6. [Zielfunktion](#6-zielfunktion)
7. [Linearisierungen](#7-linearisierungen)
8. [Validierung](#8-validierung)

---

## 1. Notation & Konventionen

### 1.1 Mathematische Symbole

| **Symbol** | **Bedeutung** |
|------------|---------------|
| `∀` | Für alle |
| `∈` | Element von |
| `∑` | Summe über |
| `∏` | Produkt über |
| `≤, ≥, =` | Kleiner/gleich, größer/gleich, gleich |
| `∧` | Logisches UND |
| `∨` | Logisches ODER |
| `⇒` | Implikation |

### 1.2 Variablen-Konventionen

- **Lowercase** `x, y, z`: Kontinuierliche Variablen
- **Uppercase** `X, Y`: Binary/Integer Variablen
- **Bold** `**x**`: Vektoren
- **Greek** `λ, η, ρ`: Spezielle Variablen (SOS2, Wirkungsgrad, Dichte)

### 1.3 Indizierung

- `[t]`: Zeitindex (Stunde)
- `[i], [j]`: Knotenindex
- `[p]`: Rohr-Index (pipe)
- `[n]`: Netzwerk-Index
- `[k]`: Diskrete Auswahl-Index (DN, Pumpen-Größe, etc.)

### 1.4 Einheiten

| **Größe** | **Einheit** | **Konvention** |
|-----------|-------------|----------------|
| Massenstrom | kg/s | `m_flow` |
| Druck | bar | `p` |
| Druckdifferenz | bar | `Δp` |
| Temperatur | °C | `T` |
| Wärmeleistung | MW | `Q` |
| Elektrische Leistung | MW | `P_el` |
| Länge | m | `L` |
| Durchmesser | m | `D` |
| Rohrlänge | m | `L_pipe` |
| Zeit | h | `t` |
| Kosten | EUR | `C` |

---

## 2. Sets & Indices

### 2.1 Temporale Sets

```python
T = {1, 2, ..., 8760}           # Zeitschritte (Stunden pro Jahr)
t ∈ T                            # Zeitindex
Δt = 1.0                         # Zeitschrittlänge [h]
```

### 2.2 Räumliche Sets

```python
# Knoten
N = {1, 2, ..., |N|}             # Alle Knoten
N_prod ⊆ N                       # Erzeuger-Knoten
N_cons ⊆ N                       # Verbraucher-Knoten
N_junc ⊆ N                       # Verzweigungs-Knoten
i, j ∈ N                         # Knotenindizes

# Rohre
P = {1, 2, ..., |P|}             # Alle Rohre
P_supply ⊆ P                     # Vorlauf-Rohre
P_return ⊆ P                     # Rücklauf-Rohre
p ∈ P                            # Rohrindex

# Konnektivität
P_in(i) = {p ∈ P : end_node(p) = i}      # Rohre die in Knoten i enden
P_out(i) = {p ∈ P : start_node(p) = i}   # Rohre die von Knoten i starten
```

### 2.3 Netzwerk-Sets

```python
# Netze
ℕ = {1, 2, ..., |ℕ|}             # Alle Netzwerke
n ∈ ℕ                            # Netzwerk-Index

# Beispiel:
# n=1: Hochdruck-Dampf (250°C, 40 bar)
# n=2: Fernwärme HT (90°C, 6 bar)
# n=3: Fernwärme NT (55°C, 3 bar)

# Netzwerk-spezifische Knoten/Rohre
N(n) ⊆ N                         # Knoten in Netz n
P(n) ⊆ P                         # Rohre in Netz n
```

### 2.4 Technologie-Sets

```python
# Pumpen
PUMP = {1, 2, ..., |PUMP|}       # Alle Pumpen-Standorte
PUMP_SIZE = {1, 2, ..., K_pump}  # Verfügbare Pumpen-Größen

# Rohr-Durchmesser
DN = {DN25, DN32, DN50, DN80, DN100, DN150, DN200, DN250, DN300, DN400, DN500, DN600}
k_DN ∈ DN                        # DN-Index

# Isolationsklassen
INSUL = {poor, standard, good, excellent}
k_ins ∈ INSUL                    # Isolations-Index
```

---

## 3. Parameter

### 3.1 Geografische Parameter

```python
# Koordinaten
x[i] ∈ ℝ                         # X-Koordinate von Knoten i [m]
y[i] ∈ ℝ                         # Y-Koordinate von Knoten i [m]
z[i] ∈ ℝ                         # Z-Koordinate (Höhe) von Knoten i [m]

# Rohrlängen
L[p] = √((x[end(p)] - x[start(p)])² + (y[end(p)] - y[start(p)])²)   [m]

# Höhendifferenz
Δz[p] = z[end(p)] - z[start(p)]                                      [m]
```

### 3.2 Thermophysikalische Parameter

```python
# Fluid-Eigenschaften (Wasser)
ρ = 971.8                        # Dichte [kg/m³] bei 90°C
cp = 4.19                        # Spezifische Wärmekapazität [kJ/(kg·K)]
μ = 0.000315                     # Dynamische Viskosität [Pa·s] bei 90°C
g = 9.81                         # Erdbeschleunigung [m/s²]

# Erdreich
T_soil_mean = 10.0               # Mittlere Erdreichtemperatur [°C]
T_soil_amp = 5.0                 # Amplitude Jahresgang [K]
T_soil[t] = T_soil_mean + T_soil_amp · sin(2π · (t - 2190) / 8760)  [°C]

# Umgebung
T_amb = 15.0                     # Umgebungstemperatur [°C]
```

### 3.3 Netzwerk-Parameter

```python
# Pro Netzwerk n
T_supply[n]                      # Vorlauftemperatur [°C]
T_return[n]                      # Rücklauftemperatur [°C]
p_nominal[n]                     # Nennbetriebsdruck [bar]
p_min[n]                         # Minimaler Druck [bar]
p_max[n]                         # Maximaler Druck [bar]
```

### 3.4 Rohr-Parameter

```python
# Pro Nennweite k_DN
D_inner[k_DN]                    # Innendurchmesser [m]
D_outer[k_DN]                    # Außendurchmesser [m]
k_rough[k_DN]                    # Absolute Rauheit [mm]
cost_per_m[k_DN]                 # Kosten [EUR/m]
cost_fixed[k_DN]                 # Fixkosten (Armaturen) [EUR]

# Pro Isolationsklasse k_ins
U_value[k_ins]                   # Wärmedurchgangskoeffizient [W/(m²·K)]
cost_insul[k_ins]                # Zusatzkosten [EUR/m]
```

### 3.5 Pumpen-Parameter

```python
# Pro Pumpen-Größe k_pump
m_flow_nominal[k_pump]           # Nenn-Massenstrom [kg/s]
Δp_max[k_pump]                   # Maximale Druckerhöhung [bar]
cost_pump_fixed[k_pump]          # Fixkosten [EUR]
cost_pump_var[k_pump]            # Variable Kosten [EUR/kW]

# Kennlinien (Stützstellen)
m_pump_pts[k_pump] = [m₁, m₂, ..., m_M]                # [kg/s]
Δp_pump_pts[k_pump] = [Δp₁, Δp₂, ..., Δp_M]            # [bar]
η_pump_pts[k_pump] = [η₁, η₂, ..., η_M]                # [-]
```

### 3.6 Verbraucher-Parameter

```python
# Punktuelle Last
Q_demand[i, t]                   # Wärmebedarf an Knoten i, Zeit t [MW]
T_return_demand[i]               # Rücklauftemperatur vom Verbraucher [°C]

# Verteilte Last
Q_distributed[p, t]              # Gesamtlast auf Rohr p [MW]
q_line[p, t] = Q_distributed[p, t] / L[p]               # Linienlast [MW/m]
```

### 3.7 Kosten-Parameter

```python
# Brennstoff & Elektrizität
c_el[t]                          # Strompreis [EUR/MWh]
c_heat                           # Wärmepreis (für Verluste) [EUR/MWh]

# Annualisierung
r = 0.04                         # Diskontsatz [-]
n_years = 30                     # Lebensdauer [Jahre]
CRF = r · (1+r)^n_years / ((1+r)^n_years - 1)           # Capital Recovery Factor
```

---

## 4. Variablen

### 4.1 Rohrvariablen

#### 4.1.1 Kontinuierliche Variablen

```python
# Hydraulisch
m_flow[p, t] ∈ ℝ₊                # Massenstrom durch Rohr p [kg/s]
p_in[p, t] ∈ [p_min, p_max]      # Eingangsdruck [bar]
p_out[p, t] ∈ [p_min, p_max]     # Ausgangsdruck [bar]
Δp[p, t] ∈ ℝ₊                    # Druckverlust [bar]

# Thermisch
T_in[p, t] ∈ [T_min, T_max]      # Eingangstemperatur [°C]
T_out[p, t] ∈ [T_min, T_max]     # Ausgangstemperatur [°C]
Q_loss[p, t] ∈ ℝ₊                # Wärmeverlust [MW]

# Hilfsvariablen für Linearisierung
w_mT[p, t] ∈ ℝ                   # Produkt m_flow · T (McCormick)
```

#### 4.1.2 Investment-Variablen

```python
# Binary
build_pipe[p] ∈ {0, 1}           # 1 = Rohr wird gebaut
select_DN[p, k_DN] ∈ {0, 1}      # 1 = Nennweite k_DN gewählt
select_insul[p, k_ins] ∈ {0, 1}  # 1 = Isolationsklasse k_ins gewählt

# Abgeleitete Parameter (aus Auswahl)
D[p] ∈ ℝ₊                        # Effektiver Durchmesser [m]
U[p] ∈ ℝ₊                        # Effektiver U-Wert [W/(m²·K)]
```

### 4.2 Knoten-Variablen

```python
# Zustandsgrößen
p_node[i, t] ∈ [p_min, p_max]    # Druck am Knoten [bar]
T_node[i, t] ∈ [T_min, T_max]    # Temperatur am Knoten [°C]

# Bilanz
m_consumed[i, t] ∈ ℝ₊            # Verbrauchter Massenstrom [kg/s]
m_injected[i, t] ∈ ℝ₊            # Eingespeister Massenstrom [kg/s]

# Temperatur-Mischung (Hilfsvariablen)
w_mix[i, p, t] ∈ ℝ               # m_in[p] · T_in[p] für McCormick
```

### 4.3 Pumpen-Variablen

```python
# Betrieb
m_pump[pump, t] ∈ ℝ₊             # Massenstrom durch Pumpe [kg/s]
Δp_pump[pump, t] ∈ ℝ₊            # Druckerhöhung [bar]
η_pump[pump, t] ∈ [0, 1]         # Wirkungsgrad [-]
P_el_pump[pump, t] ∈ ℝ₊          # Elektrische Leistung [MW]
is_on[pump, t] ∈ {0, 1}          # 1 = Pumpe läuft

# Investment
build_pump[pump] ∈ {0, 1}        # 1 = Pumpe wird gebaut
select_pump_size[pump, k_pump] ∈ {0, 1}  # 1 = Größe k_pump gewählt

# PWL-Hilfsvariablen (SOS2)
λ_pump_curve[pump, t, j] ∈ [0, 1]        # Gewichte für Δp-Kennlinie
λ_pump_eff[pump, t, j] ∈ [0, 1]          # Gewichte für η-Kennlinie
```

### 4.4 Verbraucher-Variablen

```python
# Punktuell
m_extract[i, t] ∈ ℝ₊             # Entnommener Massenstrom [kg/s]
T_return_local[i, t] ∈ [T_min, T_max]  # Lokale Rücklauftemperatur [°C]

# Verteilt (pro Segment s bei Diskretisierung)
T_segment[p, s, t] ∈ [T_min, T_max]    # Temperatur an Segment s
```

### 4.5 Dampf-Variablen (optional)

```python
# Dampfturbine
m_steam[turbine, t] ∈ ℝ₊         # Dampf-Massenstrom [kg/s]
h_in[turbine, t] ∈ ℝ₊            # Eingangs-Enthalpie [kJ/kg]
h_out[turbine, t] ∈ ℝ₊           # Ausgangs-Enthalpie [kJ/kg]
P_el_turbine[turbine, t] ∈ ℝ₊    # Elektrische Leistung [MW]

# PWL für Dampftafeln
λ_steam[turbine, t, j] ∈ [0, 1]  # SOS2-Gewichte
```

---

## 5. Constraints

### 5.1 Massenbilanz

#### 5.1.1 An Knoten (Conservation of Mass)

```
∀ i ∈ N, ∀ t ∈ T:

    ∑[p ∈ P_in(i)] m_flow[p, t]  +  m_injected[i, t]
    =
    ∑[p ∈ P_out(i)] m_flow[p, t]  +  m_consumed[i, t]
```

**Erklärung:** Zufluss + Einspeisung = Abfluss + Verbrauch

#### 5.1.2 Verbraucher-Massenstrom (Point Load)

```
∀ i ∈ N_cons, ∀ t ∈ T:

    m_extract[i, t] · cp · (T_supply[n(i)] - T_return_local[i, t]) = Q_demand[i, t]
```

**Linearisierung:** Falls `T_return_local` variabel → McCormick für `m · T`

**Vereinfachung (oft ausreichend):** `T_return_local[i, t] = T_return[n(i)]` (konstant)
→ Dann: `m_extract[i, t] = Q_demand[i, t] / (cp · ΔT_fixed)`

### 5.2 Energiebilanz

#### 5.2.1 Temperatur-Mischung an Knoten

```
∀ i ∈ N_junc, ∀ t ∈ T:

    ∑[p ∈ P_in(i)] m_flow[p, t] · T_in[p, t]
    =
    T_node[i, t] · ∑[p ∈ P_out(i)] m_flow[p, t]
```

**Linearisierung mit McCormick Envelopes:**

Hilfsvariable: `w_mix[i, p, t] = m_flow[p, t] · T_in[p, t]`

Bounds:
- `m_min[p] ≤ m_flow[p, t] ≤ m_max[p]`
- `T_min ≤ T_in[p, t] ≤ T_max`

McCormick Inequalities:
```
w_mix[i, p, t]  ≥  T_min · m_flow[p, t]  +  m_min[p] · T_in[p, t]  -  T_min · m_min[p]
w_mix[i, p, t]  ≥  T_max · m_flow[p, t]  +  m_max[p] · T_in[p, t]  -  T_max · m_max[p]
w_mix[i, p, t]  ≤  T_min · m_flow[p, t]  +  m_max[p] · T_in[p, t]  -  T_min · m_max[p]
w_mix[i, p, t]  ≤  T_max · m_flow[p, t]  +  m_min[p] · T_in[p, t]  -  T_max · m_min[p]
```

Dann:
```
∑[p ∈ P_in(i)] w_mix[i, p, t]  =  T_node[i, t] · ∑[p ∈ P_out(i)] m_flow[p, t]
```

**Hinweis:** Je enger die Bounds, desto besser die Approximation!

#### 5.2.2 Wärmeverlust in Rohr (ohne verteilte Last)

```
∀ p ∈ P, ∀ t ∈ T:

    Q_loss[p, t] = U[p] · π · D[p] · L[p] · (T_avg[p, t] - T_soil[t]) / 10⁶
```

Mit: `T_avg[p, t] = (T_in[p, t] + T_out[p, t]) / 2`

**Linearisierung:**
- **Option A:** Approximation `T_avg ≈ T_in` (konservativ)
- **Option B:** Einführung Hilfsvariable `T_avg` mit bounds, dann McCormick falls nötig

```
m_flow[p, t] · cp · (T_in[p, t] - T_out[p, t])  =  Q_loss[p, t]
```

**Umformung (linear wenn Q_loss linear):**

```
T_out[p, t] = T_in[p, t] - Q_loss[p, t] / (m_flow[p, t] · cp)
```

**Problem:** `Q_loss / m_flow` ist bilinear!

**Lösung:** PWL-Approximation über Diskretisierung von `m_flow`-Bereichen:

```
# Für Segment k: m_flow ∈ [m_k, m_{k+1}]
# Linearisierte Form:
T_out[p, t] = T_in[p, t] - f_k(m_flow[p, t], T_in[p, t], U, D, L, T_soil[t])
```

#### 5.2.3 Temperatur mit verteilter Last (Diskretisierung)

Rohr in `N_seg` Segmente unterteilen:

```
∀ p ∈ P_distributed, ∀ s ∈ {1, ..., N_seg}, ∀ t ∈ T:

    # Segmentlänge
    L_seg = L[p] / N_seg

    # Linienlast
    q_seg[s] = q_line[p, t]

    # Temperaturabfall pro Segment
    # Kombination aus Wärmeverlust + Entnahme:
    Q_seg_loss = U[p] · π · D[p] · L_seg · (T_segment[p, s, t] - T_soil[t]) / 10⁶
    Q_seg_extract = q_seg[s] · L_seg

    # Energiebilanz
    m_flow[p, t] · cp · (T_segment[p, s, t] - T_segment[p, s+1, t]) = Q_seg_loss + Q_seg_extract
```

**Linearisierung:** Wie oben mit McCormick oder PWL

### 5.3 Druckbilanzen

#### 5.3.1 Druckverlust in Rohr (Darcy-Weisbach)

```
∀ p ∈ P, ∀ t ∈ T:

    Δp[p, t]  =  p_in[p, t] - p_out[p, t]
```

**Physikalisches Modell:**

```
Δp[p, t] = λ[p] · (L[p] / D[p]) · (ρ · v[p, t]² / 2) / 10⁵
```

Mit:
- `v = m_flow / (ρ · A)` = Geschwindigkeit [m/s]
- `A = π · D² / 4` = Querschnittsfläche [m²]
- `λ` = Rohrreibungszahl (Moody-Diagramm, abhängig von Re und k/D)

**Vereinfachung für Turbulenz (Re > 4000):**

```
λ ≈ 0.11 · (k_rough / D + 68/Re)^0.25     # Haaland-Approximation
```

Für konstanten Betrieb mit hohem Re → `λ ≈ const.`

Dann:

```
Δp[p, t] ≈ a[p] · m_flow[p, t]²
```

Mit: `a[p] = λ · L[p] · 8 / (π² · ρ · D[p]⁵ · 10⁵)`

**Linearisierung mit PWL + SOS2:**

Stützstellen:
```
m_pts = [0, 5, 10, 20, 50, 100]                    # kg/s
Δp_pts = [a[p] · m² for m in m_pts]                # bar
```

PWL-Variablen:
```
λ_dp[p, t, j] ∈ [0, 1]  ∀ j ∈ {1, ..., |m_pts|}

∑ λ_dp[p, t, j] = 1
λ_dp[p, t, :] ist SOS2

m_flow[p, t] = ∑ λ_dp[p, t, j] · m_pts[j]
Δp[p, t] = ∑ λ_dp[p, t, j] · Δp_pts[j]
```

#### 5.3.2 Geodätischer Druck

```
∀ p ∈ P, ∀ t ∈ T:

    Δp_geo[p] = -ρ · g · Δz[p] / 10⁵            # bar
```

Dann:
```
Δp[p, t] = Δp_friction[p, t] + Δp_geo[p]
```

#### 5.3.3 Druckkonsistenz an Knoten

```
∀ i ∈ N, ∀ p ∈ P_in(i), ∀ t ∈ T:

    p_out[p, t] = p_node[i, t]
```

```
∀ i ∈ N, ∀ p ∈ P_out(i), ∀ t ∈ T:

    p_in[p, t] = p_node[i, t]
```

#### 5.3.4 Pumpen-Druckerhöhung

```
∀ pump ∈ PUMP, ∀ t ∈ T:

    p_downstream[pump, t] = p_upstream[pump, t] + Δp_pump[pump, t]
```

**Pumpenkennlinie (PWL):**

```
# Gegeben: Stützstellen (m_pts, Δp_pts) für gewählte Pumpe k_pump

∀ pump, ∀ t, ∀ k_pump:

    # Nur wenn Pumpe läuft UND Größe k_pump gewählt:
    IF select_pump_size[pump, k_pump] == 1:

        λ_curve[pump, t, j] ∈ [0, 1]  ∀ j

        ∑ λ_curve[pump, t, j] = 1
        λ_curve ist SOS2

        m_pump[pump, t] = ∑ λ_curve[pump, t, j] · m_pump_pts[k_pump][j]
        Δp_pump[pump, t] ≤ ∑ λ_curve[pump, t, j] · Δp_pump_pts[k_pump][j]
```

**On/Off-Logik:**

```
m_pump[pump, t] ≤ m_max · is_on[pump, t]
Δp_pump[pump, t] ≤ Δp_max · is_on[pump, t]
```

### 5.4 Investitions-Constraints

#### 5.4.1 Rohr-Investition

```
∀ p ∈ P_invest:

    # (1) Rohr existiert nur wenn gebaut
    ∀ t: m_flow[p, t] ≤ M · build_pipe[p]

    # (2) Genau eine Nennweite (wenn gebaut)
    ∑[k_DN] select_DN[p, k_DN] = build_pipe[p]

    # (3) Durchmesser aus Auswahl
    D[p] = ∑[k_DN] select_DN[p, k_DN] · D_inner[k_DN]

    # (4) Genau eine Isolationsklasse
    ∑[k_ins] select_insul[p, k_ins] = build_pipe[p]

    # (5) U-Wert aus Auswahl
    U[p] = ∑[k_ins] select_insul[p, k_ins] · U_value[k_ins]
```

#### 5.4.2 Pumpen-Investition

```
∀ pump ∈ PUMP:

    # (1) Pumpe existiert nur wenn gebaut
    ∀ t: is_on[pump, t] ≤ build_pump[pump]

    # (2) Genau eine Größe (wenn gebaut)
    ∑[k_pump] select_pump_size[pump, k_pump] = build_pump[pump]

    # (3) Kapazität aus Auswahl
    ∀ t: m_pump[pump, t] ≤ ∑[k_pump] select_pump_size[pump, k_pump] · m_flow_nominal[k_pump]
```

#### 5.4.3 Vorlauf/Rücklauf-Kopplung

```
∀ p ∈ P_supply:

    # Zugeordnetes Rücklauf-Rohr
    p_ret = return_pipe(p)

    # (1) Gleiche Massenstrom (Steady-State)
    ∀ t: m_flow[p, t] = m_flow[p_ret, t]

    # (2) Gleiche Investitionsentscheidung
    build_pipe[p] = build_pipe[p_ret]
    select_DN[p, :] = select_DN[p_ret, :]
```

### 5.5 Pumpen-Wirkungsgrad & Leistung

#### 5.5.1 Wirkungsgrad (PWL)

```
∀ pump ∈ PUMP, ∀ t ∈ T, ∀ k_pump (falls gewählt):

    λ_eff[pump, t, j] ∈ [0, 1]  ∀ j

    ∑ λ_eff[pump, t, j] = 1
    λ_eff ist SOS2

    m_pump[pump, t] = ∑ λ_eff[pump, t, j] · m_pump_pts[k_pump][j]
    η_pump[pump, t] = ∑ λ_eff[pump, t, j] · η_pump_pts[k_pump][j]
```

**Hinweis:** Dieselbe `m_pump` für Kennlinie UND Wirkungsgrad → konsistent!

#### 5.5.2 Elektrische Leistung

```
∀ pump ∈ PUMP, ∀ t ∈ T:

    # Hydraulische Leistung
    P_hyd[pump, t] = (m_pump[pump, t] / ρ) · Δp_pump[pump, t] · 10⁵ / 10⁶    # MW

    # Elektrische Leistung
    P_el_pump[pump, t] · η_pump[pump, t] = P_hyd[pump, t]
```

**Problem:** `P_el · η = P_hyd` ist bilinear!

**Lösung 1: Direkte PWL** (empfohlen)

Vorberechnung:
```
P_el_pts[k_pump][j] = (m_pts[j] / ρ) · Δp_pts[j] · 10⁵ / (10⁶ · η_pts[j])
```

Dann:
```
P_el_pump[pump, t] = ∑ λ_eff[pump, t, j] · P_el_pts[k_pump][j]
```

**Lösung 2: McCormick** (falls dynamischer Δp)

Falls `Δp_pump` unabhängig variabel (z.B. VFD-Pumpe):
→ McCormick für `m · Δp / η`

### 5.6 Grenzen & Bounds

```
∀ p ∈ P, ∀ t ∈ T:

    # Massenstrom
    0 ≤ m_flow[p, t] ≤ m_max[p]

    # Druck
    p_min[n(p)] ≤ p_in[p, t], p_out[p, t] ≤ p_max[n(p)]

    # Temperatur
    T_min[n(p)] ≤ T_in[p, t], T_out[p, t] ≤ T_max[n(p)]
```

```
∀ pump ∈ PUMP, ∀ t ∈ T:

    # Druckerhöhung
    0 ≤ Δp_pump[pump, t] ≤ Δp_max[pump]

    # Leistung
    0 ≤ P_el_pump[pump, t] ≤ P_el_max[pump]
```

### 5.7 Multi-Netzwerk-Kopplung

#### 5.7.1 Wärmeübertrager zwischen Netzen

```
∀ hex ∈ HEX, ∀ t ∈ T:

    # Primärseite (Hot)
    Q_hot[hex, t] = m_hot[hex, t] · cp · (T_hot_in[hex, t] - T_hot_out[hex, t])

    # Sekundärseite (Cold)
    Q_cold[hex, t] = m_cold[hex, t] · cp · (T_cold_out[hex, t] - T_cold_in[hex, t])

    # Wärmeübertragung (mit Verlusten)
    Q_cold[hex, t] = ε_hex · Q_hot[hex, t]

    # Pinch-Point
    T_hot_out[hex, t] - T_cold_out[hex, t] ≥ ΔT_pinch
```

**Linearisierung:** `m · T` Terme mit McCormick

**Vereinfachung:** Falls ε_hex = const. und Temperaturen fix:
```
Q_transfer[hex, t] ist Variable (linear)
m_hot[hex, t] = Q_transfer[hex, t] / (cp · ΔT_hot_fixed)
m_cold[hex, t] = Q_transfer[hex, t] / (cp · ΔT_cold_fixed)
```

#### 5.7.2 Netzwerk-Hierarchie

```
# Nur Wärmefluss "bergab" in Temperaturniveau
∀ hex ∈ HEX, ∀ t:

    IF T_level[primary_net(hex)] > T_level[secondary_net(hex)]:
        Q_transfer[hex, t] ≥ 0
    ELSE:
        Q_transfer[hex, t] = 0
```

---

## 6. Zielfunktion

### 6.1 Gesamtkosten (NPV)

```
Minimize:
    CAPEX + OPEX_discounted
```

### 6.2 CAPEX (Capital Expenditures)

```
CAPEX = CAPEX_pipes + CAPEX_pumps
```

#### 6.2.1 Rohr-Investitionen

```
CAPEX_pipes = ∑[p ∈ P_invest] (

    # Fixkosten (Armaturen)
    ∑[k_DN] select_DN[p, k_DN] · cost_fixed[k_DN]

    +

    # Variable Kosten (Rohr + Isolierung)
    L[p] · (
        ∑[k_DN] select_DN[p, k_DN] · cost_per_m[k_DN]
        +
        ∑[k_ins] select_insul[p, k_ins] · cost_insul[k_ins]
    )
)
```

#### 6.2.2 Pumpen-Investitionen

```
CAPEX_pumps = ∑[pump ∈ PUMP] (

    ∑[k_pump] select_pump_size[pump, k_pump] · (
        cost_pump_fixed[k_pump]
        +
        m_flow_nominal[k_pump] · Δp_max[k_pump] · cost_pump_var[k_pump]
    )
)
```

### 6.3 OPEX (Operational Expenditures)

```
OPEX_annual = OPEX_pumps + OPEX_losses
```

#### 6.3.1 Pumpen-Betriebskosten (Strom)

```
OPEX_pumps = ∑[pump ∈ PUMP] ∑[t ∈ T] P_el_pump[pump, t] · c_el[t] · Δt
```

#### 6.3.2 Wärmeverluste (Opportunitätskosten)

```
OPEX_losses = ∑[p ∈ P] ∑[t ∈ T] Q_loss[p, t] · c_heat · Δt
```

### 6.4 Annualisierung

```
OPEX_discounted = OPEX_annual · ((1 + r)^n_years - 1) / (r · (1 + r)^n_years)

# Äquivalent: OPEX_annual / CRF

Total_Cost = CAPEX + OPEX_discounted
```

### 6.5 Alternative: Annualisierte Gesamtkosten

```
TAC (Total Annualized Cost) = CAPEX · CRF + OPEX_annual

Minimize: TAC
```

---

## 7. Linearisierungen

### 7.1 Übersicht

| **Nichtlinearer Term** | **Kontext** | **Methode** | **Variablen** |
|------------------------|-------------|-------------|---------------|
| `m²` | Druckverlust | PWL + SOS2 | λ_dp[p,t,j] |
| `m · T` | Wärmestrom, Mischung | McCormick | w_mT[p,t] |
| `m · Δp / η` | Pumpenleistung | PWL (vorberechnet) | λ_eff[pump,t,j] |
| `Q / m` | Temperaturabfall | Diskretisierung + PWL | - |
| `ln(D)` | U-Wert | Diskrete Auswahl | select_DN[p,k] |

### 7.2 Detaillierte Formulierungen

#### 7.2.1 PWL mit SOS2 (Standard-Template)

**Gegeben:** Univariate Funktion `y = f(x)` mit Stützstellen `(x_pts, y_pts)`

**Variablen:**
```
λ[j] ∈ [0, 1]  ∀ j ∈ {1, ..., M}     # M = Anzahl Stützstellen
```

**Constraints:**
```
x = ∑[j=1..M] λ[j] · x_pts[j]         # Interpolation x

y = ∑[j=1..M] λ[j] · y_pts[j]         # Interpolation y

∑[j=1..M] λ[j] = 1                    # Konvexe Kombination

SOSConstraint(λ, type=2)              # Maximal 2 aufeinanderfolgende λ > 0
```

**Pyomo-Code:**
```python
model.λ = pyo.Var(range(M), domain=pyo.NonNegativeReals, bounds=(0, 1))

model.x_interp = pyo.Constraint(
    expr=x_var == sum(model.λ[j] * x_pts[j] for j in range(M))
)

model.y_interp = pyo.Constraint(
    expr=y_var == sum(model.λ[j] * y_pts[j] for j in range(M))
)

model.λ_sum = pyo.Constraint(
    expr=sum(model.λ[j] for j in range(M)) == 1
)

model.λ_sos = pyo.SOSConstraint(var=model.λ, sos=2)
```

#### 7.2.2 McCormick Envelopes (Standard-Template)

**Gegeben:** Bilineare Term `w = x · y`

**Bounds:**
```
x_L ≤ x ≤ x_U
y_L ≤ y ≤ y_U
```

**Variablen:**
```
w ∈ ℝ
```

**Constraints:**
```
w ≥ x_L · y + y_L · x - x_L · y_L
w ≥ x_U · y + y_U · x - x_U · y_U
w ≤ x_L · y + y_U · x - x_L · y_U
w ≤ x_U · y + y_L · x - x_U · y_L
```

**Pyomo-Code:**
```python
model.w = pyo.Var()

x_L, x_U = x_var.bounds
y_L, y_U = y_var.bounds

model.mc1 = pyo.Constraint(
    expr=model.w >= x_L * y_var + y_L * x_var - x_L * y_L
)
model.mc2 = pyo.Constraint(
    expr=model.w >= x_U * y_var + y_U * x_var - x_U * y_U
)
model.mc3 = pyo.Constraint(
    expr=model.w <= x_L * y_var + y_U * x_var - x_L * y_U
)
model.mc4 = pyo.Constraint(
    expr=model.w <= x_U * y_var + y_L * x_var - x_U * y_L
)
```

**KRITISCH:** Bounds müssen so eng wie möglich sein!

**Verbesserung:** Adaptive bounds basierend auf vorheriger Lösung (Rolling Horizon)

#### 7.2.3 2D-PWL (Dampftafeln)

**Gegeben:** `h = f(p, T)` (Enthalpie als Funktion von Druck und Temperatur)

**Methode A: Separable Programming** (Approximation)

Annahme: `h(p, T) ≈ h_p(p) + h_T(T) - h_ref`

→ Zwei separate 1D-PWL

**Methode B: Look-up Table** (exakt)

Vorberechnung aller `(p_i, T_j)` Kombinationen:
```
conditions = [(p_1, T_1), (p_2, T_1), ..., (p_M, T_N)]
h_values = [h(p_i, T_j) for (p_i, T_j) in conditions]
```

Dann: 1D-PWL über Index `k = i + (j-1)·M`

**Methode C: Triangulation** (für wenige Punkte)

Tetraeder-Unterteilung des (p, T)-Raums → Konvexe Hülle

### 7.3 Genauigkeits-Analyse

#### Anzahl Stützstellen vs. Fehler

| **Funktion** | **5 Stützstellen** | **10 Stützstellen** | **20 Stützstellen** |
|--------------|--------------------|---------------------|---------------------|
| `x²` | ±5% | ±2% | ±0.5% |
| `x^1.75` (Druckverlust) | ±4% | ±1.5% | ±0.4% |
| `exp(-x)` | ±3% | ±1% | ±0.3% |

**Empfehlung:**
- Standard: 10 Stützstellen
- Kritische Komponenten: 15-20 Stützstellen
- Weniger wichtig: 5 Stützstellen

---

## 8. Validierung

### 8.1 Physikalische Tests

#### 8.1.1 Massenbilanz

```
∀ i ∈ N, ∀ t ∈ T:

    Error_mass[i, t] = |∑[p ∈ P_in(i)] m_flow[p, t] + m_injected[i, t]
                        - ∑[p ∈ P_out(i)] m_flow[p, t] - m_consumed[i, t]|

    assert Error_mass[i, t] < ε_mass  (z.B. ε_mass = 1e-6 kg/s)
```

#### 8.1.2 Energiebilanz

```
∀ i ∈ N, ∀ t ∈ T:

    E_in = ∑[p ∈ P_in(i)] m_flow[p, t] · cp · T_in[p, t]
    E_out = ∑[p ∈ P_out(i)] m_flow[p, t] · cp · T_out[p, t]
    Q_consumed = Q_demand[i, t]

    Error_energy[i, t] = |E_in - E_out - Q_consumed|

    assert Error_energy[i, t] < ε_energy  (z.B. ε_energy = 1e-3 MW)
```

#### 8.1.3 Druck-Monotonie

```
∀ p ∈ P, ∀ t ∈ T:

    assert p_in[p, t] ≥ p_out[p, t]  # (außer Pumpen!)
```

#### 8.1.4 Temperatur-Plausibilität

```
∀ p ∈ P_supply, ∀ t ∈ T:

    assert T_in[p, t] ≥ T_out[p, t]  # Vorlauf kühlt ab

∀ p ∈ P_return, ∀ t ∈ T:

    # Rücklauf kann sich erwärmen (unwahrscheinlich) oder abkühlen
    # Aber: T_return < T_supply
    assert T_in[p, t] < T_supply[network(p)]
```

### 8.2 Linearisierungs-Validierung

#### 8.2.1 PWL-Genauigkeit

```
# Für alle Rohre mit Druckverlust
∀ p ∈ P:

    m_test = linspace(0, m_max[p], 1000)

    # Exakte Berechnung
    Δp_exact[m] = a[p] · m²

    # PWL-Approximation (aus Lösung)
    Δp_approx[m] = interpolate(λ_dp[p, t, :], Δp_pts)

    # Relativer Fehler
    rel_error[m] = |Δp_exact[m] - Δp_approx[m]| / Δp_exact[m]

    assert max(rel_error) < 0.02  # < 2%
```

#### 8.2.2 McCormick-Tightness

```
# Für Temperatur-Mischung
∀ i ∈ N_junc, ∀ p ∈ P_in(i), ∀ t:

    # Exakter Wert
    exact = m_flow[p, t] · T_in[p, t]

    # McCormick-Variable
    approx = w_mix[i, p, t]

    rel_error = |exact - approx| / exact

    assert rel_error < 0.01  # < 1%
```

**Hinweis:** Falls Fehler > Toleranz → Bounds verschärfen!

### 8.3 Vergleich mit TESpy (optional)

#### 8.3.1 Workflow

1. **Löse EnerGIS (MILP)**
   - Extrahiere Investment-Entscheidungen (DN, Pumpen-Größen)
   - Extrahiere eine Betriebsstunde t

2. **Baue TESpy-Netz**
   - Gleiche Topologie
   - Gleiche Komponenten-Parameter (DN, Pumpen-Kurven)
   - Setze Randbedingungen aus EnerGIS (Q_demand[i,t], T_supply, etc.)

3. **Simuliere TESpy (nichtlinear)**
   - TESpy löst exakte thermodynamische Gleichungen

4. **Vergleiche Ergebnisse**

#### 8.3.2 Vergleichs-Metriken

```
∀ p ∈ P:

    # Massenstrom
    error_m[p] = |m_EnerGIS[p] - m_TESpy[p]| / m_TESpy[p]
    assert error_m[p] < 0.05  # < 5%

    # Druck
    error_p_in[p] = |p_in_EnerGIS[p] - p_in_TESpy[p]| / p_in_TESpy[p]
    error_p_out[p] = |p_out_EnerGIS[p] - p_out_TESpy[p]| / p_out_TESpy[p]
    assert error_p_in[p], error_p_out[p] < 0.05

    # Temperatur
    error_T_out[p] = |T_out_EnerGIS[p] - T_out_TESpy[p]|
    assert error_T_out[p] < 1.0  # < 1 K
```

**Akzeptable Abweichungen:**
- Massenstrom: < 5%
- Druck: < 5% (oder < 0.2 bar absolut)
- Temperatur: < 1 K
- Leistung: < 5%

Falls Abweichungen größer → Verfeinerung der PWL-Approximationen

---

## 9. Implementierungs-Hinweise

### 9.1 Pyomo-Struktur

```python
import pyomo.environ as pyo

# Model
model = pyo.ConcreteModel()

# Sets
model.T = pyo.RangeSet(1, 8760)
model.N = pyo.Set(initialize=node_ids)
model.P = pyo.Set(initialize=pipe_ids)
# ...

# Parameters
model.L = pyo.Param(model.P, initialize=length_data)
model.T_soil = pyo.Param(model.T, initialize=T_soil_data)
# ...

# Variables
model.m_flow = pyo.Var(model.P, model.T, domain=pyo.NonNegativeReals)
model.p_in = pyo.Var(model.P, model.T, bounds=(p_min, p_max))
# ...

# Constraints
def mass_balance_rule(model, i, t):
    return (
        sum(model.m_flow[p, t] for p in P_in(i)) + model.m_injected[i, t]
        ==
        sum(model.m_flow[p, t] for p in P_out(i)) + model.m_consumed[i, t]
    )
model.mass_balance = pyo.Constraint(model.N, model.T, rule=mass_balance_rule)

# Objective
def objective_rule(model):
    return CAPEX_expr + OPEX_expr
model.objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize)
```

### 9.2 Performance-Tipps

#### 9.2.1 Sparse Indexing

```python
# SCHLECHT: Dichte Matrix (viele Nullen)
model.m_flow = pyo.Var(model.N, model.N, model.T)  # |N|² · |T| Variablen

# GUT: Nur existierende Rohre
model.m_flow = pyo.Var(model.P, model.T)           # |P| · |T| Variablen (|P| << |N|²)
```

#### 9.2.2 Bounds angeben

```python
# WICHTIG: Enge Bounds für alle Variablen
model.m_flow = pyo.Var(model.P, model.T, bounds=(0, m_max))
model.T_in = pyo.Var(model.P, model.T, bounds=(T_min, T_max))
```

Warum?
- Beschleunigt Branch-and-Bound
- Verbessert McCormick-Approximation
- Reduziert Suchraum

#### 9.2.3 Warm Start (Rolling Horizon)

```python
# Nach erstem Solve: Warm start für nächstes Zeitfenster
for v in model.component_objects(pyo.Var):
    for index in v:
        v[index].value = previous_solution[v.name][index]

# Dann: Solve mit Warm Start
solver.solve(model, warmstart=True)
```

#### 9.2.4 Gurobi-Tuning

```python
solver = pyo.SolverFactory('gurobi')

solver.options['MIPGap'] = 0.01          # 1% Optimalitäts-Gap
solver.options['TimeLimit'] = 3600       # 1h Zeitlimit
solver.options['Threads'] = 8            # Parallelisierung
solver.options['Method'] = 2             # Barrier-Methode (gut für große LPs)
solver.options['Presolve'] = 2           # Aggressive Presolve
solver.options['MIPFocus'] = 1           # Focus: Gute Lösungen finden
```

### 9.3 Debugging

#### 9.3.1 Infeasibility Diagnosis

```python
from pyomo.util.infeasible import log_infeasible_constraints

# Model ist infeasible
log_infeasible_constraints(model, log_expression=True)
```

#### 9.3.2 Constraint Violation Check

```python
def check_violations(model, tolerance=1e-6):
    for con in model.component_objects(pyo.Constraint):
        for index in con:
            if con[index].body is not None:
                val = pyo.value(con[index].body)
                lb = con[index].lower
                ub = con[index].upper

                if lb is not None and val < lb - tolerance:
                    print(f"Violation: {con.name}[{index}]: {val} < {lb}")
                if ub is not None and val > ub + tolerance:
                    print(f"Violation: {con.name}[{index}]: {val} > {ub}")
```

---

## 10. Zusammenfassung: Kritische Gleichungen

### Kompakt-Referenz

```
# Massenbilanz
∑ m_in = ∑ m_out + m_consumed

# Energiebilanz (Mischung)
∑(m_in · T_in) = T_node · ∑ m_out        [mit McCormick für m·T]

# Druckverlust (Rohr)
Δp = a · m²                              [PWL + SOS2]
p_in - p_out = Δp + Δp_geo

# Wärmeverlust
Q_loss = U · π · D · L · (T - T_soil)
m · cp · (T_in - T_out) = Q_loss         [Linearisierung!]

# Pumpe
P_el = (m · Δp) / (ρ · η)                [PWL über m]
Δp ≤ Δp_curve(m)                         [PWL]
η = η_curve(m)                           [PWL]

# Investment
D = ∑ select_DN[k] · D[k]
U = ∑ select_insul[k] · U[k]
m ≤ M · build

# Zielfunktion
Min: CAPEX · CRF + OPEX_annual
```

---

**Dokument erstellt am:** 2025-11-18
**Version:** 1.0
**Status:** Design Complete - Ready for Implementation
