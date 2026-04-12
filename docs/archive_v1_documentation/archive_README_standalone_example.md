# Standalone Heat Planning Example

## Übersicht

Dieses Beispiel zeigt ein **vollständiges, eigenständiges Heat Planning System** in einem einzigen Python-Script. Es demonstriert:

- ✅ **Umfangreiche ENV-basierte Konfiguration** - Alle Parameter über Environment Variables steuerbar
- ✅ **Excel-Datenlader** mit robuster Zeitreihenverarbeitung
- ✅ **COP-Lookup-Tabellen** für Wärmepumpen mit bilinearer Interpolation
- ✅ **Planning Framework (PF)** - Design-Optimierung für Kapazitäten
- ✅ **Rolling Horizon (RH)** - Operative Betriebsoptimierung
- ✅ **Multi-Komponenten-System** - HP1-4, HKW, GTOST, P2H, BMHKW, HWS, HWW, AVA, Speicher
- ✅ **Flexible Export-Funktionen** - Excel und JSON

## Komponenten

### System-Komponenten

| Komponente | Beschreibung | Kapazität (Beispiel) |
|------------|--------------|---------------------|
| HP1-4 | Wärmepumpen mit dynamischen COPs | Optimiert (PF) |
| HKW | Heizkraftwerk (Gas) | 0-50 MW |
| GTOST | Gas-Turbine ORC-System | 0-30 MW |
| P2H | Power-to-Heat | 0-20 MW |
| BMHKW | Biomasse-Heizkraftwerk | 0-25 MW |
| HWS/HWW | Heizwerke (Süd/West) | 0-15 MW je |
| AVA | Abfallverwertungsanlage | 0-20 MW |
| Storage | Thermischer Speicher | Optimiert (PF) |

## Installation & Voraussetzungen

```bash
# Pyomo und Solver installieren
pip install pyomo pandas numpy openpyxl

# Solver (einer davon):
# - CBC (Open Source): conda install -c conda-forge coincbc
# - Gurobi (Kommerziell): siehe https://www.gurobi.com/
# - GLPK (Open Source): conda install -c conda-forge glpk
```

## Verwendung

### 1. Basis-Ausführung (Planning Framework)

```bash
python examples/standalone_heat_planning_example.py
```

**Standard-Einstellungen:**
- `RUN_MODE=PF_ONLY` - Nur Design-Optimierung
- `SOLVER_NAME=cbc` - CBC Solver
- `YEAR_TARGET=2023` - Zieljahr
- Input: `Import_Data.xlsx` (im Root-Verzeichnis)

### 2. Mit Environment Variables

```bash
# Komplett-Lauf (PF + RH)
RUN_MODE=PF_THEN_RH SCENARIO_TITLE=HP_v3_CO2_100 python examples/standalone_heat_planning_example.py

# Rolling Horizon mit bestehendem Design
RUN_MODE=RH_ONLY python examples/standalone_heat_planning_example.py

# Anderen Solver verwenden
SOLVER_NAME=gurobi SOLVER_TEE=1 python examples/standalone_heat_planning_example.py

# CO2-Kosten anpassen
CO2_PRICE_EUR_PER_T=150 INCLUDE_CO2_COST_IN_OBJECTIVE=1 python examples/standalone_heat_planning_example.py
```

### 3. Erweiterte Konfiguration

```bash
# Alle wichtigen Parameter
RUN_MODE=PF_THEN_RH \
SCENARIO_TITLE=Sensitivity_Gas_High \
YEAR_TARGET=2023 \
DT_H=1.0 \
SOLVER_NAME=gurobi \
GASPREIS_EUR_PER_MWh_th=85.0 \
CO2_PRICE_EUR_PER_T=200 \
HEAT_HORIZON_HOURS=168 \
STEP_HOURS=24 \
RH_TERMINAL_POLICY=geq \
EXPORT_BASE_DIR=exports/sensitivity \
python examples/standalone_heat_planning_example.py
```

## Konfiguration

### Wichtige Environment Variables

#### Laufmodus
- `RUN_MODE` - Ausführungsmodus:
  - `PF_ONLY` - Nur Planning Framework (Design-Optimierung)
  - `RH_ONLY` - Nur Rolling Horizon (benötigt existierendes Design)
  - `PF_THEN_RH` - Erst PF, dann RH (Empfohlen)

