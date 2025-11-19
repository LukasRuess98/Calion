# Erweiterung: Kältenetze & Wärmerückgewinnung

## Executive Summary

Diese Erweiterung integriert **Kältenetze** (Cooling Networks) und **Wärmerückgewinnung** (Heat Recovery) in das thermische Netzwerk-Framework.

**Kernpunkte:**
- ✅ Minimale Änderungen an bestehenden Modellen
- ✅ Gleiche physikalische Gleichungen (nur andere Temperaturbereiche)
- ✅ 4 neue Komponenten: Chiller, Cooling Tower, Free Cooling, Heat Recovery Unit
- ✅ +1-2 Wochen Implementierungsaufwand
- ✅ Ermöglicht Sektorenkopplung (Wärme-Kälte-Integration)

---

## 1. Motivation & Anwendungsfälle

### 1.1 Kältenetze (District Cooling)

**Typische Anwendungen:**
- Klimatisierung von Bürogebäuden, Rechenzentren
- Industrielle Kühlung (Lebensmittel, Pharma)
- Medizinische Einrichtungen (Krankenhäuser)

**Typische Parameter:**
```
Kältenetz (Kaltwasser):
- Vorlauf:  6-8°C
- Rücklauf: 12-16°C
- Druck:    4-8 bar
- Medium:   Wasser (+ Glykol bei <0°C)
```

**Vorteile zentraler Kältenetze:**
- Höhere Effizienz (COP 5-7 statt 3-4 bei dezentralen Geräten)
- Free Cooling aus Gewässern, Grundwasser
- Lastmanagement (Kältespeicher)
- Weniger Kältemittel-Leckagen

### 1.2 Wärmerückgewinnung (Heat Recovery)

**Typische Quellen:**
```
Industrielle Abwärme:
- Hochtemperatur (>200°C): Öfen, Trocknungsprozesse
- Mitteltemperatur (80-200°C): Dampfprozesse, Kompressoren
- Niedertemperatur (30-80°C): Kühlwasser, Abluft

Sonstige Quellen:
- Rechenzentren: 30-50°C
- Abwasserreinigung: 20-30°C
- Kühlprozesse: Variable Temperaturen
```

**Integration:**
- Direkte Einspeisung in Wärmenetz (wenn T hoch genug)
- Temperaturanhebung via Wärmepumpe (wenn T zu niedrig)
- Kaskadierung über mehrere Temperatur-Niveaus

### 1.3 Wärme-Kälte-Kopplung

**Systeme mit beiden Netzen:**

```
┌─────────────────────────────────────────────────────┐
│  Wärmepumpe (zentral)                               │
│  - Verdampfer @ Kältenetz (8°C)                    │
│  - Kondensator @ Wärmenetz (55°C)                  │
│  - COP = 4-5                                        │
└─────────────────────────────────────────────────────┘
           ▲                          │
           │ Kälte                    │ Wärme
           │ (8°C)                    │ (55°C)
           │                          ▼
┌──────────┴─────────┐    ┌──────────┴─────────┐
│  Kältenetz         │    │  Wärmenetz         │
│  - Klimatisierung  │    │  - Heizung         │
│  - Prozess-Kühlung │    │  - Warmwasser      │
└────────────────────┘    └────────────────────┘
           ▲
           │ Abwärme
┌──────────┴─────────┐
│  Wärmerückgewinnung│
│  - Rechenzentrum   │
│  - Industrie       │
└────────────────────┘
```

**Vorteile:**
- Gleichzeitige Deckung von Wärme- und Kältebedarf
- Nutzung von Abwärme als Wärmequelle
- Optimierung über beide Netze hinweg

---

## 2. Neue Netzwerk-Typen

### 2.1 Cooling Network Definition

**Erweiterung von `NetworkDefinition`:**

