# 🎯 Dashboard mit echten Simulationsdaten

Dieses Dokument erklärt, wie du das Dashboard mit **echten Optimierungsergebnissen** verwendest und mehrere Simulationen vergleichst.

## 📋 Übersicht

Das EnerGIS Dashboard-System bietet zwei Hauptansätze:

| Ansatz | Vorteile | Beste für |
|--------|----------|-----------|
| **Webapp mit gespeicherten Simulationen** ⭐ | ✅ Mehrere Simulationen vergleichen<br>✅ Schneller Start (< 5 Sek)<br>✅ Detaillierte Metadaten<br>✅ Dropdown-Auswahl | **Analyse & Vergleich mehrerer Szenarien** |
| **Jupyter Notebook Integration** | ✅ Interaktive Entwicklung<br>✅ Code + Visualisierung<br>✅ Dokumentation | **Explorative Analyse & Entwicklung** |

---

## ⭐ **Webapp mit gespeicherten Simulationen (EMPFOHLEN)**

### 🎯 Konzept

```
Simulation 1 → Speichern mit Metadaten
Simulation 2 → Speichern mit Metadaten   }→ Dashboard → Dropdown-Auswahl → Analyse
Simulation 3 → Speichern mit Metadaten
```

Jede gespeicherte Simulation enthält:
- ✅ **Workflow-Daten**: Alle Optimierungsergebnisse
- ✅ **Metadaten**: Scenario, Technologien, Kosten, Solver, etc.
- ✅ **Zeitstempel**: Wann wurde optimiert
- ✅ **Beschreibung**: Eigene Notizen zum Test

---

### 📝 **Schritt 1: Simulation speichern**

#### Basis-Verwendung

```bash
# Mit Standard-Konfiguration speichern
python save_workflow_results.py
```

**Output:**
```
saved_workflows/
└── 2025-11-27_14-30-45_pf_then_rh/
    ├── workflow.pkl       # Komplettes Workflow-Objekt
    └── metadata.json      # Metadaten (Scenario, Technologien, etc.)
```

#### Mit eigenem Namen

```bash
# Simulation mit Custom-Name speichern
python save_workflow_results.py --name "baseline_v1"

# Mit Name und Beschreibung
python save_workflow_results.py \
    --name "optimized_hp" \
    --description "Optimierte Wärmepumpen-Konfiguration mit größerem Speicher"
```

**Output:**
```
saved_workflows/
└── 2025-11-27_14-35-22_baseline_v1/
    ├── workflow.pkl
    └── metadata.json
```

#### Verschiedene Szenarien speichern

Um verschiedene Szenarien zu testen:

1. **Bearbeite** `save_workflow_results.py`
2. **Ändere** die `CONFIG_PATHS` Variable:

```python
# In save_workflow_results.py

# Szenario 1: Baseline
CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/default.site.yaml',
    'configs/systems/baseline.system.yaml',
    'configs/scenarios/pf_then_rh.workflow.scenario.yaml',
]
```

3. **Führe aus** und speichere:

```bash
# Baseline Szenario
python save_workflow_results.py --name "baseline"

# Ändere CONFIG_PATHS für Advanced-System
# → Bearbeite save_workflow_results.py

# Advanced Szenario
python save_workflow_results.py --name "advanced"

# Ändere CONFIG_PATHS für eigenes Szenario
# Advanced Szenario
python save_workflow_results.py --name "custom_test"
```

---

### 📊 **Schritt 2: Dashboard starten**

```bash
# Multi-Workflow Dashboard starten
panel serve load_dashboard.py --show
```

**Das Dashboard öffnet sich automatisch im Browser!**

**URL:** http://localhost:5006/load_dashboard

---

### 🎨 **Dashboard-Features**

#### 1. **Dropdown-Auswahl**
- Liste aller gespeicherten Simulationen
- Sortiert nach Datum (neueste zuerst)
- Format: `YYYY-MM-DD - Simulationsname`

#### 2. **Metadaten-Panel** (wird automatisch angezeigt)

**Zeigt für jede Simulation:**

