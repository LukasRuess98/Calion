# Brownfield-Szenario: Schritt-für-Schritt-Anleitung

## Übersicht

Diese Anleitung zeigt, wie Sie ein **Brownfield-Szenario** (Erweiterung eines bestehenden Wärmenetzes) in EnerGIS erstellen und durchrechnen.

**Beispiel-Szenario:** Ein bestehendes gasbetriebenes Fernwärmenetz soll mit einer Wärmepumpe und einem saisonalen Speicher erweitert werden, um den CO₂-Ausstoß zu reduzieren.

---

## Workflow-Optionen

Es gibt **zwei Wege**, um ein Brownfield-Szenario zu erstellen:

### Option 1: Excel-Import (⭐ Empfohlen)

**Vorteile:**
- ✓ Schneller Einstieg (zentrale Excel-Datei statt 500+ Zeilen YAML)
- ✓ Übersichtliche Tabellenstruktur in Excel
- ✓ Automatische Generierung von Rücklaufrohren
- ✓ Automatische Extraktion von Netzknoten
- ✓ Eingebaute Validierung vor YAML-Generierung
- ✓ Alle Zeitreihen in einem Sheet (8760 Zeilen)

**Workflow:**
1. Excel-Template erstellen: `python scripts/create_thermal_network_template.py`
2. Daten in Excel eintragen (6 Sheets: Netzwerk, Erzeuger, Speicher, Rohre, Verbraucher, Zeitreihen)
3. Mit `ThermalNetworkExcelParser` zu YAML konvertieren
4. Validierung läuft automatisch
5. YAML-Dateien werden in `configs/scenarios/` erstellt

**Beispiel:**
```python
from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser

parser = ThermalNetworkExcelParser("data/musterhausen.xlsx")
errors = parser.validate()
if not errors:
    parser.save_yaml("configs/scenarios/musterhausen.scenario.yaml")
```

**➡️ Siehe Notebook:** `notebooks/thermal_network_excel_import.ipynb`

### Option 2: Manuelle YAML-Erstellung

**Vorteile:**
- ✓ Volle Kontrolle über alle Parameter
- ✓ Kein Excel erforderlich
- ✓ Versionskontrolle-freundlich (Text-Format)

**Nachteil:**
- Zeitaufwendig (4-6 Stunden für mittelgroßes Netz)
- Fehleranfällig (Tippfehler, vergessene Rücklaufrohre)

**Workflow:** Siehe Schritte 1-8 unten (manuelles Vorgehen)

---

## ⭐ EXCEL-WORKFLOW (Option 1)

### Schritt A: Template erstellen

```bash
# Template mit allen Sheets erstellen
python scripts/create_thermal_network_template.py --output data/my_network.xlsx

# Für Multi-Sheet-Support: openpyxl installieren
pip install openpyxl
```

### Schritt B: Excel ausfüllen

Öffnen Sie die Datei in Excel und füllen Sie die 6 Sheets aus:

**1. Netzwerk-Sheet:** Netzwerkparameter
```
Parameter           Wert    Einheit  Beschreibung
Name                Musterhausen     Name des Wärmenetzes
T_Vorlauf_nom       90      °C       Nominale Vorlauftemperatur
T_Ruecklauf_nom     50      °C       Nominale Rücklauftemperatur
p_nominal           6       bar      Nominaler Netzdruck
```

**2. Erzeuger-Sheet:** Wärmeerzeuger (Bestand & Investition)
```
ID          Typ         Bestand?  Investition?  Q_nom_MW  Q_options_MW    CAPEX_€_kW  ...
Kessel_1    boiler      ja        nein          15.0                      300
CHP_1       chp         ja        nein          8.0                       1200
WP_1        heat_pump   nein      ja                      5.0,10.0,15.0   800
```

**3. Speicher-Sheet:** Thermische Speicher
```
ID          Typ             Bestand?  Investition?  Kapazitaet_MWh  Kapazitaet_options_MWh  ...
Speicher_1  hot_water_tank  ja        nein          30.0
PTES_1      ptes            nein      ja                            50,100,200
```

**4. Rohre-Sheet:** NUR Vorlaufrohre (Rücklauf wird automatisch generiert!)
```
ID   Von_Knoten    Zu_Knoten       Laenge_m  Bestand?  Investition?  DN_fix  DN_options
P1   gaskessel_01  junction_ctr    100       ja        nein          DN200
P2   chp_01        junction_ctr    150       ja        nein          DN150
P3   junction_ctr  altstadt        5000      ja        nein          DN200
P4   wp_neu        junction_ctr    500       nein      ja                    DN150,DN200,DN250
```

**5. Verbraucher-Sheet:** Wärmeverbraucher
```
ID              Knoten          Lastgang                Spitzenlast_MW  Jahresbedarf_MWh
Altstadt        altstadt        heat_demand_altstadt    12.0            45000
```

**6. Zeitreihen-Sheet:** Alle Lastgänge (8760 Zeilen für Gesamtjahr)
```
Zeitstempel             heat_demand_altstadt  Strompreis_€_MWh  Gaspreis_€_MWh  Aussentemperatur_C
2023-01-01 00:00:00     8.5                   65.2              35.0            -2.5
2023-01-01 01:00:00     8.2                   62.1              35.0            -3.1
...                     ...                   ...               ...             ...
(8760 Zeilen insgesamt)
```

### Schritt C: Konvertieren & Validieren

```python
from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser

# Excel einlesen
parser = ThermalNetworkExcelParser("data/musterhausen.xlsx")

# Zusammenfassung anzeigen
print(parser.get_summary())

# Validierung
errors = parser.validate()
if errors:
    for error in errors:
        print(f"ERROR: {error}")
else:
    print("✓ Konfiguration ist valide!")

    # YAML speichern
    parser.save_yaml("configs/scenarios/musterhausen.scenario.yaml")
    # Erzeugt auch: musterhausen_timeseries.csv
```

