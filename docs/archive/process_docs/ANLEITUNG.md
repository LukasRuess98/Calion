# Framework Ausführungs-Anleitung

## Überblick

Das EnerGIS Heat Planning Framework ist ein modulares MILP-Optimierungs-Framework basierend auf Python/Pyomo. Es optimiert die Planung von Wärmesystemen über zwei Hauptschritte:

1. **Perfect Forecast (PF)**: Optimiert die Systemauslegung über den gesamten Zeitraum
2. **Rolling Horizon (RH)**: Optimiert den Betrieb in rollierenden Zeitfenstern mit fester Auslegung

## Schnellstart

### Option 1: Kommandozeile (CLI)
```bash
python -m energis.run.rolling_horizon config/scenarios/baseline.yaml
```

### Option 2: Jupyter Notebook
```bash
jupyter notebook notebooks/runner.ipynb
```

### Option 3: Shell-Skript (empfohlen für Fallstudien)
```bash
./scripts/run_case_study.sh config/scenarios/baseline.yaml
```

### Option 4: Schnelltest
```bash
python quickstart_test.py
```

---

## Detaillierte Ausführung

### 1. Vorbereitung

#### Erforderliche Daten
- **Lastprofile**: Excel-Dateien mit Wärmelast und Temperatur
- **Konfigurationsdateien**: YAML-Dateien im `config/` Verzeichnis
- **Technologiekatalog**: `config/tech_catalog.yaml`

#### Verzeichnisstruktur
```
config/
├── base.yaml                    # Grundkonfiguration
├── tech_catalog.yaml            # Technologie-Spezifikationen
├── sites/
│   └── default.site.yaml       # Standort-Konfiguration (Datenpfade)
├── systems/
│   └── baseline.system.yaml    # System-Instanzen
└── scenarios/
    └── baseline.yaml            # Szenario-Parameter
```

---

### 2. Workflow-Prozess

#### Schritt-für-Schritt Ablauf

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. KONFIGURATION LADEN                                          │
│    - YAML-Dateien zusammenführen (deep merge)                   │
│    - CLI-Argumente überschreiben Konfiguration                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. DATEN EINLESEN                                               │
│    - Lastprofile aus Excel/CSV                                  │
│    - Zeitreihen interpolieren und validieren                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. WORKFLOW PLANEN                                              │
│    - Perfect Forecast aktiviert? → PF Schritt                   │
│    - Rolling Horizon aktiviert? → RH Schritt                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4a. PERFECT FORECAST (PF) - Optional                            │
│     - Optimierung über gesamten Zeitraum (typisch 1 Jahr)       │
│     - Bestimmt optimale Kapazitäten                             │
│     - Output: Auslegungsdaten, Zeitreihen, Kosten               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4b. DESIGN EXTRAKTION                                           │
│     - Kapazitäten aus PF-Ergebnis extrahieren                   │
│     - Für RH-Schritt fixieren                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. ROLLING HORIZON (RH) - Optional                              │
│     - Zeitleiste in Fenster aufteilen (z.B. 168h = 1 Woche)     │
│     - Jedes Fenster optimieren mit fester Auslegung             │
│     - SOC zwischen Fenstern übertragen                          │
│     - Nur ersten Teil committen (z.B. 24h)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. ERGEBNISSE AGGREGIEREN                                       │
│     - Zeitreihen zusammenführen                                 │
│     - Kosten berechnen (ohne Doppelzählung)                     │
│     - Metriken erstellen                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. EXPORT                                                       │
│     - Excel: Zeitreihen, Design, Kosten                         │
│     - JSON: Maschinenlesbare Daten                              │
│     - CSV: Einzelne Zeitreihen                                  │
│     - Plots: Visualisierungen                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3. Konfigurationshierarchie

Die Konfiguration wird in folgender Reihenfolge geladen (niedrigste zu höchster Priorität):

1. `config/base.yaml` - Grundeinstellungen
2. `config/tech_catalog.yaml` - Komponenten-Spezifikationen
3. `config/sites/default.site.yaml` - Eingabedaten-Pfade
4. `config/systems/baseline.system.yaml` - System-Instanzen
5. `config/scenarios/*.yaml` - Workflow-Parameter
6. `config/overrides.local.yaml` - Lokale Überschreibungen (gitignored)
7. Umgebungsvariablen
8. **CLI-Argumente** (höchste Priorität)