```
📋 Workflow Informationen
─────────────────────────────────────

🎯 baseline_v1
Optimierte Baseline-Konfiguration

Gespeichert: 2025-11-27T14:30:45

┌─────────────────┬─────────────────┬─────────────────┐
│ SCENARIO        │ SYSTEM          │ SITE            │
│ pf_then_rh      │ baseline        │ default         │
└─────────────────┴─────────────────┴─────────────────┘

WORKFLOW
PF → RH
Solver: glpk

TECHNOLOGIEN
🔥 Wärmepumpen:
  • HP_air: 2.50 MW
  • HP_ground: 1.80 MW
🔋 Speicher: 35.00 MWh

┌─────────────────────────────┬─────────────────────────────┐
│ ZEITRAUM                    │ KOSTEN                      │
│ 8,760 Zeitschritte          │ 234,567 EUR                 │
│ 8,760.0 Stunden             │ CAPEX: 120,000 EUR          │
│                             │ OPEX: 114,567 EUR           │
└─────────────────────────────┴─────────────────────────────┘

📁 Konfigurationsdateien anzeigen ▼
  • configs/base.yaml
  • configs/tech_catalog.yaml
  • configs/sites/default.site.yaml
  • ...
```

#### 3. **Interaktives Dashboard**

Die 5 Standard-Tabs:
- 📈 **Overview**: KPI-Karten, Zusammenfassung
- 📊 **Timeseries**: Komponenten auswählen, Zeitbereich
- 💰 **Costs**: Kosten-Breakdown, sortierbare Tabelle
- 🏭 **Design**: Kapazitäten der Anlagen
- 🔄 **Comparison**: PF vs RH/MPC Vergleich

Alle Plots sind interaktiv:
- **Zoom**: Mausrad oder Box-Select
- **Pan**: Ziehen mit Maus
- **Hover**: Detailwerte anzeigen
- **Download**: Plots als PNG speichern

---

### 🔄 **Mehrere Simulationen vergleichen**

#### Workflow für Vergleichsanalyse

```bash
# 1. Baseline speichern
python save_workflow_results.py --name "baseline" \
    --description "Standard-Konfiguration ohne Optimierungen"

# 2. save_workflow_results.py bearbeiten: Größeren Speicher
#    → Ändere configs/systems/baseline.system.yaml
python save_workflow_results.py --name "large_storage" \
    --description "Speicher von 35 MWh auf 50 MWh erhöht"

# 3. Weitere Variante: Mehr Wärmepumpen
python save_workflow_results.py --name "more_hps" \
    --description "Zusätzliche Wärmepumpe hinzugefügt"

# 4. Dashboard starten und vergleichen
panel serve load_dashboard.py --show
```

**Im Dashboard:**
1. Wähle "baseline" aus Dropdown → Analysiere Ergebnisse
2. Wähle "large_storage" → Vergleiche Kosten
3. Wähle "more_hps" → Vergleiche Auslegung

**Vergleiche:**
- Gesamtkosten (CAPEX vs OPEX)
- Technologie-Mix
- Zeitreihen-Verlauf
- Peak-Demand vs Kapazitäten

---

## 📓 **Jupyter Notebook Integration**

### Bereits integriert in:

1. **notebooks/scenario_studio.ipynb** ✅
   - Dashboard-Sektion am Ende
   - Automatisch nach Optimierung

2. **notebooks/interactive_dashboard.ipynb** ✅
   - Vollständiges Tutorial
   - Schritt-für-Schritt Anleitung

### Eigenes Notebook erstellen

```python
# 1. Import
from energis.run import rolling_horizon as rh
from energis.io.dashboard import create_dashboard

# 2. Konfiguration
CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/default.site.yaml',
    'configs/systems/baseline.system.yaml',
    'configs/scenarios/pf_then_rh.workflow.scenario.yaml',
]

# 3. Optimierung ausführen
workflow = rh.run_workflow(CONFIG_PATHS)

# 4. Dashboard erstellen und anzeigen
dashboard = create_dashboard(
    workflow,
    title="Meine Analyse"
)
dashboard  # Zeigt Dashboard inline im Notebook
```

---

## 🛠️ **Voraussetzungen**

### Python-Pakete

```bash
# Dashboard-Pakete (bereits installiert)
pip install panel holoviews bokeh plotly

# Für echte Optimierung
pip install pyomo
```

### Solver

**Option A: GLPK** (kostenlos, für kleine/mittlere Probleme)
```bash
# Linux
sudo apt-get install glpk-utils

# macOS
brew install glpk

# Windows
# Download von: https://sourceforge.net/projects/winglpk/
```

**Option B: Gurobi** (kommerziell, sehr schnell)
- Kostenlose akademische Lizenz verfügbar
- https://www.gurobi.com/

