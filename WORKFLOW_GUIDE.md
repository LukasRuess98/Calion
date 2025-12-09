# EnerGIS Network Designer - Kompletter Workflow Guide

## 🎯 Übersicht

Dieser Guide zeigt den **kompletten, stringenten Workflow** von der Netzwerk-Planung bis zur Ergebnis-Analyse.

---

## 📋 Voraussetzungen

### 1. System-Check durchführen

```bash
python check_system.py
```

Dieser Check prüft:
- ✅ Python Version (>= 3.8)
- ✅ Alle Dependencies (pandas, numpy, pyomo, panel, plotly, etc.)
- ✅ Gurobi Solver + Lizenz
- ✅ Framework-Module
- ✅ Konfigurationsdateien

### 2. Falls Fehler: Installationen durchführen

```bash
# Framework installieren
pip install -e .

# Dependencies installieren
pip install -r requirements.txt

# Gurobi (falls noch nicht installiert)
# Download: https://www.gurobi.com/downloads/
# Academic License: https://www.gurobi.com/academia/
```

---

## 🚀 Workflow: 3 Wege zur Simulation

### **Weg 1: Interaktives Dashboard** (Empfohlen für Anfänger)

```bash
# Schritt 1: Network Designer starten
python start_network_designer.py

# Browser öffnet automatisch: http://localhost:5006
```

**Im Dashboard:**
1. ✅ Komponenten mit Maus platzieren (Drag-and-Click)
2. ✅ Eigenschaften konfigurieren (Status, Leistung, COP, etc.)
3. ✅ Verbindungen ziehen (Connect-Tool)
4. ✅ Validierung prüfen
5. ✅ YAML exportieren: `exports/network_designer_export.yaml`
6. ✅ Zeitreihen-Daten bereitstellen (Excel/CSV)
7. ✅ Simulation starten (Button: "▶ Simulation starten")
8. ✅ Ergebnisse analysieren (automatisch)

**Vorteile:**
- Visuell, intuitiv
- Sofortige Fehler-Anzeige
- Keine Programmierkenntnisse nötig
- Koordinaten automatisch

---

### **Weg 2: Jupyter Notebook** (Empfohlen für Analysen)

```bash
# Schritt 1: Notebook starten
jupyter notebook notebooks/complete_workflow.ipynb
```

**Im Notebook:** (Schritt für Schritt ausführen)

1. ✅ **Setup & Imports** (Zelle 1)
2. ✅ **Netzwerk programmatisch erstellen** (Zelle 2-5)
   ```python
   designer = create_network_designer()
   designer.add_component(x=100, y=300, comp_type='heat_pump')
   # ...
   ```
3. ✅ **YAML Export** (Zelle 6)
4. ✅ **Zeitreihen vorbereiten** (Zelle 7-8)
   - Option A: Existierende Daten laden
   - Option B: Synthetische Daten generieren
5. ✅ **Simulation ausführen** (Zelle 9)
   ```python
   result = run_workflow([config_path])
   ```
6. ✅ **Ergebnisse analysieren** (Zellen 10-14)
   - Kosten-Breakdown
   - Optimierte Dimensionierung
   - Zeitreihen-Plots
   - Kosten-Visualisierung
7. ✅ **Ergebnisse exportieren** (Zelle 15)

**Vorteile:**
- Reproduzierbar
- Automatisierbar
- Detaillierte Analysen
- Batch-Processing möglich

---

### **Weg 3: Python-Skript** (Empfohlen für Automatisierung)