**Ausgabe:** YAML-Datei in `configs/scenarios/` mit:
- Netzwerk-Konfiguration
- Alle Komponenten (Bestand + Investition)
- Automatisch generierte Rücklaufrohre
- Automatisch extrahierte Netzknoten
- Referenzen zu Zeitreihendaten

### Schritt D: Simulation durchführen

Verwenden Sie die generierte YAML-Datei in Ihren bestehenden Workflows:

```python
# In Notebook oder Skript
from energis.run import ThermalNetworkOptimizer

optimizer = ThermalNetworkOptimizer("configs/scenarios/musterhausen.scenario.yaml")
results = optimizer.optimize()
results.plot_summary()
```

**➡️ Das war's!** Excel → YAML → Simulation

---

## 📝 MANUELLER WORKFLOW (Option 2)

Falls Sie lieber manuell YAML erstellen (oder Excel-Import nicht verfügbar):

## Schritt 1: Bestandsaufnahme des existierenden Netzes

### 1.1 Erfassen Sie alle bestehenden Komponenten

Erstellen Sie eine Übersicht über Ihr existierendes Netz:

**Tabelle: Bestandsnetz**
| Komponente | Typ | Größe/Parameter | Baujahr | Zustand |
|------------|-----|-----------------|---------|---------|
| Gaskessel | Boiler | 15 MW | 2010 | gut |
| CHP-Anlage | CHP | 8 MW th, 3 MW el | 2015 | gut |
| Hauptpumpe | Pump | 100 kg/s, 5 bar | 2010 | befriedigend |
| Rohrnetz Altstadt | Pipes | DN200, 5 km | 2010 | gut |
| Thermischer Speicher | Storage | 30 MWh | 2012 | gut |

**Topologie-Skizze:**
```
[Gaskessel 15MW] ───┐
                    ├──► [Junction Central] ──► [Altstadt 5km DN200] ──► [Verbraucher]
[CHP 8MW] ──────────┘        ↑                           ↓
                         [Pumpe 100kg/s]             [Rücklauf]
                             ↑
                      [Speicher 30MWh]
```

### 1.2 Erfassen Sie geografische Daten

Notieren Sie die Koordinaten Ihrer Knoten (z.B. in UTM oder lokalem Koordinatensystem):

```yaml
# Beispiel-Koordinaten (in Metern)
nodes_coordinates:
  gaskessel_01: {x: 0, y: 0, z: 0}
  chp_01: {x: 100, y: 50, z: 0}
  junction_central: {x: 200, y: 100, z: 2}
  altstadt_verbrauch: {x: 5200, y: 100, z: 5}
```

### 1.3 Erfassen Sie Lastgangdaten

Sie benötigen:
- **Wärmelast-Profil** der Verbraucher (stündlich, 8760 h)
- **Strompreis-Profil** (für Wärmepumpen-Betrieb)
- **Gaspreise** und **CO₂-Preise**

```
profiles/
├── heat_demand_altstadt.csv       # Wärmelast Altstadt
├── electricity_prices.csv         # Strompreise
├── gas_prices.csv                 # Gaspreise
└── co2_prices.csv                 # CO₂-Preise
```

---

## Schritt 2: Definieren Sie die geplanten Erweiterungen

### 2.1 Neue Komponenten festlegen

Entscheiden Sie, welche neuen Komponenten Sie hinzufügen möchten:

**Tabelle: Geplante Erweiterung**
| Komponente | Typ | Größenoptionen | Standort | Zweck |
|------------|-----|----------------|----------|-------|
| Wärmepumpe | HeatPump | 5/10/15 MW | Bei Junction | Dekarbonisierung |
| PTES Speicher | PTES | 50k/100k/200k m³ | Neues Grundstück | Saisonale Speicherung |
| Anbindung WP | Pipes | DN150/DN200/DN250 | 500m neu | Hydraulik |
| Zusätzliche Pumpe | Pump | 50/100 kg/s | Bei WP | Netzhydraulik |

### 2.2 Neue Topologie skizzieren

```
                                    [NEU: Wärmepumpe 5-15MW]
                                              │
[Gaskessel 15MW] ───┐                        │
                    ├──► [Junction Central] ─┴─► [Altstadt 5km DN200] ──► [Verbraucher]
[CHP 8MW] ──────────┘        ↑                           ↓
                         [Pumpe 100kg/s]             [Rücklauf]
                             ↑
                      [Speicher 30MWh]
                             ↑
                     [NEU: PTES 50k-200k m³]
```

---

## Schritt 3: Erstellen Sie die YAML-Konfiguration

### 3.1 Netzwerk-Definition

**Datei:** `config/networks/brownfield_example.yaml`

