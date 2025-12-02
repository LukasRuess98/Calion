# 🔧 Dashboard Kernel Reload Fix

## Problem: Dashboard zeigt alte Version

Wenn du das Notebook bereits geöffnet hattest, bevor die Dashboard-Fixes committed wurden, lädt Python **noch die alte Version** aus dem Kernel-Cache.

---

## ✅ Lösung 1: Kernel Restart (Empfohlen)

### **In Jupyter Notebook:**
```
Menü: Kernel > Restart Kernel
```

### **In VS-Code:**
```
1. Klick auf den Kernel-Namen oben rechts
2. Klick auf "Restart"
```

### **In JupyterLab:**
```
Menü: Kernel > Restart Kernel...
```

Nach dem Restart: **Run All Cells** neu ausführen

---

## ✅ Lösung 2: Autoreload aktivieren (Prevention)

**Füge diese Zelle ganz am Anfang des Notebooks ein** (vor allen anderen Importen):

```python
# NEUE ERSTE ZELLE IM NOTEBOOK:
%load_ext autoreload
%autoreload 2

print("✅ Autoreload aktiviert - Code-Änderungen werden automatisch geladen")
```

**Was macht das?**
- `%autoreload 2` lädt alle Module bei jeder Zellen-Ausführung neu
- Dashboard-Änderungen werden automatisch übernommen
- Kein manueller Kernel-Restart mehr nötig

---

## ✅ Lösung 3: Manuelles Reload (Im laufenden Kernel)

Wenn Kernel-Restart nicht möglich ist, füge diese Zelle **VOR** der Dashboard-Erstellung ein:

```python
# RELOAD DASHBOARD (vor dashboard erstellen)
import importlib
import sys

# Entferne alte Module
modules_to_reload = [
    'energis.io.dashboard',
    'energis.io.notebook_helpers'
]

for module_name in modules_to_reload:
    if module_name in sys.modules:
        del sys.modules[module_name]
        print(f"🔄 {module_name} entfernt")

# Importiere neu
from energis.io.notebook_helpers import create_and_display_dashboard
print("✅ Dashboard-Module neu geladen")
```

---

## ✅ Lösung 4: Prüfe geladene Version

**Füge diese Debug-Zelle ein**, um zu prüfen welche Version geladen ist:

```python
# DEBUG: Zeige geladene Dashboard-Version
import inspect
from energis.io.dashboard import EnerGISDashboard

source = inspect.getsource(EnerGISDashboard._prepare_data)

# Prüfe auf neue Features
has_flexible_demand = "demand_col_names" in source
has_validation = "len(values) == len(self.df)" in source
has_logging = "logging.warning" in source

print("🔍 Dashboard Version Check:")
print(f"   {'✅' if has_flexible_demand else '❌'} Flexible Demand-Erkennung")
print(f"   {'✅' if has_validation else '❌'} Series-Validierung")
print(f"   {'✅' if has_logging else '❌'} Logging-Warnungen")

if has_flexible_demand and has_validation and has_logging:
    print("\n✅ NEUE VERSION IST GELADEN!")
else:
    print("\n❌ ALTE VERSION - Bitte Kernel neu starten!")
    print("   Jupyter: Kernel > Restart Kernel")
    print("   VS-Code: Klick auf 'Restart' im Kernel-Auswahlfeld")
```

---

## 🎯 Empfohlene Notebook-Struktur

**Neue Zellen-Reihenfolge für scenario_studio.ipynb:**

```python
# ===== ZELLE 0: AUTORELOAD (NEU!) =====
%load_ext autoreload
%autoreload 2
print("✅ Autoreload aktiviert")

# ===== ZELLE 1: Setup =====
import sys
from pathlib import Path
# ... (wie bisher)

# ===== ZELLE 2: Imports =====
import pandas as pd
# ... (wie bisher)

# ===== ZELLEN 3-18: Wie bisher =====
# ... Config, Optimierung, KPIs, etc.

# ===== ZELLE 19: Dashboard (UPDATE!) =====
# Dashboard mit Logging
import logging
logging.basicConfig(level=logging.WARNING)  # NEU: Zeigt Warnungen

if optimization_successful and workflow and SHOW_DASHBOARD:
    try:
        dashboard = create_and_display_dashboard(
            workflow,
            title=f"Scenario Studio - {datetime.now().strftime('%Y-%m-%d')}"
        )

        print("\n💡 Dashboard-Features:")
        print("   • Wechsle zwischen Tabs für verschiedene Ansichten")
        print("   • Im Zeitreihen-Tab: Wähle Komponenten und Zeitbereich")
        print("   • Plots sind interaktiv: Zoom, Pan, Hover")
        print("   • Kosten-Tabelle ist sortierbar")
        print("\n📋 Logs:")
        print("   Schaue oben nach WARNING-Meldungen bei Problemen")

        # Dashboard anzeigen
        dashboard

    except Exception as e:
        print(f"❌ Dashboard-Fehler: {e}")
        import traceback
        traceback.print_exc()
```

---

## 🐛 Troubleshooting

### **Problem: Dashboard zeigt noch alte Fehlermeldung**

**Lösung:**
```python
# 1. Kernel komplett neu starten
# 2. Run All Cells
# 3. Prüfe Version mit Debug-Zelle
```

### **Problem: "result.series is empty"**

**Lösung:**
```python
# Debug: Prüfe was im Workflow ist
primary_result = workflow.rh_result or workflow.mpc_result or workflow.pf_result

print("📊 Workflow Debug:")
print(f"   PF: {workflow.pf_result is not None}")
print(f"   RH: {workflow.rh_result is not None}")
print(f"   MPC: {workflow.mpc_result is not None}")

if primary_result:
    print(f"\n📋 result.series keys: {list(primary_result.series.keys())}")
    print(f"   Anzahl Series: {len(primary_result.series)}")
    print(f"   table.data keys: {list(primary_result.table.data.keys())}")
else:
    print("\n❌ Kein Ergebnis gefunden!")
```

### **Problem: Komponenten nicht erkannt**

Das neue Dashboard loggt jetzt automatisch:
```
WARNING:root:Dashboard: No heat or electric components detected.
Available columns: ['timestamp', 'demand_MW', ...]
```

**Lösung:** Prüfe ob Spalten mit `_Q_th_MW` oder `_Pel_MW` vorhanden sind

---

## 📝 Zusammenfassung

### **Sofort-Fix (für aktuelles Notebook):**
1. ✅ **Kernel > Restart Kernel**
2. ✅ **Run All Cells**
3. ✅ Dashboard sollte jetzt funktionieren

### **Langfristig (für zukünftige Sessions):**
1. ✅ Füge `%autoreload 2` am Anfang ein
2. ✅ Aktiviere Logging: `logging.basicConfig(level=logging.WARNING)`
3. ✅ Nutze Debug-Zellen bei Problemen

### **Warum passiert das?**
- Python cached importierte Module im Kernel-Speicher
- Datei-Änderungen werden nicht automatisch neu geladen
- `%autoreload` löst das Problem permanent

---

**Dein Problem ist typisch und die Lösung ist einfach: Kernel Restart! 🔄**
