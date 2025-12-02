# 🚀 Dashboard Quick Start Guide

## Schnelleinstieg in 3 Minuten

### **Methode 1: Jupyter Notebook (empfohlen für VS-Code)**

```python
# 1. Notebook öffnen
# notebooks/scenario_studio.ipynb in VS-Code oder Jupyter

# 2. Workflow ausführen (oder laden)
from energis.run import rolling_horizon as rh
from energis.io.dashboard import create_dashboard

# Workflow ausführen
workflow = rh.run_workflow([
    "configs/base.yaml",
    "configs/tech_catalog.yaml",
    "configs/sites/default.site.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/pf_then_rh.workflow.scenario.yaml",
])

# 3. Dashboard erstellen
dashboard = create_dashboard(workflow, title="Mein Dashboard")

# 4. Anzeigen
dashboard  # In Jupyter-Zelle evaluieren
```

✅ Dashboard erscheint **inline im Notebook**

---

### **Methode 2: Panel Server (empfohlen für Browser)**

```bash
# 1. Terminal öffnen
cd /path/to/Planing-Framework-for-Heat

# 2. Panel Server starten
panel serve notebooks/scenario_studio.ipynb --show

# Browser öffnet sich automatisch mit:
# http://localhost:5006/scenario_studio
```

✅ Dashboard läuft als **eigenständige Webapp**

---

### **Methode 3: Gespeicherten Workflow laden**

```python
from energis.io.notebook_helpers import (
    load_workflow_from_saved,
    create_and_display_dashboard
)

# 1. Workflow laden
workflow = load_workflow_from_saved("saved_workflows/2025-12-01_...")

# 2. Dashboard erstellen
dashboard = create_and_display_dashboard(
    workflow,
    title="Geladenes Dashboard"
)

# 3. Anzeigen
dashboard
```

✅ Schneller Start ohne erneute Optimierung

---

## 🎯 Dashboard-Features nutzen

### **Zeitreihen-Tab:**

1. **Komponenten auswählen:**
   - Klick auf MultiChoice Dropdown
   - Wähle z.B. "HP1", "HP2", "HP3"
   - Komponenten erscheinen im Plot

2. **Zeitbereich ändern:**
   - Ziehe Slider-Handles
   - Wähle z.B. erste 7 Tage (0-168h)
   - Plot zoomed automatisch

3. **Plot-Typ wechseln:**
   - Dropdown: "Stacked Area" → "Lines"
   - Visualisierung ändert sich sofort

4. **Interaktiv erkunden:**
   - **Hover:** Mouse über Plot → zeigt Werte
   - **Zoom:** Box-Select mit Maus
   - **Pan:** Drag zum Verschieben
   - **Reset:** Doppelklick auf Plot

### **Kosten-Tab:**

1. **Tabelle sortieren:**
   - Klick auf Spalten-Header
   - Sortiert nach Werten

2. **Filtern:**
   - Klick in Filter-Zeile (unter Header)
   - Eingabe: "electricity" → Zeigt nur Strom-Kosten

### **Design-Tab:**

1. **Kapazitäten ansehen:**
   - Balkendiagramm zeigt alle Komponenten
   - Tabelle zeigt Zahlen-Details

2. **JSON exportieren:**
   - Scroll nach unten zum JSON-Pane
   - Zeigt vollständige Design-Daten

---

## 🔧 Troubleshooting

### **Problem: Dashboard zeigt nur Text, keine interaktiven Plots**

**Lösung:**
```bash
# Panel Server starten
panel serve notebooks/scenario_studio.ipynb --show
```

### **Problem: "ModuleNotFoundError: No module named 'panel'"**

**Lösung:**
```bash
pip install panel holoviews bokeh plotly
```

### **Problem: VS-Code zeigt Dashboard nicht inline**

**Lösung 1:** Panel Server verwenden
```bash
panel serve notebooks/scenario_studio.ipynb --show
```

**Lösung 2:** Simple Browser in VS-Code
```
Cmd/Ctrl+Shift+P > "Simple Browser: Show"
URL: http://localhost:5006
```

### **Problem: "No results available in workflow"**

**Lösung:** Prüfe ob Optimierung erfolgreich war
```python
# Workflow-Status prüfen
print(f"PF: {workflow.pf_result is not None}")
print(f"RH: {workflow.rh_result is not None}")
print(f"MPC: {workflow.mpc_result is not None}")
```

### **Problem: Zeitreihen-Tab zeigt "Keine Komponenten erkannt"**