```python
@dataclass
class NetworkDefinition:
    """Definition eines thermischen Netzes"""
    id: str
    name: str
    network_type: str  # NEU: "heating" | "cooling"
    medium: str  # "water_liquid" | "water_glycol" | "water_steam"
    T_supply: float  # °C
    T_return: float  # °C
    p_nominal: float  # bar
    p_min: float  # bar
    p_max: float  # bar
    temperature_level: str  # "high" | "medium" | "low" | "cooling"
```

**Beispiel-Konfiguration:**

```yaml
# config/networks/heating_cooling_system.yaml
networks:
  # Wärmenetz
  - id: "dh_lt"
    name: "Fernwärme Niedertemperatur"
    network_type: "heating"
    medium: "water_liquid"
    T_supply: 55
    T_return: 35
    p_nominal: 4
    p_min: 2
    p_max: 8
    temperature_level: "low"

  # Kältenetz
  - id: "dc_chilled_water"
    name: "Fernkälte Kaltwasser"
    network_type: "cooling"
    medium: "water_liquid"
    T_supply: 6
    T_return: 12
    p_nominal: 5
    p_min: 3
    p_max: 8
    temperature_level: "cooling"

  # Abwärme-Netz (für Heat Recovery)
  - id: "waste_heat_medium"
    name: "Abwärme Mitteltemperatur"
    network_type: "heating"
    medium: "water_liquid"
    T_supply: 40
    T_return: 25
    p_nominal: 3
    p_min: 2
    p_max: 6
    temperature_level: "low"
```

### 2.2 Physikalische Unterschiede

**Wärmenetz vs. Kältenetz:**

| **Aspekt** | **Wärmenetz** | **Kältenetz** |
|------------|---------------|---------------|
| Vorlauftemperatur | 55-120°C | 6-12°C |
| Wärmeverluste | Nachteilig (Verlust an Umgebung) | Vorteilhaft (Kühlung durch Umgebung) |
| Isolierung | Hochwertig erforderlich | Reduziert (gegen Kondensat) |
| Verbraucher | Heizkörper, Fußbodenheizung | Kühldecken, Klimaanlagen |
| Erzeuger | Kessel, CHP, Wärmepumpe | Kältemaschine, Free Cooling |

**Modellierung:**

```python
# Wärmeverluste bei Kältenetz = WÄRMEGEWINN!
# Bei T_supply = 8°C, T_ambient = 20°C:
# Q_gain = U · π · D · L · (T_ambient - T_supply)  # > 0
#
# → Vorlauftemperatur steigt entlang Rohr!

# Energiebilanz Kältenetz-Rohr:
m · cp · (T_out - T_in) = Q_gain
# T_out > T_in (statt T_out < T_in bei Wärmenetz)
```

**Implementation:** Gleiche Gleichungen, aber Vorzeichen beachten!

---

## 3. Neue Komponenten

### 3.1 Chiller (Kältemaschine)

#### Beschreibung
Erzeugt Kälte durch Kompressionskältemaschine oder Absorptionskältemaschine.

#### Typen

**Typ A: Kompressionskältemaschine (elektrisch)**
```
Elektrische Energie ──► [Chiller] ──► Kälte
                                   └──► Abwärme (Kondensator)
```

**Typ B: Absorptionskältemaschine (thermisch)**
```
Wärme (HT) ──► [Absorption Chiller] ──► Kälte
                                      └──► Abwärme (LT)
```

#### Variablen

```python
# Kälteproduktion
Q_cold[t]              # Kälteleistung (Verdampfer) [MW]
T_evap[t]              # Verdampfertemperatur [°C]

# Wärmeabfuhr
Q_cond[t]              # Kondensatorwärme [MW]
T_cond[t]              # Kondensatortemperatur [°C]

# Energieeinsatz
P_el[t]                # Elektrische Leistung [MW] (Kompression)
Q_heat_in[t]           # Antriebswärme [MW] (Absorption)

# Effizienz
COP[t]                 # Coefficient of Performance [-]
# COP = Q_cold / (P_el oder Q_heat_in)
```

#### Constraints