#### Solver & Datei-Pfade
- `SOLVER_NAME` - Solver: `cbc`, `gurobi`, `glpk` (Default: `cbc`)
- `SOLVER_TEE` - Solver-Output anzeigen: `0` oder `1` (Default: `1`)
- `INPUT_XLSX` - Eingabe-Datei (Default: `Import_Data.xlsx`)
- `EXPORT_BASE_DIR` - Export-Verzeichnis (Default: `exports`)
- `SCENARIO_TITLE` - Szenario-Name (Default: `HP_v3_CO2_100`)

#### Zeiteinstellungen
- `YEAR_TARGET` - Zieljahr (Default: `2023`)
- `DT_H` - Zeitschritt in Stunden (Default: `1.0`)
- `HEAT_HORIZON_HOURS` - RH Horizont (Default: `168` = 7 Tage)
- `STEP_HOURS` - RH Schritt (Default: `24`)

#### Preise (EUR)
- `LEISTUNGSPREIS_EUR_PER_MW` - Demand Charge (Default: `127240`)
- `GRIDCOST_EUR_PER_MWh` - Netzentgelte (Default: `61.6`)
- `GASPREIS_EUR_PER_MWh_th` - Gaspreis thermisch (Default: `58.6`)
- `BIOMASSEPREIS_EUR_PER_MWh_th` - Biomassepreis (Default: `20.0`)
- `ABFALLPREIS_EUR_PER_MWh_th` - Abfallpreis (Default: `10.0`)
- `CO2_PRICE_EUR_PER_T` - CO₂-Preis pro Tonne (Default: `100.0`)

#### Einspeise-Mechanik
- `EINSPEISE_FLOOR_EUR_PER_MWh` - Mindest-Einspeisevergütung (Default: `0.0`)
- `SELL_HAIRCUT` - Verkaufs-Rabatt (Default: `0.05`)
- `SELL_SPREAD` - Spread (Default: `5.0`)
- `SELL_FEE` - Gebühr (Default: `5.0`)
- `SELL_PREMIUM` - Premium (Default: `0.0`)

#### Kosten-Schalter (Boolean: `0` oder `1`)
- `INCLUDE_GRIDCOST_IN_ENERGY` - Netzentgelte in Energiekosten (Default: `0`)
- `INCLUDE_DEMAND_CHARGE_IN_RH` - Demand Charge in RH (Default: `0`)
- `INCLUDE_INVEST_COSTS_IN_RH` - Investkosten in RH (Default: `0`)
- `INCLUDE_INSTALL_COSTS_IN_RH` - Installationskosten in RH (Default: `0`)
- `INCLUDE_CO2_COST_IN_OBJECTIVE` - CO₂-Kosten aktivieren (Default: `1`)

#### Rolling Horizon
- `RH_TERMINAL_POLICY` - Speicher-Endwert-Strategie:
  - `equal` - Gleich wie Anfang (≥ und ≤)
  - `geq` - Mindestens wie Anfang (≥)
  - `free` - Keine Einschränkung

## Input-Daten Format

Die `Import_Data.xlsx` muss folgende Spalten enthalten:

| Spalte | Beschreibung | Einheit |
|--------|--------------|---------|
| `Datum` | Zeitstempel | DateTime |
| `Day_Ahead_Price €/MWh` | Strompreis | EUR/MWh |
| `Wärmebedarf MW` | Wärmebedarf | MW (thermisch) |
| `CO2_consumption_based kgCO2/MWh` | CO₂-Intensität Netz | kg CO₂/MWh |
| `WRG1Q MW` ... `WRG4Q MW` | Wärmerückgewinnung Leistung | MW (thermisch) |
| `WRG1_T °C` ... `WRG4_T °C` | Wärmerückgewinnung Temperatur | °C |

**Hinweise:**
- Spalten-Namen sind flexibel (fuzzy matching)
- Zeitzone: Default `Europe/Berlin`
- Fehlende Zeitschritte werden interpoliert
- Duplikate werden entfernt

## Ausgabe / Exports

### Planning Framework (PF)

**Datei:** `{EXPORT_BASE_DIR}/{SCENARIO_TITLE}_PF.xlsx`