```yaml
# ============================================================================
# NETZWERK-DEFINITION
# ============================================================================
networks:
  - id: "dh_ht"
    name: "Fernwärme Hochtemperatur"
    network_type: "heating"
    medium: "water_liquid"
    T_supply: 90        # °C
    T_return: 50        # °C
    p_nominal: 6        # bar
    p_min: 3            # bar
    p_max: 10           # bar

# ============================================================================
# TOPOLOGIE: KNOTEN
# ============================================================================
nodes:
  # BESTANDSKNOTEN
  - id: "gaskessel_node"
    type: "producer"
    network: "dh_ht"
    coordinates: {x: 0, y: 0, z: 0}

  - id: "chp_node"
    type: "producer"
    network: "dh_ht"
    coordinates: {x: 100, y: 50, z: 0}

  - id: "junction_central"
    type: "junction"
    network: "dh_ht"
    coordinates: {x: 200, y: 100, z: 2}

  - id: "altstadt_consumer"
    type: "consumer"
    network: "dh_ht"
    coordinates: {x: 5200, y: 100, z: 5}
    demand_profile: "profiles/heat_demand_altstadt.csv"

  # NEU: Wärmepumpen-Knoten
  - id: "heatpump_node"
    type: "producer"
    network: "dh_ht"
    coordinates: {x: 250, y: 200, z: 2}

  # NEU: PTES-Knoten
  - id: "ptes_node"
    type: "junction"
    network: "dh_ht"
    coordinates: {x: 300, y: -200, z: 0}

# ============================================================================
# TOPOLOGIE: ROHRE (VORLAUF)
# ============================================================================
pipes:
  # BESTAND: Gaskessel → Junction
  - id: "pipe_boiler_junction_supply"
    from: "gaskessel_node"
    to: "junction_central"
    network: "dh_ht"
    pipe_type: "supply"

    existing: true                   # ← BROWNFIELD!
    invest: false
    DN_fixed: "DN200"
    insulation_fixed: "standard"
    installation_year: 2010
    condition: "good"

  # BESTAND: CHP → Junction
  - id: "pipe_chp_junction_supply"
    from: "chp_node"
    to: "junction_central"
    network: "dh_ht"
    pipe_type: "supply"

    existing: true                   # ← BROWNFIELD!
    invest: false
    DN_fixed: "DN150"
    insulation_fixed: "standard"
    installation_year: 2015
    condition: "good"

  # BESTAND: Junction → Altstadt
  - id: "pipe_junction_altstadt_supply"
    from: "junction_central"
    to: "altstadt_consumer"
    network: "dh_ht"
    pipe_type: "supply"

    existing: true                   # ← BROWNFIELD!
    invest: false
    DN_fixed: "DN200"
    insulation_fixed: "standard"
    installation_year: 2010
    condition: "good"
    length: 5000                     # m (explizit, überschreibt Auto-Berechnung)

  # NEU: Wärmepumpe → Junction
  - id: "pipe_hp_junction_supply"
    from: "heatpump_node"
    to: "junction_central"
    network: "dh_ht"
    pipe_type: "supply"

    existing: false                  # ← GREENFIELD (neu zu bauen)!
    invest: true
    DN_options: ["DN150", "DN200", "DN250"]
    insulation_options: ["standard", "good", "excellent"]

  # NEU: Junction → PTES
  - id: "pipe_junction_ptes_supply"
    from: "junction_central"
    to: "ptes_node"
    network: "dh_ht"
    pipe_type: "supply"

    existing: false                  # ← GREENFIELD!
    invest: true
    DN_options: ["DN100", "DN150", "DN200"]
    insulation_options: ["standard", "good"]

  # TODO: Rücklauf-Rohre analog definieren (hier weggelassen für Kürze)

# ============================================================================
# KOMPONENTEN: ERZEUGER
# ============================================================================
components:
  heat_producers:
    # BESTAND: Gaskessel
    - id: "boiler_01"
      type: "Boiler"
      node: "gaskessel_node"
      network: "dh_ht"

      existing: true                 # ← BROWNFIELD!
      invest: false

      Q_th_max: 15.0                 # MW (fix)
      efficiency: 0.92
      fuel_type: "natural_gas"
      installation_year: 2010

      # Kosten
      opex_variable: 45               # EUR/MWh (Gas + Wartung)

    # BESTAND: CHP
    - id: "chp_01"
      type: "CHP"
      node: "chp_node"
      network: "dh_ht"

      existing: true                 # ← BROWNFIELD!
      invest: false

      Q_th_max: 8.0                  # MW (fix)
      P_el_max: 3.0                  # MW (fix)
      efficiency_thermal: 0.55
      efficiency_electrical: 0.35
      fuel_type: "natural_gas"
      installation_year: 2015

      # Kosten
      opex_variable: 40               # EUR/MWh

    # NEU: Wärmepumpe
    - id: "hp_new_01"
      type: "HeatPump"
      node: "heatpump_node"
      network: "dh_ht"

      existing: false                # ← GREENFIELD (neu investieren)!
      invest: true

      Q_th_options: [5.0, 10.0, 15.0]  # MW (zu wählen)
      COP_nominal: 3.5
      T_source: "ambient_air"        # Luftwärmepumpe

      # Kosten
      capex_fixed: 500000            # EUR (Planung, Fundament)
      capex_per_MW: 400000           # EUR/MW
      opex_variable: 25               # EUR/MWh (Strom, Wartung)
      lifetime: 20                    # Jahre

# ============================================================================
# KOMPONENTEN: SPEICHER
# ============================================================================
  storage:
    # BESTAND: Thermischer Kurzzeitspeicher
    - id: "tes_01"
      type: "ThermalStorage"
      node: "junction_central"
      network: "dh_ht"

      existing: true                 # ← BROWNFIELD!
      invest: false

      capacity: 30.0                 # MWh (fix)
      efficiency_charge: 0.98
      efficiency_discharge: 0.98
      self_discharge_rate: 0.005     # %/h
      installation_year: 2012

      # Kosten
      opex_fixed: 5000               # EUR/Jahr (Wartung)

    # NEU: Saisonaler Erdbeckenspeicher (PTES)
    - id: "ptes_new_01"
      type: "PTES"
      node: "ptes_node"
      network: "dh_ht"

      existing: false                # ← GREENFIELD (neu investieren)!
      invest: true

      V_options: [50000, 100000, 200000]  # m³ (zu wählen)
      T_min: 40                      # °C
      T_max: 95                      # °C
      U_value: 0.3                   # W/(m²·K)
      depth: 12                      # m (Durchschnitt)

      # Kosten
      capex_fixed: 750000            # EUR (Genehmigung, Planung)
      capex_per_m3: 70               # EUR/m³ (Aushub, Isolierung)
      capex_lining_per_m2: 45        # EUR/m² (Abdichtung)
      opex_per_m3_year: 0.8          # EUR/(m³·Jahr)
      lifetime: 30                    # Jahre

# ============================================================================
# KOMPONENTEN: PUMPEN
# ============================================================================
  pumps:
    # BESTAND: Hauptpumpe
    - id: "pump_main_01"
      type: "Pump"
      at_node: "junction_central"
      network: "dh_ht"

      existing: true                 # ← BROWNFIELD!
      invest: false

      m_flow_nominal: 100            # kg/s (fix)
      delta_p_max: 5.0               # bar (fix)
      efficiency_nominal: 0.75
      installation_year: 2010
      condition: "fair"              # Etwas gealtert

      # Kosten
      opex_variable: 0.15            # EUR/MWh_el (Strom + Wartung)

    # NEU: Zusatzpumpe für Wärmepumpe
    - id: "pump_hp_01"
      type: "Pump"
      at_node: "heatpump_node"
      network: "dh_ht"

      existing: false                # ← GREENFIELD!
      invest: true

      m_flow_options: [50, 100, 150]  # kg/s (zu wählen)
      delta_p_max: 4.0               # bar
      efficiency_nominal: 0.82

      # Kosten
      capex_fixed: 20000             # EUR
      capex_per_kgs: 500             # EUR/(kg/s)
      opex_variable: 0.12            # EUR/MWh_el
      lifetime: 15                    # Jahre

# ============================================================================
# ZEITREIHEN & RANDBEDINGUNGEN
# ============================================================================
simulation:
  time_horizon: 8760               # Stunden (1 Jahr)
  time_step: 1                      # Stunde
  representative_days: null         # Volle Auflösung

  # Klimadaten
  T_ambient_profile: "profiles/ambient_temperature.csv"
  T_soil_mean: 10.0                 # °C
  T_soil_amplitude: 5.0             # °C

  # Preise
  electricity_price_profile: "profiles/electricity_prices.csv"
  gas_price: 60                     # EUR/MWh
  co2_price: 100                    # EUR/t
  co2_emission_gas: 0.201           # t/MWh

  # Wärmegestehungskosten für Verluste
  heat_cost: 50                     # EUR/MWh

# ============================================================================
# OPTIMIERUNGSZIEL
# ============================================================================
objective:
  minimize:
    - CAPEX_new_components          # Nur neue Komponenten
    - NPV_OPEX_total                # Betrieb ALLER Komponenten
    - CO2_emissions                 # Mit Gewichtung

  discount_rate: 0.04               # 4%
  planning_horizon: 20              # Jahre

  # Gewichtung
  weight_capex: 1.0
  weight_opex: 1.0
  weight_co2: 100                   # EUR/t (implizit via CO2-Preis)

# ============================================================================
# SOLVER-EINSTELLUNGEN
# ============================================================================
solver:
  name: "gurobi"
  options:
    MIPGap: 0.01                    # 1% Optimalitätstoleranz
    TimeLimit: 3600                 # 1 Stunde max.
    Threads: 8
    LogToConsole: 1
```