#### Beispiel: Mehrere Konfigurationen zusammenführen
```bash
python -m energis.run.rolling_horizon \
    config/base.yaml \
    config/scenarios/baseline.yaml \
    config/overrides.local.yaml \
    --solver=gurobi \
    --output-dir=results/test1
```

---

### 4. CLI-Argumente

#### Wichtigste Flags
```bash
# Solver auswählen
--solver=gurobi          # oder: cbc, glpk, highs
--solver-options='{"threads": 4, "mipgap": 0.01}'

# Ausgabeverzeichnis
--output-dir=results/my_run

# Workflow-Schritte steuern
--enable-pf=true         # Perfect Forecast aktivieren
--enable-rh=true         # Rolling Horizon aktivieren

# Zeitbereich festlegen
--start-date=2023-01-01
--end-date=2023-12-31

# Debugging
--log-level=DEBUG
--save-lp=true           # LP-Datei speichern
```

#### Verschachtelte Konfiguration überschreiben
```bash
--optimization.pf.enabled=true
--optimization.rh.window_hours=168
--optimization.rh.commit_hours=24
```

---

### 5. Python API

#### Einfachste Verwendung
```python
from energis.run.rolling_horizon import run_workflow

# Workflow mit Konfigurationsdateien ausführen
results = run_workflow(['config/scenarios/baseline.yaml'])
```

#### Mit zusätzlichen Parametern
```python
from energis.run.rolling_horizon import run_workflow

results = run_workflow(
    config_files=['config/scenarios/baseline.yaml'],
    cli_overrides={
        'solver': 'gurobi',
        'output_dir': 'results/my_experiment',
        'optimization': {
            'pf': {'enabled': True},
            'rh': {'enabled': True, 'window_hours': 168}
        }
    }
)

# Ergebnisse auswerten
print(f"Total costs: {results.total_costs}")
print(f"Design capacities: {results.design}")
```

---

### 6. Jupyter Notebook Verwendung

#### Hauptnotizbuch: `notebooks/runner.ipynb`

```python
# Zelle 1: Konfiguration laden
config_files = [
    'config/base.yaml',
    'config/scenarios/baseline.yaml'
]

# Zelle 2: Workflow ausführen
from energis.run.rolling_horizon import run_workflow
results = run_workflow(config_files)

# Zelle 3: Ergebnisse visualisieren
import matplotlib.pyplot as plt
results.plot_heat_balance()
results.plot_storage_soc()

# Zelle 4: Kosten analysieren
print(results.get_cost_breakdown())
```

#### Weitere Notebooks
- `scenario_studio.ipynb`: Szenario-Vergleiche und Sensitivitätsanalysen
- `validation.ipynb`: Validierung gegen Legacy-Implementierung

---

### 7. Komponenten und Module

#### Hauptkomponenten des Frameworks

| Komponente | Datei | Beschreibung |
|------------|-------|--------------|
| **Workflow-Orchestrierung** | `energis/run/rolling_horizon.py` | PF/RH Workflow, CLI-Einstiegspunkt |
| **Modell-Builder** | `energis/models/system_builder.py` | Pyomo-Modell erstellen, COP-Interpolation |
| **Ergebnis-Orchestrator** | `energis/run/orchestrator.py` | Zeitreihen aggregieren, Kosten berechnen |
| **Konfiguration** | `energis/config/merge.py` | YAML laden und zusammenführen |
| **Daten-Loader** | `energis/io/loader.py` | Excel/CSV einlesen |
| **Exporter** | `energis/io/exporter.py` | Excel/JSON/CSV/Plots exportieren |

#### Technologie-Blöcke (Plugin-System)

Alle Technologien sind über `@register_component` als Plugins registriert:

- **HeatPumpBlock**: Wärmepumpe mit COP-Zeitreihen
- **StorageBlock**: Thermischer Speicher mit Ladung/Entladung
- **ThermalGeneratorBlock**: Gas-/Biomasse-Kessel
- **P2HBlock**: Power-to-Heat Konverter
- **GridBlock**: Netzanschluss

```python
# Neue Komponente hinzufügen
from energis.models.registry import register_component

@register_component('MyCustomTech')
class MyCustomTechBlock:
    def __init__(self, model, instance_data):
        # Variablen und Constraints definieren
        pass
```

---

### 8. Ausgabedateien