```python
# Energiebilanz
Q_cond[t] = Q_cold[t] + P_el[t]  # Kompression
Q_cond[t] = Q_cold[t] + Q_heat_in[t]  # Absorption (vereinfacht)

# COP-Modell (temperaturabhängig)
# Carnot: COP_Carnot = T_evap / (T_cond - T_evap)
# Real: COP[t] = η_carnot · COP_Carnot(T_evap[t], T_cond[t])

# Für MILP: COP aus Lookup-Table (2D-PWL)
COP[t] = f_PWL(T_evap[t], T_cond[t])

# Leistung
P_el[t] = Q_cold[t] / COP[t]  # Linearisierung: PWL über Q_cold

# Flows
# Kälte-Seite: Einspeisung ins Kältenetz
m_cold[t] · cp · (T_return_cold[t] - T_supply_cold[t]) = Q_cold[t]

# Wärme-Seite: Abwärme abführen (Kühlturm oder Wärmenetz)
m_cond[t] · cp · (T_cond_out[t] - T_cond_in[t]) = Q_cond[t]
```

#### Investment

```python
# Binary: Chiller bauen?
build_chiller[chiller] ∈ {0, 1}

# Größenauswahl
select_size[chiller, size_k] ∈ {0, 1}
Q_cold_nominal = ∑ select_size[k] · Q_cold_nominal[k]

# Kosten
CAPEX_chiller = ∑ select_size[k] · (cost_fixed[k] + cost_var[k] · Q_cold_nominal[k])
OPEX_chiller = ∑_t P_el[t] · c_el[t] · Δt
```

#### Komponenten-Datei

**`energis/models/blocks/cooling/chiller.py`** (~350 Zeilen)

---

### 3.2 Cooling Tower (Rückkühler)

#### Beschreibung
Kühlt Kondensatorwasser durch Verdunstungskühlung oder Trockenkühlung.

#### Typen

**Typ A: Verdunstungsrückkühlwerk (Wet Cooling Tower)**
- Höchste Effizienz
- Wasserverbrauch
- Erreicht Kühlgrenztemperatur (nahe Feuchtkugeltemperatur)

**Typ B: Trockenkühler (Dry Cooler)**
- Kein Wasserverbrauch
- Geringere Effizienz
- Kühlgrenze = Lufttemperatur

#### Variablen

```python
# Wärmeabfuhr
Q_reject[t]            # Abgeführte Wärme [MW]
m_water[t]             # Wassermassenstrom [kg/s]
T_water_in[t]          # Eintrittstemperatur [°C]
T_water_out[t]         # Austrittstemperatur [°C]

# Umgebung
T_ambient[t]           # Lufttemperatur [°C] (exogen)
T_wetbulb[t]           # Feuchtkugeltemperatur [°C] (exogen)

# Lüfter
P_fan[t]               # Lüfterleistung [MW]
```

#### Constraints

```python
# Energiebilanz
Q_reject[t] = m_water[t] · cp · (T_water_in[t] - T_water_out[t])

# Kühlgrenze
# Wet: T_water_out[t] ≥ T_wetbulb[t] + ΔT_approach
# Dry: T_water_out[t] ≥ T_ambient[t] + ΔT_approach

# Lüfterleistung (proportional zu Q_reject)
P_fan[t] = α · Q_reject[t]  # α ≈ 0.01-0.03 (1-3% der Wärmeleistung)
```

#### Vereinfachung für MILP

```python
# Konstante Kühltemperatur (worst-case Design)
T_water_out[t].fix(T_design_out)  # z.B. 32°C

# Dann: Nur Massenstrom-Berechnung
m_water[t] = Q_reject[t] / (cp · (T_water_in[t] - T_design_out))
```

#### Komponenten-Datei

**`energis/models/blocks/cooling/cooling_tower.py`** (~250 Zeilen)

---

### 3.3 Free Cooling Unit

#### Beschreibung
Nutzt natürliche Kältequellen ohne Kältemaschine:
- Grundwasser
- Fluss-/Seewasser
- Außenluft (bei niedrigen Temperaturen)