**Option C: CPLEX** (kommerziell, sehr schnell)
- Kostenlose akademische Lizenz verfügbar
- https://www.ibm.com/analytics/cplex-optimizer

---

## 🚀 **Quick Start Guide**

### Schnellster Weg zu echten Daten

```bash
# 1. Erste Simulation speichern (dauert 5-30 Min je nach Größe)
python save_workflow_results.py --name "mein_erster_test"

# 2. Dashboard öffnet sich automatisch im Browser (< 5 Sek)
panel serve load_dashboard.py --show
```

**Fertig!** 🎉

Du siehst jetzt:
- Dropdown mit "mein_erster_test"
- Vollständige Metadaten (Scenario, Technologien, Kosten)
- Interaktives Dashboard mit 5 Tabs

---

## 📊 **Vergleich: Mock vs. Real Data**

### Mock-Daten (Demo)

```bash
panel serve demo_dashboard_mock.py --show
```

- ✅ Startet sofort (< 1 Sekunde)
- ❌ Fake-Daten (168 Stunden, sinusförmig)
- 🎯 **Zweck:** Dashboard-Interface testen

### Echte Daten (Produktiv)

```bash
python save_workflow_results.py --name "test1"
panel serve load_dashboard.py --show
```

- ✅ Echte Optimierungsergebnisse
- ✅ Realistische Zeitreihen & Kosten
- ✅ Mehrere Simulationen vergleichbar
- ✅ Detaillierte Metadaten
- 🎯 **Zweck:** Ergebnisanalyse & Vergleich

---

## 🔍 **Troubleshooting**

### "ModuleNotFoundError: No module named 'pyomo'"

**Lösung:**
```bash
pip install pyomo
```

### "No solver available"

**Lösung:**
```bash
# Linux
sudo apt-get install glpk-utils

# Test ob Solver verfügbar:
glpsol --version
```

### "Keine gespeicherten Workflows gefunden"

**Lösung:**
```bash
# Zuerst Simulation speichern!
python save_workflow_results.py

# Dann Dashboard starten
panel serve load_dashboard.py --show
```

### "Optimization takes too long"

**Lösungen:**

1. **Kleineren Zeithorizont:** Ändere in `configs/base.yaml`
   ```yaml
   simulation:
     duration_hours: 168  # Eine Woche statt einem Jahr
   ```

2. **Schnelleren Solver:** Installiere Gurobi oder CPLEX

3. **Gröbere Auflösung:**
   ```yaml
   simulation:
     timestep_hours: 1  # Statt 0.25 (15 Min)
   ```

4. **Weniger Komponenten:** Reduziere Technologien in System-Config

### "Dashboard lädt nicht im Browser"

**Lösung:**
```bash
# Prüfe ob Port 5006 frei ist
lsof -i :5006

# Falls belegt, anderen Port verwenden:
panel serve load_dashboard.py --port 5007 --show
```

---

## 💡 **Best Practices**

### 1. **Naming Convention** für Simulationen

```bash
# Gut: Beschreibend und datiert
python save_workflow_results.py \
    --name "baseline_2025_q4" \
    --description "Q4 Baseline mit aktualisierten Strompreisen"

# Gut: Versioniert
python save_workflow_results.py \
    --name "optimization_v3" \
    --description "Version 3: Speichergröße optimiert"

# Schlecht: Nicht aussagekräftig
python save_workflow_results.py --name "test"
```

### 2. **Strukturierte Vergleiche**

```bash
# Test-Serie mit Varianten
for storage in 20 35 50; do
    # Ändere Speichergröße in config
    python save_workflow_results.py \
        --name "storage_${storage}mwh" \
        --description "Speicherkapazität: ${storage} MWh"
done

# Dann vergleichen im Dashboard
panel serve load_dashboard.py --show
```

### 3. **Metadaten nutzen**

Die Metadaten im Dashboard zeigen dir:
- ✅ **Welches Szenario** wurde simuliert
- ✅ **Welche Technologien** wurden verwendet
- ✅ **Welcher Solver** wurde genutzt
- ✅ **Wann** wurde optimiert
- ✅ **Welche Config-Dateien** wurden verwendet

→ Reproduzierbarkeit garantiert!

### 4. **Backup wichtiger Simulationen**

```bash
# Wichtige Ergebnisse sichern
cp -r saved_workflows/2025-11-27_14-30-45_baseline_final \
      backup/baseline_final_2025-11-27

# Oder ZIP erstellen
cd saved_workflows
tar -czf ../archive/baseline_final.tar.gz 2025-11-27_14-30-45_baseline_final
```

