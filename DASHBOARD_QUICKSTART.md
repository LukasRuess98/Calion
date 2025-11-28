# 🚀 Dashboard Quick Start

Drei einfache Scripts für das EnerGIS Dashboard.

## 📋 **1. Installation** (nur einmal)

```bash
./install_dashboard.sh
```

**Was macht das Script:**
- ✅ Prüft Python-Version
- ✅ Installiert Dashboard-Pakete (Panel, Plotly, Holoviews, Bokeh)
- ✅ Erstellt 3 Mock-Simulationen für Demo

**Dauer:** ~1-2 Minuten

---

## 🚀 **2. Dashboard starten**

```bash
./start_dashboard.sh
```

**Oder mit custom Port:**
```bash
./start_dashboard.sh 8080
```

**Was passiert:**
- Dashboard startet auf http://localhost:5006/load_dashboard
- Browser öffnet sich automatisch (wenn möglich)
- Zeigt alle verfügbaren Simulationen

**Zum Stoppen:** `Strg+C` im Terminal

---

## 🛑 **3. Dashboard stoppen**

```bash
./stop_dashboard.sh
```

**Was macht das Script:**
- Findet alle laufenden Dashboard-Prozesse
- Stoppt sie sauber
- Zeigt Bestätigung

---

## 📊 **Dashboard verwenden**

### **Nach dem Start:**

1. **Browser öffnen:** http://localhost:5006/load_dashboard

2. **Simulation auswählen:**
   - Klick auf Dropdown oben
   - Wähle zwischen: baseline, large_storage, optimized

3. **Metadaten ansehen:**
   - Scenario, System, Site
   - Technologien (Wärmepumpen, Speicher)
   - Kosten (CAPEX, OPEX)

4. **Dashboard erkunden:**
   - Tab "Overview": KPIs
   - Tab "Timeseries": Interaktive Plots ⭐
   - Tab "Costs": Kosten-Breakdown
   - Tab "Design": Kapazitäten
   - Tab "Comparison": PF vs RH

### **Interaktive Features:**
- ✅ **Zoom**: Mausrad oder Box-Select
- ✅ **Pan**: Mit Maus ziehen
- ✅ **Hover**: Werte anzeigen
- ✅ **Komponenten**: Checkboxen an/aus
- ✅ **Zeitbereich**: Slider anpassen

---

## 🔧 **Eigene Simulationen hinzufügen**

### **Mit echten Daten:**

```bash
# 1. Simulation ausführen und speichern
python save_workflow_results.py --name "mein_test" \
    --description "Meine erste Simulation"

# 2. Dashboard neu laden (automatisch erkannt)
# Keine weiteren Schritte nötig!
```

### **Weitere Mock-Daten:**

```bash
# Mock-Simulationen neu erstellen
python create_mock_simulations.py
```

---

## 📁 **Verzeichnis-Struktur**

```
Planing-Framework-for-Heat/
├── install_dashboard.sh          # Installation
├── start_dashboard.sh            # Dashboard starten
├── stop_dashboard.sh             # Dashboard stoppen
├── save_workflow_results.py      # Echte Simulation speichern
├── create_mock_simulations.py    # Mock-Daten erstellen
├── load_dashboard.py             # Dashboard-Webapp
├── saved_workflows/              # Gespeicherte Simulationen
│   ├── 2025-11-28_..._baseline/
│   │   ├── workflow.pkl
│   │   └── metadata.json
│   └── ...
└── REAL_DATA_GUIDE.md           # Vollständige Dokumentation
```

---

## ❓ **Troubleshooting**

### **"Port bereits belegt"**

```bash
# Option 1: Stoppe altes Dashboard
./stop_dashboard.sh

# Option 2: Verwende anderen Port
./start_dashboard.sh 8080
```

### **"Keine Simulationen gefunden"**

```bash
# Mock-Simulationen erstellen
python create_mock_simulations.py

# Oder komplette Installation
./install_dashboard.sh
```

### **"Pakete fehlen"**

```bash
# Nochmal installieren
./install_dashboard.sh
```

---

## 📖 **Weitere Dokumentation**

- **REAL_DATA_GUIDE.md**: Vollständige Anleitung für echte Simulationen
- **DASHBOARD.md**: Dashboard-Features im Detail
- **docs/**: Weitere technische Dokumentation

---

## 🎯 **Workflow-Übersicht**

```bash
# Einmalig: Installation
./install_dashboard.sh

# Jedes Mal: Dashboard verwenden
./start_dashboard.sh
# → Browser öffnen: http://localhost:5006/load_dashboard
# → Simulationen erkunden
# → Strg+C zum Stoppen

# Optional: Dashboard im Hintergrund stoppen
./stop_dashboard.sh
```

---

**Viel Erfolg! 🚀**