#### Typen

**Typ A: Grundwasser/Oberflächenwasser**
```
Gewässer (8-12°C) ──► [Wärmeübertrager] ──► Kältenetz (6-12°C)
                                          └──► Gewässer zurück (10-14°C)
```

**Typ B: Außenluft (Winter)**
```
Außenluft (<5°C) ──► [Luft-Wasser-WT] ──► Kältenetz
```

#### Variablen

```python
# Kältebereitstellung
Q_cool[t]              # Bereitgestellte Kälte [MW]
is_active[t]           # Binary: Free Cooling aktiv? (nur bei niedrigen T_ambient)

# Source-Seite (Wasser/Luft)
m_source[t]            # Massenstrom Quelle [kg/s]
T_source_in[t]         # Temperatur Quelle [°C] (exogen, z.B. Flusstemperatur)
T_source_out[t]        # Temperatur Rückgabe [°C]

# Kältenetz-Seite
m_cold[t]              # Massenstrom Kältenetz [kg/s]
T_cold_in[t]           # Rücklauf Kältenetz [°C]
T_cold_out[t]          # Vorlauf Kältenetz [°C]

# Pumpen
P_pump[t]              # Pumpenleistung [MW]
```

#### Constraints

```python
# Energiebilanz Wärmeübertrager
Q_cool[t] = ε_HEX · m_source[t] · cp · (T_source_in[t] - T_pinch)
Q_cool[t] = m_cold[t] · cp · (T_cold_in[t] - T_cold_out[t])

# Pinch-Point
T_source_out[t] ≥ T_cold_out[t] + ΔT_pinch  # z.B. 2K

# Verfügbarkeit (nur bei ausreichend niedriger Quellentemperatur)
# Free Cooling nur wenn: T_source < T_cold_supply + ΔT_threshold
is_active[t] = 1  if T_source_in[t] < T_threshold  else 0

Q_cool[t] ≤ Q_max · is_active[t]

# Pumpenleistung (gering)
P_pump[t] = (m_source[t] / ρ) · Δp_system / η_pump
```

#### Jahreszeit-Abhängigkeit

```python
# Typische Verfügbarkeit:
# - Grundwasser: Ganzjährig 8-12°C → Immer nutzbar
# - Flusswasser: Sommer 18-22°C, Winter 4-8°C → Nur Winter
# - Außenluft: Nur bei T_ambient < 5°C → Wintermonate

# Zeitreihe T_source_in[t] aus Messdaten oder Modell
```

#### Komponenten-Datei

**`energis/models/blocks/cooling/free_cooling.py`** (~300 Zeilen)

---

### 3.4 Heat Recovery Unit (Wärmerückgewinnung)

#### Beschreibung
Koppelt Abwärmequelle (z.B. Industrieprozess, Rechenzentrum) an Wärmenetz.

#### Variablen

```python
# Abwärmequelle
Q_waste_available[t]   # Verfügbare Abwärme [MW] (exogen oder modelliert)
T_waste_in[t]          # Temperatur Abwärme-Quelle [°C]
T_waste_out[t]         # Temperatur nach Wärmeentnahme [°C]
m_waste[t]             # Massenstrom Abwärme-Kreislauf [kg/s]

# Wärmenetz-Seite
Q_recovered[t]         # Rückgewonnene Wärme [MW]
m_heat_net[t]          # Massenstrom Wärmenetz [kg/s]
T_heat_in[t]           # Rücklauf Wärmenetz [°C]
T_heat_out[t]          # Vorlauf Wärmenetz [°C]

# Wärmeübertrager
ε_HEX                  # Effectiveness [-]

# Optional: Wärmepumpe zur Temperaturanhebung
use_heatpump[t]        # Binary: Wärmepumpe nutzen?
Q_heatpump[t]          # Wärmepumpen-Ausgangsleistung [MW]
COP_hp[t]              # COP Wärmepumpe [-]
P_el_hp[t]             # Elektrische Leistung Wärmepumpe [MW]
```