Sheets:
- `Input_Data` - Eingangsdaten
- `heat_production` - Wärmeerzeugung aller Komponenten
- `storage` - Speicher-Level, Laden, Entladen
- `grid` - Netzbezug und Einspeisung
- `design` - Optimierte Kapazitäten

**JSON:** `{EXPORT_BASE_DIR}/pf_design.json`
```json
{
  "storage_capacity": 15000.0,
  "storage_power": 25.5,
  "HP_cap": {
    "1": 45.2,
    "2": 38.7,
    "3": 42.1,
    "4": 39.8
  }
}
```

### Rolling Horizon (RH)

**Datei:** `{EXPORT_BASE_DIR}/{SCENARIO_TITLE}_RH.xlsx`

Sheets:
- `Input_Data` - Eingangsdaten
- `RH_heat_production` - Operative Wärmeerzeugung
- `RH_storage` - Operative Speicher-Nutzung
- `RH_grid` - Operative Netzbezüge

### Combined (PF_THEN_RH)

**Datei:** `{EXPORT_BASE_DIR}/{SCENARIO_TITLE}_Combined.xlsx`

Enthält alle PF- und RH-Sheets in einer Datei.

## Beispiel-Workflows

### Szenario-Analyse

```bash
# Basis-Szenario
SCENARIO_TITLE=Base_CO2_100 CO2_PRICE_EUR_PER_T=100 \
  python examples/standalone_heat_planning_example.py

# Hoher CO2-Preis
SCENARIO_TITLE=High_CO2_200 CO2_PRICE_EUR_PER_T=200 \
  python examples/standalone_heat_planning_example.py

# Niedriger Gaspreis
SCENARIO_TITLE=Low_Gas_40 GASPREIS_EUR_PER_MWh_th=40 \
  python examples/standalone_heat_planning_example.py
```

### Sensitivitäts-Studie

```bash
#!/bin/bash
# sensitivity_study.sh

for CO2 in 50 100 150 200; do
  for GAS in 40 58.6 80 100; do
    SCENARIO_TITLE="Sens_CO2_${CO2}_Gas_${GAS}" \
    CO2_PRICE_EUR_PER_T=$CO2 \
    GASPREIS_EUR_PER_MWh_th=$GAS \
    RUN_MODE=PF_ONLY \
    EXPORT_BASE_DIR="exports/sensitivity" \
    python examples/standalone_heat_planning_example.py
  done
done
```

### Nur Design (schnell)

```bash
# Nur PF für Design-Exploration
RUN_MODE=PF_ONLY SOLVER_NAME=gurobi \
  python examples/standalone_heat_planning_example.py
```

### Design laden + RH ausführen

```bash
# 1. Design erstellen
RUN_MODE=PF_ONLY SCENARIO_TITLE=Design_v1 \
  python examples/standalone_heat_planning_example.py

# 2. RH mit diesem Design
RUN_MODE=RH_ONLY SCENARIO_TITLE=Design_v1 \
  PF_DESIGN_JSON=exports/pf_design.json \
  python examples/standalone_heat_planning_example.py
```

## COP-Berechnung

Das Script verwendet eine **bilineare Interpolation** für Wärmepumpen-COPs basierend auf:

- **Quelle-Eintrittstemperatur** (`Tsourcein`): 303.15 - 353.15 K
- **Quelle-Austrittstemperatur** (`Tsourceout`): `Tsourcein - ΔT`
- **ΔT-Werte**: 10, 20, 30, 40, 50 K

**Formel:**
```python
LMTD_sink = lmtd(Tsink_out, Tsink_in)
LMTD_source = lmtd(Tsourcein, Tsourceout)

mdts = 0.2*(Tsink_out - Tsourceout + 2*deltaTpp) + 0.2*(Tsink_out - Tsink_in) + 0.016
qww  = 0.0014*(Tsink_out - Tsourceout + 2*deltaTpp) - 0.0015*(Tsink_out - Tsink_in) + 0.039

A = LMTD_sink / (LMTD_sink - LMTD_source)
B = (1 + (mdts + deltaTpp)/LMTD_sink) / (1 + (mdts + 0.5*dT + 2*deltaTpp)/(LMTD_sink - LMTD_source))

COP = A * B * eta * (1 - qww) + 1 - eta - FQ
```

