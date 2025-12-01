# 📓 Notebook Update Guide

## Zusammenfassung: Wie man die Dashboard-Fixes nutzt

Alle aktiven Notebooks (`scenario_studio.ipynb`, `runner.ipynb`) sind bereit für die neuen Dashboard-Fixes. Folge dieser Anleitung um sie zu nutzen.

---

## ✅ Was wurde aktualisiert

### **Dashboard-Code (`energis/io/dashboard.py`):**
- ✅ Flexible Spaltennamen-Erkennung
- ✅ Robuste Validierung von Series-Daten
- ✅ Aussagekräftige Fehlermeldungen
- ✅ Logging von Problemen
- ✅ Unterstützung aller Szenarien (PF, RH, MPC)

### **Notebooks benötigen NUR einen Kernel-Restart:**
Die Notebooks selbst sind korrekt und müssen **nicht** geändert werden. Sie nutzen bereits:
- ✅ `create_and_display_dashboard()` aus `notebook_helpers`
- ✅ Korrekte Import-Struktur
- ✅ Error-Handling

---

## 🚀 Quick Start: Notebook mit neuen Fixes verwenden

### **Schritt 1: Kernel Restart (WICHTIG!)**

**In Jupyter Notebook:**
```
Menü: Kernel > Restart Kernel
```

**In VS-Code:**
```
Klick auf Kernel-Name oben rechts > "Restart"
```

**In JupyterLab:**
```
Menü: Kernel > Restart Kernel...
```

### **Schritt 2: Run All Cells**
```
Cell > Run All
```

### **Schritt 3: Dashboard sollte funktionieren!**

Das Dashboard lädt jetzt automatisch die neue Version mit allen Fixes.

---

## 🔧 Optional: Autoreload dauerhaft aktivieren

Wenn du häufig Code-Änderungen machst, aktiviere Autoreload **permanent**:

### **Für scenario_studio.ipynb:**

Füge diese Zelle **ganz am Anfang** ein (vor Zelle 1):

```python
# ============================================================================
# ZELLE 0: AUTORELOAD (NEU - ganz am Anfang einfügen)
# ============================================================================

# IPython Magic: Autoreload
%load_ext autoreload
%autoreload 2

# Logging konfigurieren
import logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)

print("="*70)
print("✅ AUTORELOAD AKTIVIERT")
print("="*70)
print("📝 Code-Änderungen werden automatisch neu geladen")
print("📋 Logging aktiviert - Dashboard-Probleme werden angezeigt")
print("="*70)
```

### **Für runner.ipynb:**

Füge die gleiche Zelle am Anfang ein.

### **Was bringt das?**
- ✅ Kein Kernel-Restart mehr nötig bei Code-Änderungen
- ✅ Dashboard lädt automatisch neueste Version
- ✅ Logging zeigt sofort Probleme an
- ✅ Besseres Debugging-Erlebnis

---

## 🐛 Troubleshooting

### **Problem: Dashboard zeigt alte Fehlermeldungen**

**Ursache:** Kernel hat alte Version gecached

**Lösung:**
```
1. Kernel > Restart Kernel
2. Run All Cells
3. Problem sollte behoben sein
```

### **Problem: "No demand column found"**

**Ursache:** Das neue Dashboard sucht mehrere Spaltennamen, findet aber keine

**Lösung:** Prüfe welche Spalten vorhanden sind:
```python
# Debug-Zelle einfügen:
primary_result = workflow.rh_result or workflow.mpc_result or workflow.pf_result
print("Verfügbare Spalten in table.data:")
print(list(primary_result.table.data.keys()))
```

Das Dashboard sucht nach:
- `waermebedarf_MWth`
- `Waermebedarf_MWth`
- `heat_demand_MW`
- `demand_MW`
- `Q_demand_MW`

### **Problem: "No components detected"**

**Ursache:** Dashboard findet keine Spalten mit `_Q_th_MW` oder `_Pel_MW`

**Lösung:** Prüfe Series-Keys:
```python
# Debug-Zelle:
primary_result = workflow.rh_result or workflow.mpc_result or workflow.pf_result
print("Series Keys:")
print(list(primary_result.series.keys())[:20])
```

Dashboard sucht:
- Wärme: `*_Q_th_MW`
- Elektro: `*_Pel_MW`
- Speicher: `*TES*`

### **Problem: "No cost data available"**

**Ursache:** `result.costs` ist leer oder None

**Lösung:** Prüfe ob Optimierung erfolgreich war:
```python
# Debug-Zelle:
print(f"PF: {workflow.pf_result is not None}")
print(f"RH: {workflow.rh_result is not None}")

if workflow.rh_result:
    print(f"Costs available: {workflow.rh_result.costs is not None}")
    if workflow.rh_result.costs:
        print(f"Number of cost entries: {len(workflow.rh_result.costs)}")
```

### **Problem: "No design available"**

**Ursache:** Kein PF-Schritt wurde ausgeführt