---

## Schritt 4: Vorbereiten der Zeitreihen

### 4.1 Wärmelast

**Datei:** `profiles/heat_demand_altstadt.csv`

```csv
timestamp,Q_demand_MW
2024-01-01 00:00,8.5
2024-01-01 01:00,7.8
2024-01-01 02:00,7.2
...
2024-12-31 23:00,6.5
```

**Tipp:** Falls Sie keine stündlichen Daten haben:
- Verwenden Sie **Standard-Lastprofile** (BDEW, VDI 4655)
- Skalieren Sie auf Ihre Jahres-Wärmemenge
- Tool: `energis.utils.generate_standard_profile()`

### 4.2 Strompreise

**Datei:** `profiles/electricity_prices.csv`

```csv
timestamp,price_EUR_MWh
2024-01-01 00:00,45.2
2024-01-01 01:00,42.8
2024-01-01 02:00,40.5
...
```

**Quelle:** EPEX Spot Day-Ahead Preise oder Annahmen

### 4.3 Umgebungstemperatur (für Wärmepumpen-COP)

**Datei:** `profiles/ambient_temperature.csv`

```csv
timestamp,T_ambient_C
2024-01-01 00:00,2.5
2024-01-01 01:00,1.8
...
```

**Quelle:** DWD Testreferenzjahre (TRY) für Ihre Region

---

## Schritt 5: Python-Script zum Bauen und Lösen

### 5.1 Hauptscript

**Datei:** `scripts/run_brownfield_optimization.py`