#### Constraints

**Fall A: Direkte Einspeisung (T_waste hoch genug)**

```python
# Wenn T_waste_in > T_heat_out + ΔT_pinch:
# Direkter Wärmeübertrager

Q_recovered[t] = ε_HEX · min(
    m_waste[t] · cp · (T_waste_in[t] - T_pinch),
    m_heat_net[t] · cp · (T_heat_out[t] - T_heat_in[t])
)

# Energiebilanzen
m_waste[t] · cp · (T_waste_in[t] - T_waste_out[t]) = Q_recovered[t]
m_heat_net[t] · cp · (T_heat_out[t] - T_heat_in[t]) = Q_recovered[t]

# Pinch
T_waste_out[t] ≥ T_heat_out[t] + ΔT_pinch
```

**Fall B: Mit Wärmepumpe (T_waste zu niedrig)**

```python
# Wenn T_waste_in < T_heat_out + ΔT_pinch:
# Wärmepumpe erforderlich

# Abwärme als Wärmequelle für WP
Q_source_hp[t] = ε_HEX · m_waste[t] · cp · (T_waste_in[t] - T_evap_hp[t])

# Wärmepumpe
COP_hp[t] = f(T_evap_hp[t], T_cond_hp[t])  # PWL
Q_heatpump[t] = Q_source_hp[t] + P_el_hp[t]
P_el_hp[t] = Q_heatpump[t] / (COP_hp[t] + 1)  # Linearisierung

# Einspeisung ins Wärmenetz
Q_recovered[t] = Q_heatpump[t]
```

**MILP-Formulierung mit Binary:**

```python
# use_heatpump[t] = 1 falls T_waste_in < T_threshold

# Constraint:
# IF use_heatpump[t] == 0:
#     Q_recovered[t] aus Fall A
# ELSE:
#     Q_recovered[t] aus Fall B

# Mit Big-M Formulierung oder Indicator Constraints
```

#### Typen von Abwärmequellen

**Rechenzentrum:**
```yaml
heat_recovery_datacenter:
  type: "heat_recovery"
  source_type: "datacenter"
  Q_available_profile: "profiles/datacenter_waste_heat.csv"
  T_waste: 35  # °C (Serverkühlwasser)
  m_waste_max: 50  # kg/s
  requires_heatpump: true  # Zu niedrig für direkte Einspeisung
```

**Industrieprozess:**
```yaml
heat_recovery_industrial:
  type: "heat_recovery"
  source_type: "industrial_process"
  Q_available_profile: "profiles/industrial_waste_heat.csv"
  T_waste: 80  # °C (Abgas nach Prozess)
  m_waste_max: 20  # kg/s
  requires_heatpump: false  # Direkt nutzbar
```

#### Komponenten-Datei

**`energis/models/blocks/heat_recovery/heat_recovery_unit.py`** (~400 Zeilen)

---

## 4. Erweiterte Wärmepumpen-Modellierung

### 4.1 Bidirektionale Wärmepumpe

**Betriebsmodi:**
- **Heizen:** Kältenetz als Quelle, Wärmenetz als Senke
- **Kühlen:** Wärmenetz als Quelle, Kältenetz als Senke (reversibel)

#### Variablen

```python
# Betriebsmodus
mode[t] ∈ {0, 1}           # 0 = Heizen, 1 = Kühlen

# Heizmodus
Q_heat[t]                  # Wärmeabgabe [MW]
Q_cold_source[t]           # Wärmeaufnahme aus Kältequelle [MW]
COP_heat[t]                # COP im Heizmodus [-]

# Kühlmodus
Q_cool[t]                  # Kälteabgabe [MW]
Q_heat_sink[t]             # Wärmeabgabe (Kondensator) [MW]
COP_cool[t]                # EER im Kühlmodus [-]

# Elektrisch
P_el[t]                    # Elektrische Leistung [MW]
```

#### Constraints