---

## 📁 **Dateistruktur**

### Scripts

| Datei | Zweck | Verwendung |
|-------|-------|------------|
| `save_workflow_results.py` | Optimierung ausführen & speichern | `python save_workflow_results.py --name "test1"` |
| `load_dashboard.py` | Multi-Workflow Dashboard | `panel serve load_dashboard.py --show` |
| `demo_dashboard_mock.py` | Demo mit Mock-Daten | Schnelles Testing der Oberfläche |

### Verzeichnisse

```
Planing-Framework-for-Heat/
├── saved_workflows/                    # Gespeicherte Simulationen
│   ├── 2025-11-27_14-30-45_baseline/
│   │   ├── workflow.pkl               # Workflow-Objekt
│   │   └── metadata.json              # Metadaten
│   ├── 2025-11-27_15-00-12_optimized/
│   │   ├── workflow.pkl
│   │   └── metadata.json
│   └── ...
├── save_workflow_results.py           # Speicher-Script
├── load_dashboard.py                  # Dashboard-Webapp
└── REAL_DATA_GUIDE.md                 # Diese Dokumentation
```

### Metadata JSON Format

```json
{
  "saved_at": "2025-11-27T14:30:45.123456",
  "name": "baseline_v1",
  "description": "Baseline-Konfiguration Q4 2025",
  "scenario": {
    "name": "pf_then_rh",
    "system": "baseline",
    "site": "default"
  },
  "config_files": [
    "configs/base.yaml",
    "configs/tech_catalog.yaml",
    "configs/sites/default.site.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/pf_then_rh.workflow.scenario.yaml"
  ],
  "workflow": {
    "steps": ["PF", "RH"],
    "fix_design": false
  },
  "results_available": {
    "pf": true,
    "rh": true,
    "mpc": false
  },
  "solver": "glpk",
  "technologies": {
    "heat_pumps": {
      "HP_air": {
        "capacity_mw": 2.5,
        "type": "heat_pump"
      },
      "HP_ground": {
        "capacity_mw": 1.8,
        "type": "heat_pump"
      }
    },
    "storage": {
      "capacity_mwh": 35.0,
      "type": "thermal_storage"
    }
  },
  "statistics": {
    "timesteps": 8760,
    "duration_hours": 8760.0
  },
  "costs": {
    "total_eur": 234567.89,
    "capex_eur": 120000.0,
    "opex_eur": 114567.89,
    "fuel_eur": 0.0
  }
}
```

---

## 🎓 **Nächste Schritte**

### Für Einsteiger

1. ✅ **Solver installieren** (GLPK)
2. ✅ **Erste Simulation:** `python save_workflow_results.py --name "test1"`
3. ✅ **Dashboard öffnen:** `panel serve load_dashboard.py --show`
4. ✅ **Erkunden:** Verschiedene Tabs ausprobieren

### Für Fortgeschrittene

1. ✅ **Mehrere Szenarien** erstellen und vergleichen
2. ✅ **Eigene Configs** erstellen (System, Site)
3. ✅ **Jupyter Integration** nutzen für Entwicklung
4. ✅ **Export-Funktionalität** für Publikationen nutzen

---

## 📞 **Support**

Bei Problemen oder Fragen:

1. ✅ Prüfe **Troubleshooting**-Section oben
2. ✅ Checke **Logausgaben** der Scripts
3. ✅ Erstelle **GitHub Issue** mit:
   - Fehlermeldung
   - Verwendete Konfiguration
   - Schritte zur Reproduktion

---

## 🎯 **Zusammenfassung**

### Workflow in 3 Schritten

```bash
# 1. Speichern
python save_workflow_results.py --name "mein_test"

# 2. Dashboard starten
panel serve load_dashboard.py --show

# 3. Analysieren & Vergleichen
# → Dropdown → Auswählen → Metadaten → Dashboard
```

### Hauptvorteile

✅ **Metadaten-Tracking**: Scenario, Technologien, Solver, Kosten
✅ **Multi-Simulation**: Mehrere Läufe vergleichen
✅ **Schneller Start**: Dashboard in < 5 Sekunden
✅ **Reproduzierbar**: Alle Infos gespeichert
✅ **Interaktiv**: Zoom, Pan, Hover, Filter

**Viel Erfolg mit deinen Simulationen! 🚀**
