# Paper 1 vs. Framework: Detaillierte Analyse & Kontrollmechanismen

**Stand: 2026-01-22**
**Paper: "High-Fidelity Thermo-Hydraulic Modeling of Electrified District Heating Networks"**

---

## 1. Übersicht: Paper-Ansprüche vs. Implementierung

| Paper-Feature | Paper-Gleichung | Framework-Datei | Status | Kontrolle |
|---------------|-----------------|-----------------|--------|-----------|
| **Massenerhaltung** | Eq. 1 | `network_manager.py:920` | ✅ | Junction flow balance |
| **Darcy-Weisbach** | Eq. 2 | `pipe_pair.py:455` | ⚠️ Linearisiert | `delta_p_supply[t]` |
| **Colebrook-White** | Eq. 4 | - | ❌ | - |
| **Swamee-Jain** | Eq. 5 | `pipe_pair.py:445` | ✅ | `f_darcy` berechnet |
| **Newton-Raphson** | Alg. 1 | - | ❌ | Post-Validierung geplant |
| **Wärmeverlust Q=ULdT** | Eq. 7,9 | `network_physics.py:44-57` | ✅ | `pipe_heat_loss_mw()` |
| **FDM Diskretisierung** | Eq. 8 | - | ❌ | Keine Segmente/Rohr |
| **Heizkurve T_supply(T_out)** | Neu | `network_physics.py:88-184` | ✅ | `calculate_supply_temperature()` |
| **Lorenz COP** | Eq. 11 | `heat_pump.py` (extern) | ⚠️ | COP als Zeitreihe |
| **Jensen COP linear** | Eq. 12 | - | ❌ | Nicht implementiert |
| **Teillast PLR** | Eq. 13-14 | `heat_pump.py:min_load` | ⚠️ | Nur min_load Constraint |
| **Multi-Node TES** | Eq. 17-19 | `stratified_storage.py` | ⚠️ 2-Zonen | Nur Hot/Cold Zone |
| **SOC Definition** | Eq. 20 | `stratified_storage.py:436` | ✅ | `E_total[t]` |

---