```python
#!/usr/bin/env python3
"""
Brownfield-Optimierung: Erweiterung eines bestehenden Fernwärmenetzes
"""

import yaml
import pyomo.environ as pyo
from pathlib import Path

# EnerGIS Imports
from energis.models.system_builder import SystemBuilder
from energis.models.network.topology import NetworkTopology
from energis.models.network.multi_network import MultiNetworkManager
from energis.utils.results import ResultsProcessor
from energis.utils.visualization import plot_network_topology, plot_operation_results

def main():
    print("=" * 80)
    print("BROWNFIELD-OPTIMIERUNG: Fernwärmenetz-Erweiterung")
    print("=" * 80)

    # ========================================================================
    # SCHRITT 1: Lade Konfiguration
    # ========================================================================
    print("\n[1/7] Lade Konfiguration...")

    config_path = Path("config/networks/brownfield_example.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    print(f"   ✓ Konfiguration geladen: {config_path}")
    print(f"   - Netzwerke: {len(config['networks'])}")
    print(f"   - Knoten: {len(config['nodes'])}")
    print(f"   - Rohre: {len(config['pipes'])}")
    print(f"   - Komponenten: {sum(len(v) for v in config['components'].values())}")

    # ========================================================================
    # SCHRITT 2: Baue Netzwerk-Topologie
    # ========================================================================
    print("\n[2/7] Baue Netzwerk-Topologie...")

    topology = NetworkTopology.from_yaml(config)

    # Validiere Topologie
    errors = topology.validate_topology()
    if errors:
        print("   ❌ FEHLER in Topologie:")
        for error in errors:
            print(f"      - {error}")
        return
    else:
        print("   ✓ Topologie validiert")

    # Visualisiere Netzwerk
    topology.visualize(output_path="results/network_topology.png")
    print("   ✓ Topologie-Visualisierung: results/network_topology.png")

    # ========================================================================
    # SCHRITT 3: Identifiziere Brownfield-Komponenten
    # ========================================================================
    print("\n[3/7] Analysiere Brownfield-Komponenten...")

    existing_components = []
    new_components = []

    # Rohre
    for pipe in config['pipes']:
        if pipe.get('existing', False):
            existing_components.append(f"Pipe: {pipe['id']} (DN{pipe['DN_fixed']})")
        elif pipe.get('invest', False):
            new_components.append(f"Pipe: {pipe['id']} (DN optimieren)")

    # Andere Komponenten
    for comp_type, comp_list in config['components'].items():
        for comp in comp_list:
            if comp.get('existing', False):
                size = comp.get('Q_th_max') or comp.get('capacity') or comp.get('m_flow_nominal')
                existing_components.append(f"{comp_type}: {comp['id']} ({size} fix)")
            elif comp.get('invest', False):
                options = comp.get('Q_th_options') or comp.get('V_options') or comp.get('m_flow_options')
                new_components.append(f"{comp_type}: {comp['id']} ({options} zu wählen)")

    print(f"\n   BESTANDSNETZ ({len(existing_components)} Komponenten):")
    for comp in existing_components:
        print(f"      ✓ {comp}")

    print(f"\n   ERWEITERUNG ({len(new_components)} Komponenten):")
    for comp in new_components:
        print(f"      ⊕ {comp}")

    # ========================================================================
    # SCHRITT 4: Baue Optimierungsmodell
    # ========================================================================
    print("\n[4/7] Baue Optimierungsmodell...")

    # Erstelle Pyomo-Modell
    model = pyo.ConcreteModel(name="BrownfieldOptimization")

    # Zeitset
    T_hours = config['simulation']['time_horizon']
    model.T = pyo.RangeSet(1, T_hours)
    print(f"   - Zeithorizont: {T_hours} Stunden")

    # Monatliches Set (für saisonale Speicher)
    model.M = pyo.RangeSet(1, 12)
    print(f"   - Monatliche Auflösung: 12 Monate (für PTES)")

    # System Builder
    builder = SystemBuilder(config)
    builder.build_network_components(model, topology)
    builder.build_energy_components(model, config)
    builder.add_constraints(model)

    print(f"   ✓ Modell gebaut")
    print(f"   - Variablen: {len(list(model.component_data_objects(pyo.Var)))}")
    print(f"   - Constraints: {len(list(model.component_data_objects(pyo.Constraint)))}")
    print(f"   - Binärvariablen: {sum(1 for v in model.component_data_objects(pyo.Var) if v.is_binary())}")

    # ========================================================================
    # SCHRITT 5: Definiere Zielfunktion
    # ========================================================================
    print("\n[5/7] Definiere Zielfunktion...")

    # CAPEX (nur neue Komponenten)
    capex_expr = builder.calculate_capex(model, only_new=True)

    # OPEX (alle Komponenten)
    opex_expr = builder.calculate_opex(model, all_components=True)

    # NPV
    discount_rate = config['objective']['discount_rate']
    planning_horizon = config['objective']['planning_horizon']

    npv_opex = sum(
        opex_expr * (1 / (1 + discount_rate) ** year)
        for year in range(1, planning_horizon + 1)
    )

    # CO2-Emissionen (monetarisiert)
    co2_emissions = builder.calculate_co2_emissions(model)
    co2_cost = co2_emissions * config['simulation']['co2_price']

    # Gesamtziel
    model.objective = pyo.Objective(
        expr=capex_expr + npv_opex + co2_cost,
        sense=pyo.minimize
    )

    print(f"   ✓ Zielfunktion: min(CAPEX_neu + NPV(OPEX_alle) + CO2_Kosten)")

    # ========================================================================
    # SCHRITT 6: Löse Optimierung
    # ========================================================================
    print("\n[6/7] Löse Optimierung...")
    print(f"   Solver: {config['solver']['name']}")
    print(f"   MIP Gap: {config['solver']['options']['MIPGap'] * 100}%")
    print(f"   Time Limit: {config['solver']['options']['TimeLimit']} s")
    print("\n   ⏳ Optimierung läuft... (dies kann einige Minuten dauern)")

    solver = pyo.SolverFactory(config['solver']['name'])
    for option, value in config['solver']['options'].items():
        solver.options[option] = value

    results = solver.solve(model, tee=True)

    # Check Status
    if results.solver.termination_condition == pyo.TerminationCondition.optimal:
        print("\n   ✓ OPTIMALE LÖSUNG GEFUNDEN!")
    elif results.solver.termination_condition == pyo.TerminationCondition.feasible:
        print("\n   ⚠ ZULÄSSIGE LÖSUNG GEFUNDEN (nicht optimal, aber gültig)")
    else:
        print(f"\n   ❌ FEHLER: {results.solver.termination_condition}")
        return

    # ========================================================================
    # SCHRITT 7: Analysiere Ergebnisse
    # ========================================================================
    print("\n[7/7] Analysiere Ergebnisse...")

    processor = ResultsProcessor(model, config, topology)

    # Extrahiere Ergebnisse
    solution = processor.extract_solution()

    # Investment-Entscheidungen
    print("\n" + "=" * 80)
    print("INVESTMENT-ENTSCHEIDUNGEN")
    print("=" * 80)

    investments = solution['investments']

    print("\n🔹 Wärmepumpe:")
    hp_size = investments['hp_new_01']['Q_th_selected']
    hp_capex = investments['hp_new_01']['CAPEX']
    print(f"   Größe gewählt: {hp_size} MW")
    print(f"   CAPEX: {hp_capex:,.0f} EUR")

    print("\n🔹 PTES Saisonalspeicher:")
    ptes_volume = investments['ptes_new_01']['V_selected']
    ptes_capex = investments['ptes_new_01']['CAPEX']
    print(f"   Volumen gewählt: {ptes_volume:,.0f} m³")
    print(f"   CAPEX: {ptes_capex:,.0f} EUR")

    print("\n🔹 Neue Rohre:")
    for pipe_id, pipe_inv in investments.items():
        if pipe_id.startswith('pipe') and pipe_inv.get('is_new'):
            dn = pipe_inv['DN_selected']
            insul = pipe_inv['insulation_selected']
            length = pipe_inv['length']
            capex = pipe_inv['CAPEX']
            print(f"   {pipe_id}: DN{dn}, {insul}, {length}m → CAPEX: {capex:,.0f} EUR")

    print("\n🔹 Neue Pumpen:")
    pump_size = investments['pump_hp_01']['m_flow_selected']
    pump_capex = investments['pump_hp_01']['CAPEX']
    print(f"   Größe gewählt: {pump_size} kg/s")
    print(f"   CAPEX: {pump_capex:,.0f} EUR")

    # Gesamtkosten
    print("\n" + "=" * 80)
    print("KOSTEN-ZUSAMMENFASSUNG")
    print("=" * 80)

    total_capex = solution['costs']['CAPEX_total']
    opex_year1 = solution['costs']['OPEX_year1']
    npv_20y = solution['costs']['NPV_20years']
    co2_saved = solution['emissions']['CO2_saved_yearly']

    print(f"\n💰 CAPEX (Erweiterung):      {total_capex:>15,.0f} EUR")
    print(f"💰 OPEX (Jahr 1, gesamt):    {opex_year1:>15,.0f} EUR/Jahr")
    print(f"💰 NPV (20 Jahre):           {npv_20y:>15,.0f} EUR")
    print(f"\n🌱 CO₂-Einsparung:           {co2_saved:>15,.0f} t/Jahr")
    print(f"🌱 CO₂-Reduktion:            {co2_saved / solution['emissions']['CO2_baseline'] * 100:>14.1f} %")

    # Betriebsstatistik
    print("\n" + "=" * 80)
    print("BETRIEBSSTATISTIK (Jahr 1)")
    print("=" * 80)

    operation = solution['operation']

    print("\n📊 Wärmeerzeugung:")
    for producer, stats in operation['heat_production'].items():
        print(f"   {producer:30s}: {stats['total_MWh']:>10,.0f} MWh  ({stats['percentage']:>5.1f}%)")

    print("\n📊 Stromverbrauch Wärmepumpe:")
    hp_el = operation['electricity_consumption']['hp_new_01']
    print(f"   Total:     {hp_el['total_MWh']:>10,.0f} MWh")
    print(f"   Ø COP:     {hp_el['avg_COP']:>10.2f}")

    print("\n📊 Speicher-Nutzung:")
    print(f"   Kurzzeitspeicher (TES):  {operation['storage']['tes_01']['cycles_per_year']:>6.1f} Zyklen/Jahr")
    print(f"   Saisonalspeicher (PTES): {operation['storage']['ptes_new_01']['max_SOC_percent']:>6.1f} % max. Füllstand")

    # Visualisierungen
    print("\n" + "=" * 80)
    print("VISUALISIERUNGEN")
    print("=" * 80)

    plot_operation_results(
        solution,
        output_dir="results/plots/",
        show_components=['boiler_01', 'chp_01', 'hp_new_01', 'tes_01', 'ptes_new_01']
    )

    print("\n✓ Ergebnisse gespeichert in: results/")
    print("   - CSV: results/operation_timeseries.csv")
    print("   - Plots: results/plots/*.png")
    print("   - Zusammenfassung: results/summary_report.pdf")

    print("\n" + "=" * 80)
    print("BROWNFIELD-OPTIMIERUNG ABGESCHLOSSEN")
    print("=" * 80)

if __name__ == "__main__":
    main()
```

