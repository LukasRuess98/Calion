# Stratified Storage Integration Guide

## Übersicht

Dieser Leitfaden erklärt, wie Sie die **StratifiedStorageBlock**-Komponente in Ihr bestehendes EnerGIS Heat Planning System integrieren.

## Quick Start

### 1. Komponente ist bereits registriert

Die Komponente ist automatisch über den Component Registry verfügbar:

```python
from energis.models import ComponentRegistry

# Prüfen ob verfügbar
assert "stratified_storage" in ComponentRegistry.list_components()

# Komponente erstellen
storage = ComponentRegistry.create(
    "stratified_storage",
    name="MyStorage",
    T_hot_C=90.0,
    T_cold_C=40.0,
    investable=True,
    e_cap_min=100.0,
    e_cap_max=1000.0,
    p_cap_min=20.0,
    p_cap_max=150.0
)
```

### 2. Integration in YAML-Konfiguration

Fügen Sie die Komponente zu Ihrer System-Konfiguration hinzu:

```yaml
# configs/systems/your_system.yaml

system:
  stratified_storage:
    - id: main_storage
      component_type: stratified_storage
      enabled: true

      # Thermal parameters
      T_hot_C: 90.0
      T_cold_C: 40.0
      T_ambient_C: 15.0
      T_ground_C: 10.0

      # Geometry
      aspect_ratio: 1.5
      geometry_type: tank

      # Heat transfer [W/(m²·K)]
      U_top: 0.3
      U_side: 0.2
      U_bottom: 0.15

      # Efficiency
      eff_c: 0.95
      eff_d: 0.95

      # Investment
      investment:
        enabled: true
        energy_capacity_min_mwh: 100.0
        energy_capacity_max_mwh: 1000.0
        power_capacity_min_mw: 20.0
        power_capacity_max_mw: 150.0
```

Vollständige Konfigurationsbeispiele finden Sie in:
- `configs/systems/district_heating_stratified_example.yaml`

### 3. Verwendung mit bestehendem Runner

#### Option A: Mit Orchestrator

```python
from energis.run.orchestrator import run_scenario

# Standard-Orchestrator verwendet automatisch YAML-Konfiguration
results = run_scenario(
    config_path="configs/systems/district_heating_stratified_example.yaml",
    input_xlsx="Import_Data.xlsx",
    solver="gurobi"
)
```

#### Option B: Standalone Integration

Siehe `examples/stratified_storage_integration.py` für vollständiges Beispiel:

```python
from energis.models.blocks.stratified_storage import StratifiedStorageBlock

# Erstellen
storage = StratifiedStorageBlock(
    name="TES",
    T_hot_C=90.0,
    T_cold_C=40.0,
    investable=True,
    e_cap_min=100.0,
    e_cap_max=1000.0,
    p_cap_min=20.0,
    p_cap_max=150.0,
    # ... weitere Parameter
)

# In Pyomo-Modell integrieren
storage_result = storage.attach(model, time_set, config, buses)

# Zugriff auf Variablen
E_total = storage_result['state']              # SOC [MWh]
Qc = storage_result['flows']['heat']['input']  # Charging [MW]
Qd = storage_result['flows']['heat']['output'] # Discharging [MW]
V_hot = storage_result['zones']['V_hot']       # Hot volume [m³]
V_cold = storage_result['zones']['V_cold']     # Cold volume [m³]
```

## Solver-Konfiguration mit Gurobi

### Gurobi installieren

```bash
# Mit Conda (empfohlen)
conda install -c gurobi gurobi

# Oder mit pip
pip install gurobipy
```

### Gurobi-Lizenz

Gurobi benötigt eine Lizenz:
- **Akademisch**: Kostenlose Lizenz unter https://www.gurobi.com/academia/
- **Kommerziell**: Lizenz erforderlich

Lizenz aktivieren:
```bash
grbgetkey YOUR-LICENSE-KEY
```

### Solver in Konfiguration setzen

```yaml
# configs/systems/your_system.yaml

solver:
  name: gurobi

  options:
    MIPGap: 0.01          # 1% Optimalitätslücke
    TimeLimit: 600        # 10 Minuten Zeitlimit
    Threads: 0            # Alle verfügbaren Threads
    LogToConsole: 1       # Solver-Output anzeigen
    NumericFocus: 0       # Standard numerische Stabilität

    # Weitere Optionen (optional):
    # Presolve: 2         # Aggressives Presolve
    # Method: 2           # Barrier-Methode
    # MIPFocus: 1         # Fokus auf Feasibility
```

### Solver programmatisch verwenden