**Lösung:** Prüfe verfügbare Spalten
```python
# Im Log nachsehen (nach create_dashboard)
# Zeigt: "Available columns: ['timestamp', 'demand_MW', ...]"

# Dashboard erwartet Spalten mit:
# - _Q_th_MW (thermische Komponenten)
# - _Pel_MW (elektrische Komponenten)
```

---

## 📊 Verschiedene Szenarien

### **PF_ONLY:**
```python
workflow = rh.run_workflow(CONFIG_PATHS, overrides={
    'scenario': {'run_mode': 'PF_ONLY'}
})
dashboard = create_dashboard(workflow)
```
✅ Zeigt PF-Ergebnisse und Design

### **RH_ONLY:**
```python
workflow = rh.run_workflow(CONFIG_PATHS, overrides={
    'scenario': {'run_mode': 'RH_ONLY'}
})
dashboard = create_dashboard(workflow)
```
✅ Zeigt RH-Ergebnisse, Design-Tab zeigt Hinweis

### **PF_THEN_RH:**
```python
workflow = rh.run_workflow(CONFIG_PATHS, overrides={
    'scenario': {'run_mode': 'PF_THEN_RH'}
})
dashboard = create_dashboard(workflow)
```
✅ Zeigt RH-Ergebnisse, PF-Design, und Vergleichs-Tab

---

## 🌐 Als Webapp deployen

### **Lokal testen:**
```bash
panel serve notebooks/scenario_studio.ipynb \
    --port 5006 \
    --show \
    --autoreload
```

### **Für Team-Zugriff:**
```bash
panel serve notebooks/scenario_studio.ipynb \
    --address 0.0.0.0 \
    --port 5006 \
    --allow-websocket-origin="*"

# Zugriff von anderen Rechnern:
# http://<deine-ip>:5006
```

⚠️ **Sicherheit:** Nur in vertrauenswürdigen Netzwerken!

### **Mit Docker:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

EXPOSE 5006

CMD ["panel", "serve", "notebooks/scenario_studio.ipynb", \
     "--address", "0.0.0.0", "--port", "5006", \
     "--allow-websocket-origin=*"]
```

```bash
docker build -t energis-dashboard .
docker run -p 5006:5006 energis-dashboard
```

---

## 💡 Pro-Tips

### **1. Mehrere Workflows vergleichen:**
```python
# Workflow 1: Baseline
workflow1 = rh.run_workflow(CONFIG_BASELINE)
dashboard1 = create_dashboard(workflow1, title="Baseline")

# Workflow 2: Mit höherem CO2-Preis
workflow2 = rh.run_workflow(CONFIG_HIGH_CO2)
dashboard2 = create_dashboard(workflow2, title="High CO2")

# Beide anzeigen (in separaten Zellen)
dashboard1  # Zelle 1
dashboard2  # Zelle 2
```

### **2. Großes Zeitfenster → Aggregiere:**
```python
# Für 4 Jahre Daten (35k Zeitschritte)
# Aggregiere auf Tageswerte vor Dashboard

import pandas as pd

# Erstelle DF
df = pd.DataFrame({
    'timestamp': result.table.index,
    **result.series
})
df.set_index('timestamp', inplace=True)

# Aggregiere auf Tag
df_daily = df.resample('1D').mean()

# Dann normale Dashboard-Erstellung
# (Result anpassen mit aggregierten Daten)
```

### **3. Logging aktivieren:**
```python
import logging
logging.basicConfig(level=logging.WARNING)

# Jetzt zeigt create_dashboard Warnungen bei:
# - Fehlenden Spalten
# - Übersprungenen Series
# - Komponenten-Problemen
```

### **4. Workflow automatisch speichern:**
```python
from energis.io.notebook_helpers import save_workflow_run

# Nach Optimierung
workflow_dir = save_workflow_run(
    workflow,
    name="Meine Simulation",
    description="Baseline mit 4 Wärmepumpen",
    config_paths=CONFIG_PATHS
)

# Später laden
workflow = load_workflow_from_saved(workflow_dir)
dashboard = create_dashboard(workflow)
```

---

## 📚 Weitere Hilfe

- **Dokumentation:** `DASHBOARD_FIX_DOCUMENTATION.md`
- **Validierung:** `DASHBOARD_VALIDATION_REPORT.md`
- **Test-Skript:** `test_dashboard_fix.py`
- **Notebook:** `notebooks/scenario_studio.ipynb`
- **Panel Docs:** https://panel.holoviz.org/

---

**Viel Erfolg mit dem Dashboard! 🎉**