---

## Schritt 6: Ausführen der Optimierung

### 6.1 Installation prüfen

```bash
# Virtuelle Umgebung aktivieren
source venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt

# Gurobi-Lizenz prüfen
gurobi_cl --version
```

### 6.2 Script ausführen

```bash
# In Projekt-Root wechseln
cd /path/to/Planing-Framework-for-Heat

# Optimierung starten
python scripts/run_brownfield_optimization.py
```

### 6.3 Erwartete Ausgabe

```
================================================================================
BROWNFIELD-OPTIMIERUNG: Fernwärmenetz-Erweiterung
================================================================================

[1/7] Lade Konfiguration...
   ✓ Konfiguration geladen: config/networks/brownfield_example.yaml
   - Netzwerke: 1
   - Knoten: 6
   - Rohre: 10
   - Komponenten: 7

[2/7] Baue Netzwerk-Topologie...
   ✓ Topologie validiert
   ✓ Topologie-Visualisierung: results/network_topology.png

[3/7] Analysiere Brownfield-Komponenten...

   BESTANDSNETZ (7 Komponenten):
      ✓ Pipe: pipe_boiler_junction_supply (DN200)
      ✓ Pipe: pipe_chp_junction_supply (DN150)
      ✓ Pipe: pipe_junction_altstadt_supply (DN200)
      ✓ heat_producers: boiler_01 (15.0 fix)
      ✓ heat_producers: chp_01 (8.0 fix)
      ✓ storage: tes_01 (30.0 fix)
      ✓ pumps: pump_main_01 (100 fix)

   ERWEITERUNG (4 Komponenten):
      ⊕ Pipe: pipe_hp_junction_supply (DN optimieren)
      ⊕ Pipe: pipe_junction_ptes_supply (DN optimieren)
      ⊕ heat_producers: hp_new_01 ([5.0, 10.0, 15.0] zu wählen)
      ⊕ storage: ptes_new_01 ([50000, 100000, 200000] zu wählen)
      ⊕ pumps: pump_hp_01 ([50, 100, 150] zu wählen)

[4/7] Baue Optimierungsmodell...
   - Zeithorizont: 8760 Stunden
   - Monatliche Auflösung: 12 Monate (für PTES)
   ✓ Modell gebaut
   - Variablen: 87,620
   - Constraints: 105,450
   - Binärvariablen: 24

[5/7] Definiere Zielfunktion...
   ✓ Zielfunktion: min(CAPEX_neu + NPV(OPEX_alle) + CO2_Kosten)

[6/7] Löse Optimierung...
   Solver: gurobi
   MIP Gap: 1.0%
   Time Limit: 3600 s

   ⏳ Optimierung läuft... (dies kann einige Minuten dauern)

Gurobi Optimizer version 10.0.0 build ...
...
Optimal solution found (tolerance 1.00e-02)
Best objective 1.234567e+07, best bound 1.234567e+07, gap 0.0%

   ✓ OPTIMALE LÖSUNG GEFUNDEN!

[7/7] Analysiere Ergebnisse...

================================================================================
INVESTMENT-ENTSCHEIDUNGEN
================================================================================

🔹 Wärmepumpe:
   Größe gewählt: 10.0 MW
   CAPEX: 4,500,000 EUR

🔹 PTES Saisonalspeicher:
   Volumen gewählt: 100,000 m³
   CAPEX: 7,750,000 EUR

🔹 Neue Rohre:
   pipe_hp_junction_supply: DN200, good, 120m → CAPEX: 52,000 EUR
   pipe_junction_ptes_supply: DN150, standard, 320m → CAPEX: 98,000 EUR

🔹 Neue Pumpen:
   Größe gewählt: 100 kg/s
   CAPEX: 70,000 EUR

================================================================================
KOSTEN-ZUSAMMENFASSUNG
================================================================================

💰 CAPEX (Erweiterung):         12,470,000 EUR
💰 OPEX (Jahr 1, gesamt):        1,850,000 EUR/Jahr
💰 NPV (20 Jahre):              38,500,000 EUR

🌱 CO₂-Einsparung:               8,500 t/Jahr
🌱 CO₂-Reduktion:                   62.5 %

================================================================================
BETRIEBSSTATISTIK (Jahr 1)
================================================================================

📊 Wärmeerzeugung:
   boiler_01                     :     15,000 MWh  ( 18.5%)
   chp_01                        :     25,000 MWh  ( 30.9%)
   hp_new_01                     :     41,000 MWh  ( 50.6%)

📊 Stromverbrauch Wärmepumpe:
   Total:         11,700 MWh
   Ø COP:           3.51

📊 Speicher-Nutzung:
   Kurzzeitspeicher (TES):     145.2 Zyklen/Jahr
   Saisonalspeicher (PTES):     78.5 % max. Füllstand

================================================================================
VISUALISIERUNGEN
================================================================================

✓ Ergebnisse gespeichert in: results/
   - CSV: results/operation_timeseries.csv
   - Plots: results/plots/*.png
   - Zusammenfassung: results/summary_report.pdf

================================================================================
BROWNFIELD-OPTIMIERUNG ABGESCHLOSSEN
================================================================================
```