Nach der Ausführung werden folgende Dateien erstellt:

#### Standard-Ausgabeverzeichnis: `results/<timestamp>/`

```
results/2025-11-18_143022/
├── results.xlsx              # Excel mit allen Ergebnissen
│   ├── Sheet: TimeSeries     # Zeitreihen (Leistung, Energie)
│   ├── Sheet: Design         # Kapazitäten
│   ├── Sheet: Costs          # Kostenaufschlüsselung
│   └── Sheet: Metadata       # Run-Informationen
├── results.json              # JSON-Format (maschinenlesbar)
├── timeseries/               # Einzelne CSV-Dateien
│   ├── heat_pump_power.csv
│   ├── storage_soc.csv
│   └── ...
├── plots/                    # Visualisierungen
│   ├── heat_balance.png
│   ├── storage_operation.png
│   └── ...
├── config_merged.yaml        # Verwendete Gesamt-Konfiguration
└── solver.log                # Solver-Ausgabe
```

#### Mit Shell-Skript: `artifacts/<scenario_name>/`
```bash
./scripts/run_case_study.sh config/scenarios/baseline.yaml
# Ausgabe in: artifacts/baseline/
```

---

### 9. Perfect Forecast (PF) Details

#### Zweck
- Bestimmt die **optimale Systemauslegung** (Kapazitäten)
- Berücksichtigt gesamten Planungshorizont (z.B. 1 Jahr)
- Gibt Investitions- und Betriebskosten aus

#### Konfiguration
```yaml
optimization:
  pf:
    enabled: true
    start_date: "2023-01-01"
    end_date: "2023-12-31"
    time_step_hours: 1
```

#### Ausgabe
- **Design**: Optimale Kapazitäten aller Komponenten
- **Time Series**: Stündliche Betriebsprofile
- **Costs**: Investitions-, Betriebs-, Wartungskosten

---

### 10. Rolling Horizon (RH) Details

#### Zweck
- Optimiert den **Betrieb** mit fester Auslegung aus PF
- Teilt lange Zeithorizonte in handhabbare Fenster
- Realistischere Simulation durch beschränkte Vorausschau

#### Funktionsweise

```
Gesamtzeitraum: 8760 Stunden (1 Jahr)
Window: 168 Stunden (1 Woche)
Commit: 24 Stunden (1 Tag)

┌──────────────────────────────────────────────────────┐
│ Fenster 1: h0-h167 → Commit h0-h23                   │
│         Fenster 2: h24-h191 → Commit h24-h47         │
│                 Fenster 3: h48-h215 → Commit h48-h71 │
│                         ...                          │
└──────────────────────────────────────────────────────┘
```

#### Konfiguration
```yaml
optimization:
  rh:
    enabled: true
    window_hours: 168      # Optimierungsfenster
    commit_hours: 24       # Committete Stunden pro Fenster
    overlap_hours: 144     # window_hours - commit_hours
    carry_soc: true        # SOC zwischen Fenstern übertragen
```

#### Besonderheiten
- **SOC-Übertragung**: Speicherzustand wird von einem Fenster zum nächsten weitergegeben
- **Keine Kostenüberschneidung**: Investitionskosten nur einmal gezählt
- **Boundary Conditions**: Speicher startet und endet bei konfiguriertem SOC

---

### 11. Beispiel: Vollständiger Workflow

#### Szenario: Baseline-System optimieren

```bash
# 1. Konfigurationsdateien überprüfen
cat config/scenarios/baseline.yaml

# 2. Workflow ausführen
python -m energis.run.rolling_horizon \
    config/scenarios/baseline.yaml \
    --solver=gurobi \
    --output-dir=results/baseline_run \
    --log-level=INFO

# 3. Ergebnisse überprüfen
ls -lh results/baseline_run/
cat results/baseline_run/results.json | jq '.costs'

# 4. Excel öffnen
libreoffice results/baseline_run/results.xlsx
```

#### Erwartete Ausgabe
```
[INFO] Loading configuration from 1 files
[INFO] Merged configuration: 247 keys
[INFO] Loading input data from config/data/load_profiles.xlsx
[INFO] Starting Perfect Forecast step
[INFO] Building Pyomo model with 5 components
[INFO] Solving with gurobi (8760 timesteps)
[INFO] Solution found in 12.3s, objective: 125834.50 €
[INFO] Starting Rolling Horizon step
[INFO] Window 1/52: h0-h167
[INFO] Window 2/52: h24-h191
...
[INFO] Window 52/52: h8736-h8903
[INFO] Aggregating results from 52 windows
[INFO] Exporting results to results/baseline_run/
[INFO] Done! Total runtime: 385.2s
```