## 2. Datenfluss: Vom Input bis zur Optimierung

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ EINGABEDATEN (Excel/CSV)                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ Spalten:                                                                    │
│ ├── Zeitstempel                                                             │
│ ├── Wärmebedarf MW        → heatd[t] in Pyomo                              │
│ ├── Strompreis €/MWh      → price[t] in Pyomo                              │
│ ├── CO2 kg/MWh            → grid_co2[t] in Pyomo                           │
│ └── Außentemperatur °C    → outdoor_temp[t] → Heizkurve                    │
│                                                                             │
│ Kontrolle: calion/io/loader.py:223-270                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ KONFIGURATION (YAML)                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ configs/05_networks/brownfield.yaml                                         │
│ ├── parameters:                                                             │
│ │   ├── supply_temp_nominal_c: 120                                          │
│ │   ├── return_temp_nominal_c: 55                                           │
│ │   ├── heating_curve:                                                      │
│ │   │   ├── enabled: true                                                   │
│ │   │   ├── T_supply_min_c: 80                                              │
│ │   │   ├── T_supply_max_c: 120                                             │
│ │   │   ├── T_outdoor_high_c: 20                                            │
│ │   │   └── T_outdoor_low_c: -10                                            │
│ │   └── ground_temp_default_c: 10                                           │
│ ├── pipes: [...]                                                            │
│ └── consumer_zones: [...]                                                   │
│                                                                             │
│ Kontrolle: cat configs/05_networks/brownfield.yaml                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SYSTEM BUILDER (calion/models/system_builder.py)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ 1. Lädt Zeitreihen (Zeile 314-324):                                         │
│    m.price = pyo.Param(m.t, initialize=series_dict("strompreis_EUR_MWh"))   │
│    m.heatd = pyo.Param(m.t, initialize=series_dict("waermebedarf_MWth"))    │
│    m.outdoor_temp = {t: outdoor_temp_series[i] for i, t in enumerate(T)}    │
│                                                                             │
│ 2. Prüft Außentemperatur (Zeile 1126-1130):                                 │
│    if hasattr(m, 'outdoor_temp') and m.outdoor_temp is not None:            │
│        network_cfg['use_outdoor_temperature'] = True                        │
│                                                                             │
│ 3. Erstellt Komponenten (WP, Speicher, Erzeuger)                            │
│                                                                             │
│ 4. Ruft NetworkManager auf (Zeile 1139-1159)                                │
│                                                                             │
│ Kontrolle: Logs beim Build prüfen                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ NETWORK MANAGER (calion/models/network_manager.py)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ PHASE 1: Heizkurve berechnen (Zeile 368-410)                                │
│ ──────────────────────────────────────────────                              │
│ if use_heating_curve and use_outdoor_temp:                                  │
│     supply_temp_series = calculate_supply_temperature_series(               │
│         T_outdoor_series=outdoor_temp_series,                               │
│         T_supply_min_c=80, T_supply_max_c=120, ...                          │
│     )                                                                       │
│     model.supply_temp_series = {t: supply_temp_series[i] for ...}           │
│                                                                             │
│ PHASE 2: Pipes und Nodes erstellen (Zeile 414-489)                          │
│ ──────────────────────────────────────────────────                          │
│ - Erstellt Temperatur-Variablen T_supply_in[t], T_supply_out[t]             │
│ - Erstellt Wärmeverlust-Variablen Q_loss_supply[t], Q_loss_return[t]        │
│ - Erstellt Massenstrom-Variablen m_dot[t]                                   │
│                                                                             │
│ PHASE 3b: Brownfield Temperaturen fixieren (Zeile 500-592)                  │
│ ──────────────────────────────────────────────────────────                  │
│ for t in time_set:                                                          │
│     base_supply_temp = supply_temp_dict[t]  # Aus Heizkurve!                │
│     T_supply_in[t].fix(base_supply_temp)                                    │
│     T_supply_out[t].fix(base_supply_temp - temp_drop_per_pipe)              │
│                                                                             │
│ PHASE 6: Netzwerkverluste (Zeile 1049-1109)                                 │
│ ──────────────────────────────────────────────                              │
│ model.network_Q_loss_per_timestep[t] = total_loss_mw                        │
│                                                                             │
│ Kontrolle: Logger-Output während Optimierung                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Kontrollmechanismen

### 3.1 Heizkurve verifizieren

```python
# Test 1: Funktion direkt testen
from calion.models.network_physics import (
    calculate_supply_temperature,
    get_heating_curve_parameters,
    plot_heating_curve
)

# Parameter abrufen
params = get_heating_curve_parameters()
print(f"Formel: {params['formula']}")
# Output: T_supply = 106.67 + (-1.3333) * T_outdoor

# Einzelwerte testen
print(calculate_supply_temperature(20))   # → 80°C
print(calculate_supply_temperature(0))    # → 106.67°C
print(calculate_supply_temperature(-10))  # → 120°C

# Visualisieren
plot_heating_curve(save_path="heating_curve.pdf", show=False)
```

### 3.2 Konfiguration verifizieren

```bash
# Config-Struktur prüfen
cat configs/05_networks/brownfield.yaml | grep -A 10 "heating_curve"

# Erwartete Ausgabe:
#   heating_curve:
#     enabled: true
#     T_supply_min_c: 80.0
#     T_supply_max_c: 120.0
#     T_outdoor_high_c: 20.0
#     T_outdoor_low_c: -10.0
```

### 3.3 Datenladung verifizieren

```python
from calion.io.loader import load_stadtbach

# Daten laden
table = load_stadtbach(site_cfg={}, path="data/stadtbach/stadtbach_2023.xlsx")

# Prüfen ob Außentemperatur geladen wurde
if "outdoor_temp_C" in table.columns:
    print(f"✅ Außentemperatur vorhanden: {min(table['outdoor_temp_C']):.1f}°C - {max(table['outdoor_temp_C']):.1f}°C")
else:
    print("❌ Außentemperatur NICHT geladen - Heizkurve deaktiviert")
```

### 3.4 Modell-Variablen verifizieren