---

## Schritt 7: Ergebnisse interpretieren

### 7.1 Investment-Entscheidungen

**Optimales Design:**
- **Wärmepumpe**: 10 MW (mittelgroß → deckt Grundlast)
- **PTES**: 100.000 m³ (mittelgroß → ausreichend für saisonale Speicherung)
- **Neue Rohre**: DN200 für Hauptanbindung, DN150 für Speicher
- **Pumpe**: 100 kg/s (ausreichend für WP-Betrieb)

**Interpretation:** Der Optimierer wählt mittlere Größen, da:
- Kleinere Größen → höhere OPEX (mehr Gas-Backup)
- Größere Größen → höhere CAPEX (unwirtschaftlich)

### 7.2 Wirtschaftlichkeit

**Amortisation:**
```
CAPEX_total = 12,47 Mio EUR
OPEX_Einsparung ≈ 800.000 EUR/Jahr (weniger Gas)
→ Amortisation ≈ 15,6 Jahre

Bei CO₂-Preis 150 EUR/t:
OPEX_Einsparung ≈ 1,22 Mio EUR/Jahr
→ Amortisation ≈ 10,2 Jahre
```

**Sensitivität:** Führen Sie Sensitivitätsanalysen durch:
```python
# Variiere CO₂-Preis, Gaspreise, Strompreise
for co2_price in [50, 100, 150, 200]:
    # Re-optimiere...
```

### 7.3 Betrieb

**Wärmepumpe:**
- Deckt 50,6% der Wärmeerzeugung (Grundlast)
- COP ≈ 3,5 (sehr gut für Luftwärmepumpe)
- Läuft hauptsächlich im Sommer (günstiger Strom + PTES-Ladung)

**PTES:**
- Wird im Sommer geladen (78,5% Füllstand)
- Entlädt im Winter (Spitzenlast-Abdeckung)
- Vermeidet Gas-Spitzenlast-Kessel