---

### 12. Fehlerbehandlung und Debugging

#### Häufige Probleme

**Problem**: Solver nicht gefunden
```
ERROR: Solver 'gurobi' not available
```
**Lösung**:
```bash
# Verfügbare Solver prüfen
python -c "from pyomo.opt import SolverFactory; print(SolverFactory.services())"

# Freien Solver verwenden
--solver=cbc
```

**Problem**: Infeasible Modell
```
WARNING: Model is infeasible
```
**Lösung**:
```bash
# LP-Datei speichern und analysieren
--save-lp=true
# Datei in: results/<run>/model.lp

# Log-Level erhöhen
--log-level=DEBUG
```

**Problem**: Out of Memory bei großen Problemen
```
MemoryError: Unable to allocate array
```
**Lösung**:
```yaml
# RH-Fenster verkleinern
optimization:
  rh:
    window_hours: 48  # statt 168
    commit_hours: 12  # statt 24
```

#### Debug-Modus
```bash
python -m energis.run.rolling_horizon \
    config/scenarios/baseline.yaml \
    --log-level=DEBUG \
    --save-lp=true \
    --solver-options='{"LogFile": "solver.log", "LogToConsole": 1}'
```

---

### 13. Erweiterte Verwendung

#### Parameterstudie
```python
import itertools
from energis.run.rolling_horizon import run_workflow

base_config = ['config/scenarios/baseline.yaml']

# Parameter-Kombinationen
heat_pump_cops = [3.0, 3.5, 4.0]
storage_sizes = [100, 200, 300]  # kWh

results = {}
for cop, size in itertools.product(heat_pump_cops, storage_sizes):
    run_name = f"cop{cop}_storage{size}"

    result = run_workflow(
        base_config,
        cli_overrides={
            'output_dir': f'results/parametric/{run_name}',
            'tech_catalog': {
                'heat_pump': {'cop': cop},
                'storage': {'capacity_max_kwh': size}
            }
        }
    )

    results[run_name] = result.total_costs

# Beste Konfiguration finden
best = min(results, key=results.get)
print(f"Best configuration: {best} with costs {results[best]} €")
```

#### Batch-Verarbeitung
```bash
# Alle Szenarien ausführen
for scenario in config/scenarios/*.yaml; do
    name=$(basename $scenario .yaml)
    python -m energis.run.rolling_horizon $scenario \
        --output-dir=results/batch/$name
done
```

---

### 14. Performance-Tipps

1. **Solver-Wahl**: Gurobi > CPLEX > CBC für große Probleme
2. **Parallele Threads**: `--solver-options='{"threads": 8}'`
3. **MIP Gap**: `--solver-options='{"mipgap": 0.02}'` (2% statt 1%)
4. **Zeitauflösung**: Stündlich statt minütlich wenn möglich
5. **RH-Fenster**: Balance zwischen Genauigkeit und Geschwindigkeit
6. **Presolve**: `--solver-options='{"presolve": 2}'` (aggressiv)

---

## Zusammenfassung

Das Framework wird typischerweise so verwendet:

1. **Daten vorbereiten**: Lastprofile in Excel
2. **Konfiguration anpassen**: YAML-Dateien im `config/` Ordner
3. **Ausführen**: CLI, Notebook oder Python API
4. **Ergebnisse analysieren**: Excel, JSON oder Plots

**Empfohlener Einstieg**:
```bash
# Schnelltest
python quickstart_test.py

# Erstes echtes Szenario
python -m energis.run.rolling_horizon config/scenarios/baseline.yaml

# Oder interaktiv
jupyter notebook notebooks/runner.ipynb
```

---

## Weitere Ressourcen

- **Code-Dokumentation**: Siehe Docstrings in `energis/run/rolling_horizon.py`
- **Beispiel-Konfigurationen**: `config/scenarios/`
- **Technologie-Katalog**: `config/tech_catalog.yaml`
- **Tests**: `tests/` Verzeichnis für Beispiele

Bei Fragen oder Problemen: Siehe Log-Dateien in `results/<run>/solver.log`