```python
# Nach build_model()
import pyomo.environ as pyo

# Prüfen ob outdoor_temp geladen wurde
if hasattr(model, 'outdoor_temp') and model.outdoor_temp:
    temps = [model.outdoor_temp[t] for t in model.t]
    print(f"✅ outdoor_temp: {min(temps):.1f}°C - {max(temps):.1f}°C")

# Prüfen ob supply_temp_series berechnet wurde
if hasattr(model, 'supply_temp_series'):
    temps = [model.supply_temp_series[t] for t in model.t]
    print(f"✅ supply_temp_series: {min(temps):.1f}°C - {max(temps):.1f}°C")
```

---

## 4. Konfigurations-Struktur: Analyse & Verbesserungsvorschläge

### 4.1 Aktuelle Struktur

```
configs/
├── 00_base/           # Basis-Parameter (Kosten, Grid, Solver)
├── 01_tech/           # Technologie-Definitionen (WP, Speicher, Fuels)
├── 02_site/           # Standort-spezifisch (Stadtbach)
├── 03_systems/        # System-Konfigurationen (baseline, full, with_hp)
├── 04_scenarios/      # Zeitszenarien (full_year, q1, test_1week)
├── 05_networks/       # Netzwerk-Topologie (brownfield.yaml)
└── presets/           # Workflow-Presets (mpc, rh, quick_test)
```

### 4.2 Problem: Heizkurve in brownfield.yaml

**Aktuell:**
```yaml
# configs/05_networks/brownfield.yaml
parameters:
  heating_curve:
    enabled: true
    T_supply_min_c: 80.0
    ...
```

**Problem:** Die Heizkurve ist netzwerk-spezifisch, aber eigentlich eine Betriebsstrategie (wie MPC vs. Rolling Horizon).

### 4.3 Verbesserungsvorschlag: Separate Heizkurven-Config

```yaml
# configs/01_tech/heating_curves.yaml (NEU)
heating_curves:
  standard_dh:
    description: "Klassische Fernwärme 80-120°C"
    T_supply_min_c: 80.0
    T_supply_max_c: 120.0
    T_outdoor_high_c: 20.0
    T_outdoor_low_c: -10.0

  4gdh_low_temp:
    description: "4. Generation Fernwärme 50-70°C"
    T_supply_min_c: 50.0
    T_supply_max_c: 70.0
    T_outdoor_high_c: 15.0
    T_outdoor_low_c: -5.0

  constant_90:
    description: "Konstante Vorlauftemperatur 90°C"
    T_supply_min_c: 90.0
    T_supply_max_c: 90.0
    T_outdoor_high_c: 20.0
    T_outdoor_low_c: -10.0
```

```yaml
# configs/05_networks/brownfield.yaml (ANGEPASST)
parameters:
  supply_temp_nominal_c: 120
  return_temp_nominal_c: 55
  heating_curve:
    enabled: true
    profile: standard_dh  # Referenz auf heating_curves.yaml
```

### 4.4 Alternative: In Szenario-Config

```yaml
# configs/04_scenarios/full_year_2023.yaml
scenario:
  start: "2023-01-01"
  end: "2023-12-31"

  # Betriebsstrategie
  heating_curve:
    enabled: true
    T_supply_min_c: 80.0
    T_supply_max_c: 120.0
    T_outdoor_high_c: 20.0
    T_outdoor_low_c: -10.0
```

---

## 5. Paper vs. Framework: Detaillierte Gleichungs-Mapping

### 5.1 Hydraulisches Modell (Paper Section 2.2)

| Gleichung | Paper-Formel | Framework-Code | Anmerkung |
|-----------|--------------|----------------|-----------|
| Eq. 1 Massenerhaltung | Σṁ_in = Σṁ_out | `network_manager.py:914-928` | ✅ Junction flow balance |
| Eq. 2 Darcy-Weisbach | ΔP = f·L/D·ρv²/2 | `pipe_pair.py:455-470` | ⚠️ Linearisiert: ΔP ≈ k·ṁ |
| Eq. 4 Colebrook-White | Implicit f | - | ❌ Nicht implementiert |
| Eq. 5 Swamee-Jain | Explicit f | `pipe_pair.py:445` | ✅ Für f-Berechnung |
| Eq. 6 Kirchhoff | ΣΔP = 0 (loops) | - | ❌ Keine Schleifen-Constraints |
| Alg. 1 Newton-Raphson | Iterative solver | - | ❌ Nur Post-Validierung |