**Lösung:** Design wird nur in PF erstellt. Nutze:
- `PF_ONLY`
- `PF_THEN_RH`
- `PF_THEN_MPC`

Oder lade bestehendes Design:
```python
overrides = {
    'scenario': {
        'pf_design_json': 'path/to/design.json'
    }
}
workflow = rh.run_workflow(CONFIG_PATHS, overrides=overrides)
```

---

## 📊 Verfügbare Notebooks

### **1. scenario_studio.ipynb** (Empfohlen für Analysen)
- ✅ Interaktive Szenario-Analyse
- ✅ Wissenschaftliche Plots (PDF + SVG)
- ✅ KPI-Analyse
- ✅ Dashboard-Integration
- ✅ Workflow-Speicherung

**Verwendung:**
```bash
# In Jupyter
jupyter notebook notebooks/scenario_studio.ipynb

# Als Panel Server
panel serve notebooks/scenario_studio.ipynb --show
```

### **2. runner.ipynb** (Batch-Läufe)
- ✅ Schnelle Optimierungsläufe
- ✅ Minimale Ausgabe
- ✅ Workflow-Speicherung
- ✅ Optional: Dashboard

**Verwendung:**
```bash
# In Jupyter
jupyter notebook notebooks/runner.ipynb
```

### **3. synthetic_example.ipynb** (Tests)
- ✅ Synthetische Testdaten
- ✅ Für Entwicklung
- ✅ Keine realen Daten nötig

---

## 🔄 Workflow-Vergleich

### **Notebook bereits offen:**

**OHNE Autoreload:**
1. Code-Änderung in `dashboard.py`
2. ❌ Notebook lädt alte Version
3. ✅ Kernel > Restart Kernel nötig
4. ✅ Run All Cells
5. ✅ Neue Version wird geladen

**MIT Autoreload:**
1. Code-Änderung in `dashboard.py`
2. ✅ Notebook lädt automatisch neu
3. ✅ Keine Aktion nötig
4. ✅ Nächste Zellen-Ausführung nutzt neue Version

---

## 📁 Datei-Übersicht

### **Haupt-Notebooks:**
- `notebooks/scenario_studio.ipynb` - Interaktive Analysen
- `notebooks/runner.ipynb` - Batch-Optimierungen
- `notebooks/synthetic_example.ipynb` - Test-Notebook

### **Archiv (veraltet):**
- `notebooks/archive/comparison_dashboard.ipynb`
- `notebooks/archive/interactive_dashboard.ipynb`
- `notebooks/archive/workflow_manager.ipynb`
- `notebooks/archive/rolling_horizon_validation.ipynb`
- `notebooks/archive/test_runner.ipynb`

⚠️ **Archive-Notebooks sind veraltet** und nutzen alte APIs. Verwende stattdessen die aktuellen Notebooks.

---

## 💡 Best Practices

### **1. Entwicklung:**
```python
# Zelle 0: Autoreload + Logging
%load_ext autoreload
%autoreload 2

import logging
logging.basicConfig(level=logging.WARNING)
```

### **2. Production:**
```python
# Nur Kernel-Restart bei Bedarf
# Kein Autoreload (bessere Performance)
```

### **3. Debugging:**
```python
# Logging aktivieren
import logging
logging.basicConfig(level=logging.DEBUG)  # Sehr detailliert

# Oder nur Warnungen:
logging.basicConfig(level=logging.WARNING)
```

### **4. Lange Simulationen:**
```python
# Workflow speichern VOR Dashboard-Erstellung
workflow_dir = save_workflow_run(workflow, ...)

# Dashboard separat erstellen
dashboard = create_and_display_dashboard(workflow)
```

---

## 🎯 Zusammenfassung

### **Für neue Simulationen:**
1. ✅ Kernel > Restart Kernel
2. ✅ Run All Cells
3. ✅ Dashboard funktioniert automatisch

### **Für Entwicklung:**
1. ✅ Füge Autoreload-Zelle am Anfang ein
2. ✅ Aktiviere Logging
3. ✅ Kein Kernel-Restart mehr nötig

### **Bei Problemen:**
1. ✅ Kernel-Restart durchführen
2. ✅ Logs prüfen (WARNING-Level)
3. ✅ Debug-Zellen verwenden
4. ✅ Siehe `DASHBOARD_KERNEL_FIX.md`

---

## 📚 Weitere Ressourcen

- **Dashboard-Fixes:** `DASHBOARD_FIX_DOCUMENTATION.md`
- **Validierung:** `DASHBOARD_VALIDATION_REPORT.md`
- **Quick Start:** `DASHBOARD_QUICKSTART.md`
- **Kernel-Problem:** `DASHBOARD_KERNEL_FIX.md`
- **Autoreload-Code:** `notebook_autoreload_patch.py`

---

**Die Notebooks sind bereit! Nur Kernel-Restart durchführen und los geht's! 🚀**
