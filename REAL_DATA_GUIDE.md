# 🎯 Dashboard mit echten Simulationsdaten

Dieses Dokument erklärt, wie du das Dashboard mit **echten Optimierungsergebnissen** statt Mock-Daten verwendest.

## 📋 Übersicht der Optionen

| Option | Vorteile | Nachteile | Beste für |
|--------|----------|-----------|-----------|
| **1. Speichern & Laden** ⭐ | ✅ Schneller Start<br>✅ Wiederholbar<br>✅ Mehrere Szenarien vergleichbar | ❌ Muss vorberechnet werden | **Analyse vorhandener Ergebnisse** |
| **2. Live-Optimierung** | ✅ Immer aktuelle Daten<br>✅ Kein Extra-Schritt | ❌ Langsamer Start<br>❌ Bei jedem Aufruf neu | **Entwicklung & Testing** |
| **3. Jupyter Integration** | ✅ Interaktive Analyse<br>✅ Teil des Workflows | ❌ Benötigt Jupyter | **Explorative Analyse** |

---

## ⭐ **Option 1: Speichern & Laden (EMPFOHLEN)**

### Workflow

```
Optimierung ausführen → Ergebnisse speichern → Dashboard laden → Schnelle Webapp
```

### Schritt 1: Ergebnisse speichern

```bash
# Optimierung ausführen und Ergebnisse speichern
python save_workflow_results.py
```

**Output:**
- Datei: `workflow_results.pkl`
- Enthält: Komplettes workflow-Objekt mit allen Ergebnissen

**Dauer:** 5-30 Minuten (je nach Szenario)

### Schritt 2: Dashboard starten

```bash
# Dashboard mit gespeicherten Ergebnissen starten
panel serve load_dashboard.py --show
```

**Output:**
- URL: http://localhost:5006/load_dashboard
- **Start in < 5 Sekunden** ⚡

### Vorteile dieser Methode

1. **Schnell:** Dashboard startet sofort
2. **Reproduzierbar:** Gleiche Ergebnisse bei jedem Aufruf
3. **Vergleichbar:** Mehrere Szenarien speichern und vergleichen
4. **Effizient:** Optimierung nur einmal durchführen

### Mehrere Szenarien vergleichen

```bash
# Szenario 1: Baseline
python save_workflow_results.py
mv workflow_results.pkl workflow_baseline.pkl

# Szenario 2: Advanced
# (Ändere CONFIG_PATHS in save_workflow_results.py)
python save_workflow_results.py
mv workflow_results.pkl workflow_advanced.pkl

# Dashboard für Baseline
cp workflow_baseline.pkl workflow_results.pkl
panel serve load_dashboard.py --show

# Dashboard für Advanced
cp workflow_advanced.pkl workflow_results.pkl
panel serve load_dashboard.py --show
```

---

## 🔥 **Option 2: Live-Optimierung**

### Workflow

```
Webapp starten → Optimierung läuft → Dashboard wird angezeigt
```

### Verwendung

```bash
# Dashboard mit On-the-fly Optimierung
panel serve run_dashboard.py --show
```

**Hinweis:**
- Die Optimierung läuft **bei jedem Start** der Webapp
- Dauer: 5-30 Minuten bis Dashboard verfügbar ist
- Browser öffnet sich erst nach Abschluss der Optimierung

### Konfiguration anpassen

Bearbeite `run_dashboard.py` und ändere `CONFIG_PATHS`:

```python
# Standard-Konfiguration
CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/default.site.yaml',
    'configs/systems/baseline.system.yaml',
    'configs/scenarios/pf_then_rh.workflow.scenario.yaml',
]

# Oder eigene Konfiguration
CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/my_site.site.yaml',
    'configs/systems/my_system.system.yaml',
    'configs/scenarios/my_scenario.workflow.scenario.yaml',
]
```

### Wann Option 2 verwenden?

- 🔬 **Entwicklung:** Code-Änderungen testen
- 🐛 **Debugging:** Probleme nachstellen
- 🆕 **Neue Szenarien:** Schnell verschiedene Configs ausprobieren

---

## 📓 **Option 3: Jupyter Notebook Integration**

### Bereits verfügbar in:

1. **notebooks/scenario_studio.ipynb** ✅
   - Dashboard-Zelle am Ende
   - Wird automatisch nach Optimierung angezeigt

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

# 3. Optimierung
workflow = rh.run_workflow(CONFIG_PATHS)

# 4. Dashboard anzeigen
dashboard = create_dashboard(workflow, title="Mein Dashboard")
dashboard  # Zeigt Dashboard inline an
```

### Vorteile

- ✅ **Interaktiv:** Code und Visualisierung kombiniert
- ✅ **Dokumentation:** Analyse-Schritte nachvollziehbar
- ✅ **Flexibel:** Plots anpassen und erweitern

---

## 🛠️ **Voraussetzungen**

### Für Mock-Daten (aktuell)

```bash
pip install panel holoviews bokeh plotly
```

### Für echte Optimierung (alle Optionen)

```bash
# Python-Pakete
pip install panel holoviews bokeh plotly
pip install pyomo