**Framework-Code (Linearisierung):**
```python
# pipe_pair.py:455-470
# Linearisierte Druckverlust-Approximation für MILP:
k_linear = k_pressure * max_velocity**2 / effective_max_flow
def pressure_rule(m, t):
    return delta_p_supply[t] == k_linear * m_dot[t]
```

### 5.2 Thermisches Rohrmodell (Paper Section 2.3)

| Gleichung | Paper-Formel | Framework-Code | Anmerkung |
|-----------|--------------|----------------|-----------|
| Eq. 7 Energie-PDE | ρc_p·A·∂T/∂t + ... | - | ❌ Keine PDE-Lösung |
| Eq. 8 FDM | Implizit upwind | - | ❌ Keine Diskretisierung |
| Eq. 9 U-Wert | 1/U = 1/α + ... | Config: `u_value_w_per_m_k` | ⚠️ Vorgegeben, nicht berechnet |
| Eq. 10 λ(T) | Temperaturabh. | - | ❌ Nicht implementiert |

**Framework-Code (Wärmeverlust):**
```python
# network_physics.py:44-57
def pipe_heat_loss_mw(U_w_per_m_k, length_m, T_fluid_c, T_ground_c):
    delta_T = T_fluid_c - T_ground_c
    return U_w_per_m_k * length_m * delta_T / 1e6  # [MW]
```

### 5.3 Heizkurve (NEU - nicht im Paper)

| Feature | Formel | Framework-Code | Anmerkung |
|---------|--------|----------------|-----------|
| Lineare Heizkurve | T_supply = a + b·T_out | `network_physics.py:88-147` | ✅ Implementiert |
| Zeitreihen-Berechnung | T_supply[t] = f(T_out[t]) | `network_physics.py:150-184` | ✅ Implementiert |
| Visualisierung | Plot | `network_physics.py:237-383` | ✅ Implementiert |

**Formel:**
```
T_supply = 106.67 - 1.333 × T_outdoor

Mit Clipping:
T_supply = max(80, min(120, 106.67 - 1.333 × T_outdoor))
```

### 5.4 Wärmepumpen-Modell (Paper Section 2.4)

| Gleichung | Paper-Formel | Framework-Code | Anmerkung |
|-----------|--------------|----------------|-----------|
| Eq. 11 Lorenz COP | COP = η·T_sink/(T_sink-T_source) | Extern berechnet | ⚠️ COP als Zeitreihe übergeben |
| Eq. 12 Jensen linear | COP ≈ a₀ + a₁·T_s + a₂·T_sink | - | ❌ Nicht implementiert |
| Eq. 13-14 PLR | COP_PLR = COP·f(PLR) | `heat_pump.py:min_load` | ⚠️ Nur min_load (30%) |
| Eq. 15-16 Energie | Q = Q_source + P_el | `heat_pump.py:90-95` | ✅ Implementiert |

**Framework-Code:**
```python
# heat_pump.py:90-95
# COP-basierte Energiebilanz:
def cop_balance_rule(m, t):
    return Q_th[t] == COP[t] * P_el[t]
```

### 5.5 Thermischer Speicher (Paper Section 2.5)

| Gleichung | Paper-Formel | Framework-Code | Anmerkung |
|-----------|--------------|----------------|-----------|
| Eq. 17 Multi-Node | dT_i/dt = ... | `stratified_storage.py:427` | ⚠️ Nur 2-Zonen (Hot/Cold) |
| Eq. 18 Konduktion | Q_cond = λ·A/Δz·(T_i-1 - 2T_i + T_i+1) | - | ❌ Nicht implementiert |
| Eq. 19 Wandverluste | Q_loss = U·A·(T-T_amb) | `stratified_storage.py:580-598` | ✅ Geometriebasiert |
| Eq. 20 SOC | SOC = Σ(E_i)/E_max | `stratified_storage.py:433` | ✅ Implementiert |

**Framework-Code (2-Zonen-Modell):**
```python
# stratified_storage.py:397-401
def energy_from_volume_rule(m, t):
    e_hot = self.e_specific * self.T_hot * V_hot[t]
    e_cold = self.e_specific * self.T_cold * V_cold[t]
    return E_total[t] == e_hot + e_cold
```