```python
# Heizmodus (mode[t] = 0)
# Q_heat = Q_cold_source + P_el
# COP_heat = Q_heat / P_el

# Kühlmodus (mode[t] = 1)
# Q_heat_sink = Q_cool + P_el
# EER_cool = Q_cool / P_el

# Mit Binary mode[t]:
Q_heat[t] ≤ Q_max · (1 - mode[t])
Q_cool[t] ≤ Q_max · mode[t]

# Flows zu Netzen
# Heizmodus: Entnahme aus Kältenetz, Einspeisung ins Wärmenetz
m_cold[t] · cp · (T_cold_return[t] - T_cold_supply[t]) = Q_cold_source[t] · (1 - mode[t])
m_heat[t] · cp · (T_heat_supply[t] - T_heat_return[t]) = Q_heat[t] · (1 - mode[t])

# Kühlmodus: Entnahme aus Wärmenetz, Einspeisung ins Kältenetz
m_heat[t] · cp · (T_heat_return[t] - T_heat_supply[t]) = Q_cool[t] · mode[t]
m_cold[t] · cp · (T_cold_supply[t] - T_cold_return[t]) = Q_heat_sink[t] · mode[t]
```

### 4.2 Erweiterung der existierenden HeatPumpBlock

**Änderungen in `energis/models/blocks/heat_pump.py`:**

```python
@dataclass
class HeatPumpConfig:
    # ... (existierende Parameter)

    # NEU: Kälte-Seite
    cold_network: Optional[str] = None  # ID des Kältenetzes
    supports_cooling: bool = False      # Reversible Wärmepumpe?
```

```python
def attach(self, model, time_set, config, buses):
    # ... (existierender Code)

    if self.config.cold_network:
        # Flows zu Kältenetz registrieren
        self.add_flow(Flow(
            bus=self.config.cold_network,
            direction="input",  # Im Heizmodus: Wärme aus Kältenetz
            variable=Q_cold_source,
            # ...
        ))

    if self.config.supports_cooling:
        # Zusätzliche Variablen & Constraints für Kühlmodus
        # ...
```

---

## 5. Systembeispiel: Integriertes Wärme-Kälte-System

### 5.1 Topologie

```
                      ┌────────────────────┐
                      │  Wärmenetz (55°C)  │
                      │  - Heizung         │
                      │  - Warmwasser      │
                      └─────────┬──────────┘
                                │
                    ┌───────────┴───────────┐
                    │   Wärmepumpe (zentral)│
                    │   COP = 4.5           │
                    └───────────┬───────────┘
                                │
                      ┌─────────┴──────────┐
                      │  Kältenetz (8°C)   │
                      │  - Klimatisierung  │
                      │  - Prozess-Kühlung │
                      └─────────┬──────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
    ┌─────────▼─────────┐            ┌──────────▼──────────┐
    │  Chiller           │            │  Free Cooling       │
    │  COP = 5           │            │  (Grundwasser)      │
    │  (Backup)          │            │  Q = 2 MW           │
    └────────────────────┘            └─────────────────────┘
              │
    ┌─────────▼─────────┐
    │  Cooling Tower    │
    │  (Rückkühlung)    │
    └───────────────────┘
              ▲
              │ Abwärme
    ┌─────────┴─────────┐
    │  Rechenzentrum    │
    │  Q_waste = 1 MW   │
    │  T = 35°C         │
    └───────────────────┘
```

### 5.2 Konfiguration