**Bounds:** `0.5 ≤ COP ≤ 12.0`

## Modell-Details

### Planning Framework (PF)

**Zielfunktion:**
```
min: Energiekosten + Demand Charge + Brennstoffkosten + CAPEX (annualisiert) + CO₂-Kosten
```

**Design-Variablen:**
- `HP_cap[i]` - Wärmepumpen-Kapazitäten
- `storage_capacity` - Speicher-Energiekapazität
- `storage_power` - Speicher-Leistung

**Constraints:**
- Wärmebilanz (Erzeugung = Bedarf + Speicher)
- HP-Kapazitätsgrenzen
- Speicher-Dynamik
- Netzbilanz
- Terminal-Policy für Speicher

### Rolling Horizon (RH)

**Zielfunktion:**
```
min: Energiekosten + Brennstoffkosten + CO₂-Kosten [+ optional Demand Charge]
```

**Fixiert (aus PF):**
- HP-Kapazitäten
- Speicher-Kapazität/-Leistung

**Optimiert:**
- Operative Erzeugung aller Komponenten
- Speicher-Lade-/Entladeplan
- Netzbezug/-einspeisung

## Troubleshooting

### Problem: "Datei nicht gefunden: Import_Data.xlsx"

**Lösung:**
```bash
# Pfad anpassen
INPUT_XLSX=/pfad/zu/Import_Data.xlsx python examples/standalone_heat_planning_example.py
```

### Problem: Solver nicht gefunden

**Lösung:**
```bash
# CBC installieren
conda install -c conda-forge coincbc

# Oder anderen Solver verwenden
SOLVER_NAME=glpk python examples/standalone_heat_planning_example.py
```

### Problem: "Fehlende Spalte. Gesucht eine von: ..."

**Lösung:** Excel-Datei prüfen und Spalten-Namen anpassen. Das Script versucht fuzzy matching, aber grundlegende Namen müssen vorhanden sein.

### Problem: "NaN in Import_Data"

**Lösung:** Fehlende Werte in Excel füllen oder:
```python
# gap_strategy ändern in load_input_excel():
gap_strategy="interp"  # Interpolation statt Fehler
```

### Problem: Solver findet keine optimale Lösung

**Mögliche Ursachen:**
- Infeasible model (Constraints zu restriktiv)
- Unbounded model (Zu viele Freiheitsgrade)
- Numerische Probleme

**Debug:**
```bash
# Solver-Output anzeigen
SOLVER_TEE=1 python examples/standalone_heat_planning_example.py

# Komponenten deaktivieren (in ENABLE_CONFIG)
# ... oder direkt über Code-Änderungen
```

## Erweiterungen

### Eigene Komponenten hinzufügen

1. In `_build_common_blocks()` neue Variablen definieren
2. In `build_pf_model()` / `build_rh_model()` Constraints hinzufügen
3. In `extract_results()` Ergebnisse auslesen

**Beispiel:**
```python
# Variable
m.MyComponent_Q = Var(m.t, domain=NonNegativeReals, bounds=(0, 50))

# Constraint (in heat_balance_rule)
supply = ... + mm.MyComponent_Q[t]

# Fuel cost (in objective_rule)
fuel_cost = ... + mm.MyComponent_Q[t] * mm.MyFuelPrice
```

### COP-Tabelle anpassen

Ändern Sie die Parameter in Zeile ~250:
```python
Tsourcein_vals = np.linspace(280.15, 360.15, 10)  # Mehr Stützstellen
deltaT_vals = np.array([5, 10, 15, 20, 25, 30, 40, 50])  # Feinere Schritte
```

### Terminal-Policy anpassen

Neue Policy in `_apply_terminal_policy()` hinzufügen:
```python
elif policy == "min_50pct":
    m.soc_terminal_geq.deactivate()
    m.soc_terminal_custom = Constraint(expr = m.storage_level[m.t.last()] >= 0.5 * m.storage_capacity)
```

## Lizenz

Siehe Haupt-Repository.

## Kontakt / Support

Bei Fragen zum Framework oder diesem Beispiel siehe `README.md` im Haupt-Verzeichnis.

---

**Erstellt:** 2024
**Letzte Änderung:** 2024-11-18