---

## 6. Komplexitätsstufen: Paper vs. Realität

### Paper-Anspruch (Table 2)

| Level | Netzwerk | TES | COP | MILP |
|-------|----------|-----|-----|------|
| L1 | Aggregiert | Single | Konstant | ✓ |
| L2 | Nodes only | 2-Zone | Lorenz | ✓ |
| L3 | 5 seg/pipe | Multi(5) | Jensen | ✓ |
| L4 | 10 seg/pipe | Multi(10) | Jensen NL | - |
| L5 | 50 seg/pipe | 3D-FEM | Thermo | - |

### Tatsächliche Implementierung

| Level | Netzwerk | TES | COP | MILP | **Implementiert** |
|-------|----------|-----|-----|------|-------------------|
| L1 | Aggregiert | Single | Konstant | ✓ | ✅ `StorageBlock` |
| L2 | Brownfield | 2-Zone | Zeitreihe | ✓ | ✅ `StratifiedStorageBlock` |
| L2+ | + Heizkurve | 2-Zone | Zeitreihe | ✓ | ✅ **NEU** |
| L3 | Greenfield | 2-Zone | Zeitreihe | ✓ | ⚠️ Ohne Rohr-Segmente |
| L4 | - | - | - | - | ❌ Nicht verfügbar |
| L5 | - | - | - | - | ❌ Nicht verfügbar |

---

## 7. Empfehlungen für das Paper

### 7.1 Realistische Komplexitätsstufen

```latex
\begin{table}[t]
    \centering
    \caption{Model complexity levels (revised).}
    \label{tab:complexity_levels_revised}
    \begin{tabular}{@{}clllcc@{}}
        \toprule
        \textbf{Level} & \textbf{Network} & \textbf{TES} & \textbf{Supply Temp} & \textbf{MILP} \\
        \midrule
        L1 & Aggregated & Single state & Constant & \checkmark \\
        L2 & Brownfield & 2-Zone & Constant & \checkmark \\
        L2+ & Brownfield & 2-Zone & Heating curve & \checkmark \\
        L3 & Greenfield & 2-Zone & Heating curve & \checkmark \\
        L4 & + Post-val. & Multi-Node & Dynamic & -- \\
        \bottomrule
    \end{tabular}
\end{table}
```

### 7.2 Neue Contribution: Heizkurve

```latex
\item[\textbf{C5:}] \textbf{Outdoor-dependent supply temperature:}
Implementation of linear heating curves enabling realistic
temperature-dependent network modeling while maintaining MILP compatibility.
The supply temperature varies from \SI{80}{\celsius} at \SI{20}{\celsius}
outdoor to \SI{120}{\celsius} at \SI{-10}{\celsius} outdoor.
```

### 7.3 Ehrliche Limitierungen

```latex
\subsection{Limitations}
\begin{enumerate}
    \item Hydraulic equilibrium solved via linear approximation,
          not Newton-Raphson iteration (for MILP compatibility)
    \item No finite-difference discretization along pipes;
          single-node per pipe representation
    \item Thermal storage limited to two-zone model;
          full N-node stratification not implemented
    \item COP provided as external time series,
          not calculated from temperatures within optimization
\end{enumerate}
```

---

## 8. Nächste Schritte

### 8.1 Kurzfristig (für Paper-Einreichung)

1. [ ] Außentemperatur-Spalte in Testdaten hinzufügen
2. [ ] Heizkurve in Paper Section 2.3 dokumentieren
3. [ ] Komplexitätsstufen-Tabelle anpassen
4. [ ] Validierungsmetriken (RMSE/MBE) implementieren

### 8.2 Mittelfristig (Framework-Erweiterung)

1. [ ] N-Node Speichermodell (optional)
2. [ ] Jensen COP-Linearisierung
3. [ ] Newton-Raphson Post-Validierung
4. [ ] Dashboard-Tab für Netzwerk

### 8.3 Langfristig (L4/L5)

1. [ ] FDM Rohr-Diskretisierung
2. [ ] Externe Validierung (Modelica/CFD-Kopplung)
3. [ ] Stochastische Optimierung

---

*Analyse erstellt: 2026-01-22*
*Framework-Version: CALION mit Heizkurve*