```yaml
# config/systems/integrated_heating_cooling.yaml

networks:
  - id: "heat_net"
    network_type: "heating"
    T_supply: 55
    T_return: 35
    p_nominal: 4

  - id: "cold_net"
    network_type: "cooling"
    T_supply: 8
    T_return: 12
    p_nominal: 5

  - id: "waste_heat_net"
    network_type: "heating"
    T_supply: 35
    T_return: 28
    p_nominal: 3

topology:
  nodes:
    - id: "hp_central"
      type: "converter"
      coordinates: {x: 0, y: 0}

    - id: "heat_consumer_1"
      type: "consumer"
      network: "heat_net"
      coordinates: {x: 500, y: 200}

    - id: "cold_consumer_1"
      type: "consumer"
      network: "cold_net"
      coordinates: {x: 300, y: -200}

    - id: "datacenter_1"
      type: "producer"
      network: "waste_heat_net"
      coordinates: {x: -400, y: 100}

  pipes:
    # ... (Supply + Return für jedes Netz)

components:
  heat_pump_central:
    type: "heat_pump"
    heat_network: "heat_net"
    cold_network: "cold_net"
    Q_max: 5  # MW
    supports_cooling: false

  chiller_backup:
    type: "chiller"
    cold_network: "cold_net"
    chiller_type: "compression"
    Q_cold_max: 3  # MW
    COP_nominal: 5

  free_cooling_groundwater:
    type: "free_cooling"
    cold_network: "cold_net"
    source_type: "groundwater"
    Q_max: 2  # MW
    T_source: 10  # °C

  heat_recovery_datacenter:
    type: "heat_recovery"
    source_network: "waste_heat_net"
    target_network: "heat_net"
    Q_available: 1  # MW
    T_waste: 35  # °C
    requires_heatpump: true
    COP_hp: 3.5
```

### 5.3 Optimierungslogik

**Zielfunktion:**
```
Minimize:
    CAPEX_pipes + CAPEX_pumps + CAPEX_components
    + OPEX_electricity + OPEX_losses
```

**Betriebsstrategie (zeitabhängig):**

```python
# Kälteversorgung (Rangfolge nach Kosten):
# 1. Free Cooling (wenn verfügbar) → Kosten ≈ 0 EUR/MWh
# 2. Wärmepumpe aus Abwärme → Kosten ≈ 20 EUR/MWh
# 3. Chiller (Backup) → Kosten ≈ 50 EUR/MWh

# Wärmeversorgung:
# 1. Abwärme-Rückgewinnung → Kosten ≈ 0 EUR/MWh
# 2. Wärmepumpe aus Kältenetz → Kosten ≈ 25 EUR/MWh
```

**MILP optimiert automatisch:**
- Wann welche Komponente nutzen
- Investition in Rohrdurchmesser
- Pumpendimensionierung
- Speichernutzung (falls vorhanden)

---

## 6. Implementierungs-Erweiterungen

### 6.1 Neue Verzeichnisstruktur

```
energis/models/blocks/
├── network/                    # EXISTIERT
│   ├── pipe.py
│   ├── pump.py
│   └── ...
│
├── cooling/                    # NEU
│   ├── __init__.py
│   ├── chiller.py              # Kältemaschine
│   ├── cooling_tower.py        # Rückkühler
│   └── free_cooling.py         # Free Cooling
│
├── heat_recovery/              # NEU
│   ├── __init__.py
│   └── heat_recovery_unit.py   # Wärmerückgewinnung
│
└── heat_pump.py                # ERWEITERN (Kältenetz-Anbindung)
```

### 6.2 Zeitplan-Erweiterung

**Zusätzlicher Aufwand: +1-2 Wochen**

| **Task** | **Aufwand** | **Komponente** |
|----------|-------------|----------------|
| Chiller | 4 Tage | `chiller.py` |
| Cooling Tower | 2 Tage | `cooling_tower.py` |
| Free Cooling | 3 Tage | `free_cooling.py` |
| Heat Recovery | 4 Tage | `heat_recovery_unit.py` |
| HeatPump erweitern | 2 Tage | Kältenetz-Integration |
| Tests | 2 Tage | Unit + Integration |
| Dokumentation | 1 Tag | User Guide ergänzen |
| **SUMME** | **18 Tage** | **≈ 3 Wochen** |

**Neuer Gesamt-Zeitplan: 8-10 Wochen**

---

## 7. Validierung & Tests

### 7.1 Neue Integrationstests