# Solver (wähle einen)
# Option A: GLPK (kostenlos, für kleine Probleme)
sudo apt-get install glpk-utils

# Option B: Gurobi (kommerzielle Lizenz, sehr schnell)
# Siehe: https://www.gurobi.com/

# Option C: CPLEX (kommerzielle Lizenz, sehr schnell)
# Siehe: https://www.ibm.com/analytics/cplex-optimizer
```

---

## 🚀 **Quick Start Guide**

### Szenario A: "Ich will schnell Ergebnisse sehen"

```bash
# Schritt 1: Ergebnisse einmal berechnen (dauert)
python save_workflow_results.py

# Schritt 2: Dashboard starten (schnell!)
panel serve load_dashboard.py --show
```

### Szenario B: "Ich entwickle neue Features"

```bash
# Dashboard mit Live-Optimierung
panel serve run_dashboard.py --show
```

### Szenario C: "Ich will im Notebook arbeiten"

```bash
# Jupyter starten
jupyter notebook

# Öffne: notebooks/scenario_studio.ipynb
# Run All Cells → Dashboard erscheint am Ende
```

---

## 📊 **Vergleich: Mock vs. Real Data**

### Aktuell: Mock-Daten

```bash
panel serve demo_dashboard_mock.py --show
```

- ✅ Startet sofort (< 1 Sekunde)
- ❌ Fake-Daten (168 Stunden, sinusförmig)
- 🎯 **Zweck:** Dashboard-Interface testen

### Neu: Echte Daten

```bash
panel serve load_dashboard.py --show
```

- ✅ Echte Optimierungsergebnisse
- ✅ Realistische Zeitreihen
- ✅ Tatsächliche Kosten
- 🎯 **Zweck:** Ergebnisse analysieren

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

# macOS
brew install glpk

# Windows
# Download von: https://sourceforge.net/projects/winglpk/
```

### "workflow_results.pkl not found"

**Lösung:**
```bash
# Zuerst Ergebnisse speichern!
python save_workflow_results.py

# Dann Dashboard laden
panel serve load_dashboard.py --show
```

### "Optimization takes too long"

**Lösungen:**
1. Kleineren Zeithorizont verwenden
2. Schnelleren Solver installieren (Gurobi/CPLEX)
3. Weniger Komponenten im System
4. Gröbere Zeitauflösung

---

## 💡 **Best Practices**

### 1. Entwicklung

```bash
# Während der Entwicklung: Mock-Daten
panel serve demo_dashboard_mock.py --show

# Schnelle Iterationen
# Keine Wartezeit
```

### 2. Testing

```bash
# Kleines Szenario: Live-Optimierung
panel serve run_dashboard.py --show

# Funktionalität mit echten Daten prüfen
```

### 3. Produktion/Präsentation

```bash
# Ergebnisse vorberechnen
python save_workflow_results.py

# Dashboard für Präsentation
panel serve load_dashboard.py --show

# Schneller Start, zuverlässig
```

### 4. Vergleichsanalyse

```bash
# Mehrere Szenarien berechnen
for scenario in baseline advanced optimized; do
    # CONFIG_PATHS in save_workflow_results.py anpassen
    python save_workflow_results.py
    mv workflow_results.pkl workflow_${scenario}.pkl
done

# Dashboards nacheinander öffnen und vergleichen
```

---

## 📁 **Dateiübersicht**

| Datei | Zweck | Verwendung |
|-------|-------|------------|
| `demo_dashboard_mock.py` | Mock-Daten Dashboard | Schnelles Testing |
| `save_workflow_results.py` | Ergebnisse speichern | Optimierung ausführen |
| `load_dashboard.py` | Gespeicherte Ergebnisse laden | Schnelle Webapp |
| `run_dashboard.py` | Live-Optimierung + Dashboard | Entwicklung |
| `workflow_results.pkl` | Gespeicherte Ergebnisse | Zwischen save/load |

---

## 🎓 **Nächste Schritte**

1. **Solver installieren** (siehe Voraussetzungen)
2. **Ersten Test:** `python save_workflow_results.py`
3. **Dashboard starten:** `panel serve load_dashboard.py --show`
4. **Erkunden:** Verschiedene Tabs ausprobieren
5. **Anpassen:** Eigene Szenarien in CONFIG_PATHS eintragen

---

## 📞 **Support**

Bei Problemen oder Fragen:
1. Prüfe Troubleshooting-Section oben
2. Checke Logausgaben der Skripte
3. Erstelle GitHub Issue mit:
   - Verwendete Option (1/2/3)
   - Fehlermeldung
   - Verwendete Konfiguration

---

**Viel Erfolg mit echten Daten! 🚀**