```python
#!/usr/bin/env python3
"""Komplettes Beispiel-Skript"""

from pathlib import Path
from energis.io.network_designer import create_network_designer
from energis.run.rolling_horizon import run_workflow

# 1. Netzwerk erstellen
designer = create_network_designer()

# 2. Komponenten hinzufügen
designer.add_component(x=100, y=100, comp_type='boiler')
boiler = designer.components[0]
boiler.status = 'existing'
boiler.properties['capacity_mw'] = 20.0

designer.add_component(x=100, y=300, comp_type='heat_pump')
hp = designer.components[1]
hp.status = 'investment'

designer.add_component(x=400, y=200, comp_type='storage')
storage = designer.components[2]
storage.status = 'investment'

designer.add_component(x=700, y=200, comp_type='consumer')

# 3. Verbindungen
designer.add_connection(boiler.component_id, storage.component_id)
designer.add_connection(hp.component_id, storage.component_id)
designer.add_connection(storage.component_id, designer.components[3].component_id)

# 4. Validieren
valid, errors = designer.validate_network()
if not valid:
    print("Fehler:", errors)
    exit(1)

# 5. Exportieren
config_path = Path('exports/my_network.yaml')
designer.export_to_yaml(config_path)

# 6. Simulieren (mit Zeitreihen-Daten)
result = run_workflow(
    [str(config_path)],
    overrides={
        'data': {'input_file': 'data/timeseries.xlsx'}
    }
)

# 7. Ergebnisse
print("Simulation abgeschlossen!")
print(f"Gesamtkosten: {sum(result.pf_result.costs.values()):,.0f} EUR")
```

**Vorteile:**
- Vollständig automatisiert
- CI/CD-Integration möglich
- Parameterstudien einfach

---

## 📊 Stringenter End-to-End Workflow

### Phase 1: **Planung** 🗺️

```
Input: Anforderungen
  ↓
[Network Designer]
  ↓
Output: YAML Config + Koordinaten
```

**Deliverables:**
- `exports/network_config.yaml`
- Komponenten-Liste
- Topologie-Diagramm

---

### Phase 2: **Daten-Vorbereitung** 📈

```
Input: Lastprofile, Strompreise, CO2-Daten
  ↓
[Excel/CSV]
  ↓
Output: Zeitreihen-Datei
```

**Required Columns:**
- `waermebedarf_MWth` (MW)
- `strompreis_EUR_MWh` (EUR/MWh)
- `grid_co2_kg_MWh` (kg/MWh)
- `WRG1_T_K` (Kelvin)
- `WRG1_Q_cap` (MW)

**Format:** Excel oder CSV

---

### Phase 3: **Optimierung** ⚙️

```
Input: Config + Zeitreihen
  ↓
[Pyomo + Gurobi]
  ↓
Output: Optimierte Dimensionierung
```

**Ausführung:**
```python
result = run_workflow(['config.yaml'])
```

**Dauer:** 1-60 Minuten (abhängig von Größe)

---

### Phase 4: **Analyse** 📊

```
Input: Simulation Results
  ↓
[Dashboard / Notebook]
  ↓
Output: Reports, Plots, CSVs
```

**Outputs:**
- Kosten-Breakdown (CAPEX/OPEX)
- Optimierte Kapazitäten
- Zeitreihen-Plots
- Auslastungs-Analyse
- Export: CSV, YAML, PNG

---

## 🔄 Iterativer Workflow

```
1. Design      →  2. Simulate  →  3. Analyze
    ↑                                  ↓
    └──────────────── Adjust ─────────┘
```

**Typischer Iterationszyklus:**
1. Initiales Design im Network Designer
2. Erste Simulation
3. Ergebnisse analysieren
4. Komponenten anpassen (z.B. größerer Speicher)
5. Re-Simulation
6. Vergleich der Varianten
7. Optimales Design auswählen

---

## 📁 Verzeichnis-Struktur nach Workflow

```
Planing-Framework-for-Heat/
│
├── check_system.py                 # System-Check
├── start_network_designer.py       # Dashboard-Launcher
│
├── exports/                        # Alle Exports hier
│   ├── network_config.yaml         # Network Designer Export
│   ├── simulation_config.yaml      # Mit Zeitreihen-Pfad
│   ├── results/                    # Simulations-Ergebnisse
│   │   ├── costs.csv
│   │   ├── timeseries.csv
│   │   └── summary.yaml
│   └── plots/                      # Visualisierungen
│       ├── cost_breakdown.png
│       └── timeseries.png
│
├── notebooks/
│   ├── complete_workflow.ipynb     # Kompletter Workflow
│   └── network_designer_example.ipynb  # API-Beispiel
│
├── data/                           # Zeitreihen-Daten
│   └── timeseries.xlsx
│
└── configs/                        # Basis-Konfigurationen
    ├── base.yaml
    └── systems/
        └── baseline.system.yaml
```

---