```python
from pyomo.opt import SolverFactory

# Solver erstellen
solver = SolverFactory('gurobi')

# Optionen setzen
solver.options['MIPGap'] = 0.01
solver.options['TimeLimit'] = 600
solver.options['Threads'] = 4

# Lösen
results = solver.solve(model, tee=True)
```

### Fallback auf CBC

Wenn Gurobi nicht verfügbar ist, verwendet das System automatisch CBC:

```python
try:
    solver = SolverFactory('gurobi')
    if not solver.available():
        solver = SolverFactory('cbc')
except:
    solver = SolverFactory('cbc')
```

## Export-Funktionen

### Automatischer Export mit Orchestrator

Der Orchestrator exportiert automatisch:

```yaml
export:
  directory: exports/my_scenario
  formats:
    - excel   # Haupt-Excel-Datei
    - csv     # Separate CSV-Dateien
    - json    # JSON-Metadaten

  plots:
    enabled: true
    formats:
      - png
      - pdf
```

Exportierte Dateien:
```
exports/my_scenario/
├── results.xlsx          # Hauptdatei mit allen Sheets
├── heat_pump.csv         # Wärmepumpen-Zeitreihen
├── storage.csv           # Speicher-Zeitreihen (inkl. V_hot, V_cold!)
├── investment.csv        # Investment-Ergebnisse
├── solver_info.json      # Solver-Metadaten
└── plots/
    ├── storage_soc.png
    ├── storage_zones.png
    └── power_balance.png
```

### Manuelle Export-Kontrolle

```python
from energis.io.exporter import export_scenario_bundle

# Ergebnisse extrahieren (aus gelöstem Modell)
results = {
    'storage': storage_df,
    'heat_pump': hp_df,
    'investment': inv_df
}

# Exportieren
export_scenario_bundle(
    results=results,
    export_dir="exports/custom",
    scenario_name="MyScenario",
    include_plots=True
)
```

## Spezifische Anwendungsfälle

### Fall 1: Fernwärme-Pufferspeicher (Stunden-Tage)

```yaml
stratified_storage:
  - id: dh_buffer
    T_hot_C: 90.0
    T_cold_C: 40.0
    aspect_ratio: 1.5
    geometry_type: tank
    U_top: 0.3
    U_side: 0.2
    U_bottom: 0.15
    investment:
      energy_capacity_max_mwh: 500.0   # ~12h bei 40 MW
      power_capacity_max_mw: 100.0
```

**Typische Ergebnisse:**
- Volumen: ~8.600 m³
- Durchmesser: ~19 m
- Höhe: ~28 m
- Tägliche Verluste: ~2-5%

### Fall 2: Saisonaler Erdbeckenspeicher (PTES)

```yaml
stratified_storage:
  - id: seasonal_ptes
    T_hot_C: 95.0
    T_cold_C: 30.0
    aspect_ratio: 0.4        # Flaches Becken
    geometry_type: pit
    U_top: 0.15              # Isolierte Abdeckung
    U_side: 0.03             # Erdreich
    U_bottom: 0.01           # Tiefes Erdreich
    investment:
      energy_capacity_max_mwh: 50000.0  # Saisonal
      power_capacity_max_mw: 500.0
```

**Typische Ergebnisse:**
- Volumen: ~600.000 m³
- Durchmesser: ~125 m
- Tiefe: ~50 m
- Jährliche Verluste: ~10-15% (mit guter Isolierung)

### Fall 3: Industrie-Prozesswärmespeicher

```yaml
stratified_storage:
  - id: process_heat
    T_hot_C: 120.0           # Höhere Temperatur
    T_cold_C: 60.0
    aspect_ratio: 2.0        # Schlanker Tank
    geometry_type: tank
    U_top: 0.4
    U_side: 0.3
    U_bottom: 0.2
    investment:
      energy_capacity_max_mwh: 200.0
      power_capacity_max_mw: 80.0
```

## Ergebnisanalyse

### Wichtige Output-Variablen

Aus `storage_result`:

```python
# Energieinhalt
E_total[t]     # Gesamtenergie [MWh]

# Leistung
Qc[t]          # Ladeleistung [MW]
Qd[t]          # Entladeleistung [MW]

# Schichtung (NEU!)
V_hot[t]       # Heißes Volumen [m³]
V_cold[t]      # Kaltes Volumen [m³]

# Investment
cap_energy     # Installierte Energiekapazität [MWh]
cap_power      # Installierte Leistungskapazität [MW]
build          # Binary: Wurde gebaut? {0,1}
```

### Analyse-Metriken