**`tests/integration/test_cooling_network.py`:**
```python
def test_simple_cooling_network():
    """
    Test Kältenetz mit Chiller und Verbraucher
    """
    # Chiller ──pipe──► Cold Consumer
    # ...

def test_free_cooling_availability():
    """
    Test Free Cooling nur bei niedrigen T_ambient
    """
    # ...

def test_heat_recovery_with_heatpump():
    """
    Test Abwärme-Rückgewinnung mit Wärmepumpe
    """
    # Rechenzentrum (35°C) ──HRU+HP──► Wärmenetz (55°C)
    # ...

def test_integrated_heating_cooling():
    """
    Test gekoppeltes Wärme-Kälte-System
    """
    # Vollständiges System wie in Abschnitt 5
    # ...
```

### 7.2 Validierung gegen Referenzsysteme

**Vergleich mit realen Anlagen:**
- District Cooling Stockholm: 200 MW, 540 GWh/a
- District Cooling Paris La Défense: 80 MW
- Rechenzentrum-Abwärme Zürich: Integration in Fernwärme

**Metriken:**
- COP/EER realistisch? (Vergleich mit Herstellerdaten)
- Wärmeverluste plausibel?
- Investitionskosten im üblichen Rahmen?

---

## 8. Wissenschaftliche Referenzen

### 8.1 District Cooling

**Applied Energy (2023-2024):**
- "Optimal design and operation of district cooling networks with thermal energy storage"
- "Integration of free cooling sources in district cooling systems"

**Energy (2024):**
- "Multi-objective optimization of combined heating and cooling networks"

### 8.2 Wärmerückgewinnung

**Energy Conversion and Management (2024):**
- "Industrial waste heat recovery potential and integration into district heating"
- "Data center waste heat utilization: A techno-economic assessment"

**Renewable and Sustainable Energy Reviews (2023):**
- "Heat recovery from wastewater treatment plants: Technologies and case studies"

### 8.3 Kopplung Wärme-Kälte

**Applied Thermal Engineering (2024):**
- "Simultaneous heating and cooling via bidirectional heat pumps in energy communities"

---

## 9. Zusammenfassung

### 9.1 Was ist neu?

✅ **4 neue Komponenten:**
1. Chiller (Kältemaschine)
2. Cooling Tower (Rückkühler)
3. Free Cooling (natürliche Kältequellen)
4. Heat Recovery Unit (Wärmerückgewinnung)

✅ **Erweiterte Features:**
- Kältenetze als separate Netzwerktypen
- Bidirektionale Wärmepumpen
- Multi-Netz-Integration (Wärme + Kälte + Abwärme)

✅ **Gleiche Modellierungsansätze:**
- Alle Gleichungen bleiben MILP-kompatibel
- PWL + SOS2 für Effizienz-Kurven
- McCormick für bilineare Terme
- NetworkX-basierte Topologie

### 9.2 Aufwand

**Code:** +1200 Zeilen (~30% mehr)
**Zeit:** +3 Wochen (Gesamt: 8-10 Wochen)
**Tests:** +15 Tests
**Dokumentation:** +1 Notebook

### 9.3 Nutzen

🎯 **Vollständige Sektorenkopplung:**
- Wärme, Kälte, Abwärme in einem Modell
- Optimierung über alle Energieformen hinweg

🎯 **Realistische Anwendungsfälle:**
- Moderne Quartiere mit Heizen + Kühlen
- Industriegebiete mit Prozessabwärme
- Rechenzentren als Wärmequelle

🎯 **Wissenschaftlich fundiert:**
- State-of-the-art Literatur
- Validierbar gegen reale Systeme

---

**Empfehlung: JA, unbedingt integrieren!**

Die Erweiterung ist mit minimalem Zusatzaufwand umsetzbar und macht das Framework deutlich leistungsfähiger. Gerade die Kopplung Wärme-Kälte ist hochaktuell für moderne Energiesysteme.

---

**Nächste Schritte:**
1. Requirements-Dokument erweitern
2. Math Design um Cooling-Gleichungen ergänzen
3. Implementation Plan aktualisieren
4. Los implementieren! 🚀