## ⚡ Quick Start (5 Minuten)

```bash
# 1. System prüfen
python check_system.py

# 2. Dashboard starten
python start_network_designer.py

# 3. Im Browser:
#    - 2-3 Komponenten platzieren
#    - Verbindungen ziehen
#    - Exportieren

# 4. Notebook öffnen
jupyter notebook notebooks/complete_workflow.ipynb

# 5. Alle Zellen ausführen
#    (nutzt synthetische Testdaten)

# ✅ Fertig! Ergebnisse in exports/results/
```

---

## 🎓 Erweiterte Workflows

### Szenario-Vergleiche

```python
scenarios = {
    'Small_HP': {'heat_pump_capacity': 10},
    'Large_HP': {'heat_pump_capacity': 20},
    'With_Storage': {'storage_capacity': 100},
}

results = {}
for name, overrides in scenarios.items():
    results[name] = run_workflow(['base.yaml'], overrides)

# Vergleiche...
```

### Sensitivitäts-Analysen

```python
import numpy as np

co2_prices = np.arange(50, 200, 25)  # 50-200 EUR/t
results = []

for price in co2_prices:
    result = run_workflow(
        ['config.yaml'],
        overrides={'costs': {'co2_price_eur_per_t': price}}
    )
    results.append(result)

# Analyse...
```

### Batch-Processing

```bash
# Erstelle configs/batch/scenario_*.yaml
# Dann:
python scripts/run_batch.py --input configs/batch/ --output results/batch/
```

---

## 🔧 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'panel'"

**Lösung:**
```bash
pip install panel plotly holoviews bokeh
```

---

### Problem: "Gurobi license not found"

**Lösung:**
```bash
# Academic License beantragen:
# https://www.gurobi.com/academia/

# Lizenz aktivieren:
grbgetkey YOUR-LICENSE-KEY
```

---

### Problem: "No heat or electric components detected"

**Lösung:**
- Prüfe YAML-Struktur: `system.heat_pumps` muss Liste sein
- Prüfe IDs: Müssen eindeutig sein
- Prüfe WRG-Spalten in Zeitreihen-Daten

---

### Problem: "Simulation dauert zu lange (>10 min)"

**Lösungen:**
```yaml
# In config.yaml:
run:
  solver_options:
    MIPGap: 0.05       # Erhöhe von 0.02 auf 0.05
    TimeLimit: 600     # Setze Timeout (Sekunden)
    Presolve: 2        # Aggressive Presolve
```

---

## 📚 Weitere Ressourcen

- **Dokumentation:**
  - `docs/NETWORK_DESIGNER_GUIDE.md` - Detailliertes Dashboard-Manual
  - `SIMPLIFICATION_PROPOSAL.md` - Konzept & Alternativen
  - `INTEGRATION_SUMMARY.md` - Feature-Übersicht

- **Beispiele:**
  - `notebooks/network_designer_example.ipynb` - Programmatic API
  - `notebooks/complete_workflow.ipynb` - End-to-End Workflow
  - `examples/` - Standalone-Beispiele

- **Konfigurationen:**
  - `configs/systems/baseline.system.yaml` - Referenz-System
  - `configs/scenarios/*.scenario.yaml` - Beispiel-Szenarien

---

## ✅ Checkliste für erfolgreiche Simulation

- [ ] System-Check erfolgreich (`python check_system.py`)
- [ ] Gurobi Lizenz gültig
- [ ] Netzwerk erstellt (min. 1 Komponente)
- [ ] Alle Komponenten verbunden (keine isolierten Komponenten)
- [ ] YAML exportiert
- [ ] Zeitreihen-Daten vorhanden (waermebedarf_MWth, strompreis_EUR_MWh, ...)
- [ ] WRG-Spalten für Wärmepumpen vorhanden (WRG1_T_K, WRG1_Q_cap)
- [ ] Konfiguration validiert
- [ ] Simulation gestartet
- [ ] Ergebnisse exportiert

---

## 🎉 Das war's!

**Sie haben jetzt alles, um thermische Netzwerke zu planen, optimieren und analysieren.**

Bei Fragen: GitHub Issues oder Dokumentation konsultieren.

**Viel Erfolg! 🚀**