```python
import pandas as pd

# SOC-Statistiken
soc_min = storage_df['E_total_MWh'].min()
soc_max = storage_df['E_total_MWh'].max()
soc_mean = storage_df['E_total_MWh'].mean()

# Roundtrip-Effizienz
total_charged = storage_df['Qc_MW'].sum()
total_discharged = storage_df['Qd_MW'].sum()
roundtrip_eff = total_discharged / total_charged

# Schichtungsverhalten
V_total = storage_df['V_hot_m3'] + storage_df['V_cold_m3']
ratio_hot = storage_df['V_hot_m3'] / V_total

# Zyklen zählen
charge_hours = (storage_df['Qc_MW'] > 0).sum()
discharge_hours = (storage_df['Qd_MW'] > 0).sum()
utilization = (charge_hours + discharge_hours) / len(storage_df)

print(f"Roundtrip Efficiency: {roundtrip_eff:.1%}")
print(f"Hot Zone Range: {ratio_hot.min():.1%} - {ratio_hot.max():.1%}")
print(f"Storage Utilization: {utilization:.1%}")
```

## Fehlerbehebung

### Problem: Solver nicht gefunden

```python
from pyomo.opt import SolverFactory

solver = SolverFactory('gurobi')
if not solver.available():
    print("Gurobi not available, using CBC")
    solver = SolverFactory('cbc')
```

### Problem: Numerische Instabilität

Gurobi-Optionen anpassen:

```yaml
solver:
  options:
    NumericFocus: 3      # Maximale numerische Genauigkeit
    ScaleFlag: 2         # Aggressive Skalierung
    BarConvTol: 1e-6    # Barrier Konvergenz-Toleranz
```

### Problem: Zu lange Lösungszeit

```yaml
solver:
  options:
    MIPGap: 0.05         # Lockerere Toleranz (5%)
    Heuristics: 0.2      # Mehr Zeit für Heuristiken
    Cuts: 2              # Aggressivere Schnitte
    Presolve: 2          # Aggressives Presolve
```

### Problem: Infeasible Model

Prüfen Sie:

1. **Kapazitätsgrenzen**:
   ```python
   assert e_cap_max >= heat_demand.max() * 8  # Mindestens 8h Speicher
   assert p_cap_max >= heat_demand.max()      # Genug Leistung
   ```

2. **Initial SOC**:
   ```yaml
   soc0: 100.0  # Nicht größer als e_cap_max!
   ```

3. **Verluste zu hoch**:
   ```yaml
   U_top: 0.3   # Reduzieren wenn Verluste zu groß
   U_side: 0.2
   U_bottom: 0.15
   ```

## Performance-Tipps

### Große Probleme (> 8760 Zeitschritte)

1. **Zeitauflösung reduzieren**:
   ```yaml
   simulation:
     dt_hours: 2.0  # Statt 1.0
   ```

2. **Rolling Horizon verwenden**:
   ```yaml
   simulation:
     rolling_horizon:
       enabled: true
       horizon_hours: 168   # 1 Woche
       step_hours: 24       # 1 Tag
   ```

3. **Gurobi-Parallelisierung**:
   ```yaml
   solver:
     options:
       Threads: 8          # Mehr Threads
       Method: 2           # Barrier-Methode (parallel)
   ```

### Speicherverbrauch reduzieren

```yaml
solver:
  options:
    NodefileStart: 0.5    # Swap to disk früher
    NodefileDir: /tmp     # Swap-Verzeichnis
```

## Beispiele

Vollständige funktionierende Beispiele:

1. **Standalone Integration**:
   ```bash
   python examples/stratified_storage_integration.py
   ```

2. **Einfache Demonstrationen**:
   ```bash
   python examples/stratified_storage_example.py
   ```

3. **Mit vollständigem System**:
   ```bash
   # TODO: Nach Integration mit Orchestrator
   python run_scenario.py --config configs/systems/district_heating_stratified_example.yaml
   ```

## Weitere Ressourcen

- **API-Dokumentation**: `docs/stratified_storage.md`
- **Physikalisches Modell**: Siehe Kommentare in `energis/models/blocks/stratified_storage.py`
- **Kalibrierung**: `docs/stratified_storage.md` → "Hinweise zur Kalibrierung"
- **Beispiel-Ergebnisse**: `exports/stratified_storage_example.json`

## Support

Bei Fragen oder Problemen:
1. Prüfen Sie zuerst die Dokumentation oben
2. Schauen Sie sich die Beispiele an
3. Erstellen Sie ein Issue auf GitHub mit:
   - Ihrer Konfigurationsdatei (YAML)
   - Fehlermeldungen
   - Solver-Output (wenn verfügbar)
