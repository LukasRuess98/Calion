# 📦 Dashboard Installation Guide

## Vollständige Installations-Anleitung für das EnerGIS Dashboard

---

## ✅ **Schritt 1: Basis-Dependencies (falls noch nicht vorhanden)**

```bash
# Basis Python-Pakete für EnerGIS
pip install pandas numpy matplotlib

# Diese sind wahrscheinlich schon installiert, falls du EnerGIS nutzt
```

---

## ✅ **Schritt 2: Dashboard-spezifische Dependencies**

```bash
# Dashboard Framework und Plotting
pip install panel holoviews bokeh plotly

# Optional: Jupyter Integration
pip install jupyter-bokeh ipywidgets
```

---

## 📋 **Komplette Dependency-Liste**

Falls du von Grund auf installierst:

```bash
# Alle Dependencies auf einmal
pip install \
    pandas \
    numpy \
    matplotlib \
    panel \
    holoviews \
    bokeh \
    plotly \
    jupyter-bokeh \
    ipywidgets
```

---

## 🧪 **Schritt 3: Installation testen**

```bash
# Führe Test-Script aus
python test_dashboard.py
```

**Erwartete Ausgabe:**
```
======================================================================
🧪 Testing EnerGIS Dashboard
======================================================================

1. Testing dashboard import...
   ✅ Dashboard module imported successfully

2. Checking dependencies...
   ✅ Panel 1.3.x available
   ✅ Plotly 5.x.x available

3. Testing workflow import...
   ✅ Workflow module available

4. Checking config files...
   ✅ configs/base.yaml
   ✅ configs/tech_catalog.yaml
   ...

======================================================================
✅ Dashboard is ready to use!
======================================================================
```

---

## 🚀 **Schritt 4: Erste Verwendung**

### **Option A: Mit Demo-Notebook**

```bash
# 1. Starte Jupyter
jupyter notebook

# 2. Öffne notebooks/interactive_dashboard.ipynb

# 3. Run All Cells

# 4. Dashboard erscheint am Ende
```

### **Option B: In bestehendem Notebook**

Füge am Ende von `runner.ipynb` oder `scenario_studio.ipynb` hinzu:

```python
# Nach der Optimierung
from energis.io.dashboard import create_dashboard

dashboard = create_dashboard(workflow, title="Meine Analyse")
dashboard  # Zeigt Dashboard an
```

### **Option C: Als Webapp**

```bash
panel serve notebooks/interactive_dashboard.ipynb --show

# Öffnet Browser auf http://localhost:5006
```

---

## 🔧 **Troubleshooting**

### Problem: "No module named 'panel'"

**Lösung:**
```bash
pip install panel holoviews bokeh plotly
```

### Problem: "No module named 'pandas'"

**Lösung:**
```bash
pip install pandas numpy matplotlib
```

### Problem: Dashboard wird nicht angezeigt in Jupyter

**Lösung 1:** Neustart des Kernels
```python
# In Jupyter: Kernel > Restart & Run All
```

**Lösung 2:** JupyterLab Extension installieren
```bash
pip install jupyter-bokeh
jupyter labextension install @pyviz/jupyterlab_pyviz
jupyter lab build
```

**Lösung 3:** Explizit anzeigen
```python
dashboard.show()
```

### Problem: "ModuleNotFoundError: No module named 'energis'"

**Lösung:**
```python
# Stelle sicher, dass du im Projekt-Root bist
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd()
if 'energis' not in str(PROJECT_ROOT):
    PROJECT_ROOT = PROJECT_ROOT.parent  # Oder entsprechend anpassen

sys.path.insert(0, str(PROJECT_ROOT))
```

---

## 📦 **Versions-Anforderungen**

| Paket | Min. Version | Empfohlen |
|-------|--------------|-----------|
| Python | 3.8 | 3.11+ |
| pandas | 1.3.0 | Latest |
| numpy | 1.20.0 | Latest |
| matplotlib | 3.3.0 | Latest |
| panel | 1.0.0 | 1.3.0+ |
| plotly | 5.0.0 | Latest |
| holoviews | 1.15.0 | 1.18.0+ |
| bokeh | 3.0.0 | 3.3.0+ |

---

## 🎯 **Quick Check: Ist alles installiert?**

Kopiere diesen Code in eine Jupyter-Zelle:

```python
# Quick Dependency Check
import sys

dependencies = {
    'pandas': 'Data handling',
    'numpy': 'Numerical operations',
    'matplotlib': 'Plotting',
    'panel': 'Dashboard framework',
    'plotly': 'Interactive plots',
    'holoviews': 'High-level plotting',
    'bokeh': 'Bokeh backend',
}

print("🔍 Checking Dependencies:\n")

all_ok = True
for package, description in dependencies.items():
    try:
        module = __import__(package)
        version = getattr(module, '__version__', 'unknown')
        print(f"✅ {package:15s} {version:10s} - {description}")
    except ImportError:
        print(f"❌ {package:15s} {'NOT FOUND':10s} - {description}")
        all_ok = False

if all_ok:
    print("\n🎉 All dependencies installed!")
    print("   You're ready to use the dashboard!")
else:
    print("\n⚠️  Some dependencies are missing")
    print("   Install with: pip install panel holoviews bokeh plotly")
```

---

## 🌐 **Webapp-Modus (Optional)**

Falls du das Dashboard als Webapp bereitstellen möchtest:

### Lokal (Development):
```bash
panel serve notebooks/interactive_dashboard.ipynb --show
```

### Netzwerk-Zugriff (für Demos):
```bash
panel serve notebooks/interactive_dashboard.ipynb \
  --address 0.0.0.0 \
  --port 5006 \
  --allow-websocket-origin='*'

# Dann erreichbar unter: http://<deine-ip>:5006
```

### Production (mit Auth):
```bash
panel serve notebooks/interactive_dashboard.ipynb \
  --address 0.0.0.0 \
  --port 5006 \
  --basic-auth credentials.json

# credentials.json Format:
# {"username": "password"}
```

---

## 📚 **Weitere Ressourcen**

- **Panel Docs**: https://panel.holoviz.org/
- **Plotly Docs**: https://plotly.com/python/
- **Dashboard README**: `docs/DASHBOARD.md`
- **Demo Notebook**: `notebooks/interactive_dashboard.ipynb`

---

## ✨ **Zusammenfassung**

### Minimal-Installation (nur Dashboard):
```bash
pip install panel holoviews bokeh plotly pandas numpy
```

### Vollständige Installation (mit Jupyter):
```bash
pip install panel holoviews bokeh plotly pandas numpy \
    jupyter-bokeh ipywidgets matplotlib
```

### Test der Installation:
```bash
python test_dashboard.py
```

### Erste Verwendung:
```python
from energis.io.dashboard import create_dashboard
dashboard = create_dashboard(workflow)
dashboard
```

---

**Viel Erfolg! 🚀**

Bei Fragen siehe `docs/DASHBOARD.md` oder öffne ein Issue auf GitHub.