**Gaskessel + CHP:**
- CHP läuft weiter (Grundlast + Stromproduktion)
- Gaskessel nur noch Spitzenlast (18,5% statt 45%)

---

## Schritt 8: Sensitivitätsanalyse & Varianten

### 8.1 Varianten erstellen

**Szenario 1: Ohne PTES**
```yaml
# In config: ptes_new_01 deaktivieren
  - id: "ptes_new_01"
    existing: false
    invest: false        # ← NICHT investieren
```

**Szenario 2: Geothermie statt Luft-WP**
```yaml
  - id: "hp_new_01"
    T_source: "geothermal"   # ← Geothermie
    COP_nominal: 4.5         # Höherer COP
```

**Szenario 3: CHP-Stilllegung**
```yaml
  - id: "chp_01"
    existing: true
    allow_decommission: true  # ← Kann abgeschaltet werden
```

### 8.2 Batch-Optimierung

```python
scenarios = [
    {"name": "Base", "co2_price": 100, "ptes": True},
    {"name": "No_PTES", "co2_price": 100, "ptes": False},
    {"name": "High_CO2", "co2_price": 200, "ptes": True},
    {"name": "Low_CO2", "co2_price": 50, "ptes": True},
]

for scenario in scenarios:
    # Modifiziere config
    # Optimiere
    # Speichere Ergebnisse
```

---

## Troubleshooting

### Problem 1: Infeasible Model

**Symptom:** `InfeasibleModel` oder keine Lösung gefunden

**Lösungen:**
1. **Check Wärmebilanz**: Ist genug Erzeugungskapazität?
   ```python
   total_demand = max(Q_demand_profile)
   total_capacity = Q_boiler + Q_chp + Q_hp_max
   assert total_capacity >= total_demand * 1.1  # 10% Reserve
   ```

2. **Check Hydraulik**: Sind Massenströme physikalisch?
   ```python
   m_max = Q_max / (cp * ΔT)
   assert m_flow_max >= m_max
   ```

3. **Relax Constraints**: Temporär Grenzen erweitern
   ```python
   p_min: 2.5  # statt 3.0
   ```

### Problem 2: Sehr lange Laufzeit

**Symptom:** Nach 1 Stunde immer noch kein Ergebnis

**Lösungen:**
1. **Reduziere Zeitauflösung**:
   ```yaml
   representative_days: 12  # 12 Tage statt 8760h
   ```

2. **Erhöhe MIP Gap**:
   ```yaml
   MIPGap: 0.05  # 5% statt 1%
   ```

3. **Warm Start**: Nutze vorherige Lösung
   ```python
   # Lade vorherige Lösung
   model.load_solution("previous_solution.json")
   ```

### Problem 3: Unplausible Ergebnisse

**Symptom:** WP hat Größe 0 MW oder PTES nie genutzt

**Lösungen:**
1. **Check Kosten**: Sind Preise realistisch?
   ```python
   # Gaspreise zu niedrig → WP nicht wirtschaftlich
   gas_price: 60  # EUR/MWh (realistisch?)
   ```

2. **Check Zeitreihen**: Sind Profile korrekt?
   ```python
   # Plotte Lastgang
   import matplotlib.pyplot as plt
   plt.plot(Q_demand_profile)
   plt.show()
   ```

3. **Forciere Investment**: Mindestgröße
   ```yaml
   Q_th_min: 5.0  # MW (mindestens)
   ```

---

## Zusammenfassung: Ihre Checkliste

✅ **Vor der Optimierung:**
- [ ] Bestandsnetz dokumentiert (Komponenten, Größen, Zustand)
- [ ] Geografische Daten erfasst (Koordinaten, Rohrlängen)
- [ ] Zeitreihen vorbereitet (Lastgänge, Preise, Klima)
- [ ] YAML-Konfiguration erstellt
- [ ] `existing: true` für Bestandskomponenten gesetzt
- [ ] `invest: true` für neue Komponenten gesetzt
- [ ] Kataloge vorhanden (Rohre, Pumpen, etc.)

✅ **Nach der Optimierung:**
- [ ] Lösung ist optimal (oder zulässig)
- [ ] Investment-Entscheidungen plausibel
- [ ] Wärmebilanz stimmt (Erzeugung = Verbrauch + Verluste)
- [ ] Kosten realistisch (CAPEX, OPEX, NPV)
- [ ] CO₂-Reduktion sinnvoll
- [ ] Betriebsstatistik plausibel
- [ ] Visualisierungen erstellt

✅ **Weiterführend:**
- [ ] Sensitivitätsanalysen durchgeführt
- [ ] Varianten verglichen
- [ ] Bericht erstellt
- [ ] Stakeholder informiert

---

## Nächste Schritte

1. **Passen Sie das Beispiel an Ihr reales Netz an**
   - Ersetzen Sie die Beispiel-Werte durch Ihre echten Daten
   - Laden Sie Ihre Zeitreihen

2. **Führen Sie die Optimierung durch**
   - Starten Sie mit einem vereinfachten Modell (wenige Zeitschritte)
   - Erhöhen Sie dann die Komplexität

3. **Analysieren Sie die Ergebnisse**
   - Prüfen Sie Plausibilität
   - Diskutieren Sie mit Experten

4. **Varianten-Vergleich**
   - Testen Sie verschiedene Szenarien
   - Identifizieren Sie robuste Lösungen

5. **Implementierung**
   - Nutzen Sie die Ergebnisse für Ihre Planung
   - Erstellen Sie Ausschreibungen basierend auf den optimalen Größen

---

**Viel Erfolg mit Ihrer Brownfield-Optimierung! 🚀**

Bei Fragen: Siehe `docs/thermal_network_requirements.md` Sektion 7.4 für detaillierte Spezifikationen.
