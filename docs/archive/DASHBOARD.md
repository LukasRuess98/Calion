# 🎛️ EnerGIS Dashboard

Standalone Dashboard zur Visualisierung gespeicherter Simulationsergebnisse.

## 🎯 Übersicht

Das EnerGIS Dashboard ist eine unabhängige Webanwendung zur interaktiven Visualisierung und Analyse gespeicherter Workflow-Simulationen. Es läuft **unabhängig** von aktiven Simulationen und lädt automatisch alle verfügbaren Ergebnisse aus dem `saved_workflows/` Verzeichnis.

### ✨ Features

- **📁 Automatisches Scannen** aller Simulationen in `saved_workflows/`
- **🔍 Dropdown-Auswahl** zur Navigation zwischen verschiedenen Workflows
- **📊 Vollständiges Dashboard** mit interaktiven Tabs:
  - 📈 **Übersicht**: Erweiterte KPIs inkl. Autarkie-Metriken
  - 📉 **Zeitreihen**: Interaktive Plots mit Quick-Filtern
  - 📊 **Jahresdauerlinie**: Load Duration Curve für Dimensionierung
  - ⚡ **Effizienz & COP**: Wärmepumpen-Performance-Analyse
  - 🌊 **Energieflüsse**: Sankey-Diagramm für Energiebilanzen
  - 💰 **Kosten**: Detaillierte Kostenaufschlüsselung
  - 🏭 **Anlagen**: Komponenten-Design und Auslastung
  - 🔀 **Vergleich**: PF vs. RH/MPC Vergleich
- **📈 Interaktive Plots**: Zoom, Pan, Hover mit Plotly
- **⚡ Quick-Filter Buttons**: Erste Woche, Winter-Tag, Sommer-Tag, Ganzes Jahr
- **🎯 Autarkie-Metriken**: Thermische Autarkie, Auslastungsfaktor, Betriebsstunden
- **🚀 Performance**: Automatisches Downsampling für große Datensätze (>20k Punkte)
- **💾 Zugriff auf Rohdaten**: CSV-Export und Metadaten

## 🚀 Quick Start

### Variante 1: Python-Skript (empfohlen)

Das einfachste und schnellste Setup:

```bash
# Im Projekt-Root
python start_dashboard.py
```

Das Dashboard öffnet sich automatisch im Browser unter `http://localhost:5007`.

**Optionen:**
```bash
# Spezifisches Verzeichnis
python start_dashboard.py --dir my_workflows/

# Anderer Port
python start_dashboard.py --port 5008

# Ohne automatisches Browser-Öffnen
python start_dashboard.py --no-show

# Debug-Modus
python start_dashboard.py --debug

# Hilfe
python start_dashboard.py --help
```

### Variante 2: Workflow Browser Notebook

Falls du das Dashboard in einem Jupyter-Umfeld starten möchtest:

```bash
# Mit Panel's Built-in Server
panel serve notebooks/workflow_browser.ipynb --show

# Mit spezifischem Port
panel serve notebooks/workflow_browser.ipynb --port 5008 --show

# Ohne Auto-Open
panel serve notebooks/workflow_browser.ipynb
```

## 📋 Voraussetzungen

### Erforderliche Pakete

```bash
pip install panel holoviews bokeh plotly
```

Oder mit allen optionalen Dependencies:

```bash
pip install -e ".[dashboard]"
```

### Gespeicherte Workflows

Das Dashboard benötigt mindestens einen gespeicherten Workflow in `saved_workflows/`.

**Workflows erstellen:**
- Mit `notebooks/runner.ipynb` - Standard-Optimierungsläufe
- Mit `notebooks/scenario_studio.ipynb` - Interaktive Szenario-Analysen
- Via CLI: `python -m energis.run.rolling_horizon --config ...`

Jeder Workflow wird automatisch in `saved_workflows/` mit folgendem Inhalt gespeichert:
```
saved_workflows/
└── 20251201_143022_PF_THEN_RH-Baseline/
    ├── workflow.pkl              # Komplettes Workflow-Objekt
    ├── metadata.json             # Metadaten (Name, Datum, Kosten, etc.)
    ├── pf_timeseries.csv         # Perfect Forecast Zeitreihen
    ├── rh_timeseries.csv         # Rolling Horizon Zeitreihen
    ├── design.json               # Anlagen-Design
    └── *.pdf, *.svg              # Exportierte Plots
```

## 🎯 Verwendung

### 1. Dashboard starten

```bash
python start_dashboard.py
```

### 2. Simulation auswählen

- Im Dashboard erscheint ein **Dropdown-Menü** mit allen verfügbaren Workflows
- Workflows sind nach Datum sortiert (neueste zuerst)
- Jeder Eintrag zeigt: Name, Datum, Szenario, Kosten

### 3. Ergebnisse analysieren

Navigiere durch die verschiedenen Tabs:

#### 📈 Übersicht (NEU: Erweiterte KPIs)
- **9 KPI-Cards** mit farbcodierten Metriken:
  - Gesamtkosten, Stromkosten, Brennstoffkosten, CAPEX
  - Wärmebedarf, Spitzenlast
  - **NEU: Thermische Autarkie** (Selbstversorgungsgrad in %)
  - **NEU: Auslastungsfaktor** (Durchschnittslast / Spitzenlast in %)
  - **NEU: Betriebsstunden** (Gesamtzahl der Zeitschritte)
- Workflow-Zusammenfassung
- Mini-Plot für Jahresverlauf

#### 📉 Zeitreihen (NEU: Quick-Filter)
- **Quick-Filter Buttons** für typische Zeitbereiche:
  - 🔹 **Erste Woche**: Zeigt die ersten 168 Stunden
  - 🔹 **Winter-Tag**: Springt zum Tag mit höchstem Wärmebedarf
  - 🔹 **Sommer-Tag**: Springt zum Tag mit niedrigstem Wärmebedarf
  - 🔹 **Ganzes Jahr**: Zeigt den kompletten Zeitraum
- **Aggregation-Optionen**: Stündlich, Täglich, Wöchentlich, Monatlich
- Komponenten-Multi-Select für thermische Erzeuger
- Drei Plot-Typen: Stacked Area, Lines, Stacked Bar
- Interaktive Features: Zoom, Pan, Hover-Details

#### 📊 Jahresdauerlinie (NEU)
- **Load Duration Curve** für Wärmebedarf und Erzeuger
- Sortierte Häufigkeitsverteilung der Lasten
- **Statistiken**:
  - Spitzenlast, Durchschnittslast
  - Auslastungsfaktor
  - Volllast-Stunden (>80% der Spitzenlast)
  - Gesamt-Betriebsstunden
- **Nutzen**: Essentiell für Dimensionierung und Identifikation von Grund- vs. Spitzenlast

#### ⚡ Effizienz & COP (NEU)
- **COP-Zeitverlauf** für alle Wärmepumpen
- **COP Box-Plot** mit statistischer Verteilung
- **Statistik-Tabelle** mit:
  - Durchschnitt, Minimum, Maximum, Median
  - Pro Wärmepumpe
- **Hinweis**: Benötigt COP-Daten in den Workflow-Ergebnissen

#### 🌊 Energieflüsse (NEU: Sankey-Diagramm)
- **Sankey-Diagramm** visualisiert Energieströme
- Flussbreite proportional zur übertragenen Energiemenge
- **Energie-Bilanz**:
  - Gesamt-Wärmebedarf, Gesamt-Erzeugung
  - Bilanz-Berechnung
- **Erzeugung nach Quelle** mit prozentualer Aufteilung

### 4. Weitere Tabs

#### 📈 Übersicht
- Wichtigste KPIs auf einen Blick
- Kosten-Summary
- System-Konfiguration
- Workflow-Informationen

#### 📉 Zeitreihen
- **Komponenten-Auswahl**: Multi-Select für thermische/elektrische Komponenten
- **Zeitbereich**: Slider zur Einschränkung des angezeigten Zeitraums
- **Plot-Typen**: Stacked Area, Line, Bar
- **Interaktive Features**: Zoom, Pan, Hover für Details

#### 💰 Kosten
- Detaillierte Kostenaufschlüsselung
- Sortierbare Tabellen
- Pie-Chart mit Visualisierung
- Aufschlüsselung nach OPEX/CAPEX

#### 🏭 Anlagen
- Installierte Komponenten und Kapazitäten
- Auslastungs-Statistiken
- Design-Übersicht als JSON
- Komponentenvergleich

## 🔧 Konfiguration

### Port ändern

```bash
# Standard: 5007
python start_dashboard.py --port 8080
```

### Eigenes Workflow-Verzeichnis

```bash
python start_dashboard.py --dir /path/to/my/workflows
```

### Titel anpassen

```bash
python start_dashboard.py --title "Mein Custom Dashboard"
```

## 🚀 Performance & Optimierungen

### Automatisches Downsampling

Das Dashboard erkennt automatisch große Datensätze (>20.000 Zeitschritte) und reduziert die Datenpunkte für bessere Performance:

```
⚠️  Performance-Hinweis:
   Datensatz wurde von 35,040 auf 17,520 Punkte reduziert (Faktor 2)
   Dies verbessert die Dashboard-Performance erheblich.
   Für detaillierte Analysen: Verwende die CSV-Exports aus saved_workflows/
```

**Vorteile:**
- Schnelleres Rendering der interaktiven Plots
- Flüssigeres Zoomen und Pan
- Geringerer Speicherverbrauch
- Vollständige Daten bleiben in CSV-Exporten verfügbar

### Best Practices

1. **Für große Datensätze (>10k Zeitschritte)**:
   - Nutze Quick-Filter zum Fokussieren auf interessante Bereiche
   - Verwende Aggregation (Täglich/Wöchentlich) für Jahresübersicht
   - CSV-Exports für detaillierte Offline-Analysen

2. **Für Präsentationen**:
   - Quick-Filter für typische Tage nutzen
   - Jahresdauerlinie für Dimensionierung zeigen
   - Sankey-Diagramm für intuitive Energiebilanzen

3. **Für Performance-Analysen**:
   - COP-Tab für Wärmepumpen-Effizienz
   - Autarkie-Metriken im Overview
   - Auslastungsfaktor für Betriebsoptimierung

## 🐛 Troubleshooting

### Dashboard startet nicht

**Problem:** `ImportError: Panel not installed`

**Lösung:**
```bash
pip install panel holoviews bokeh plotly
```

---

**Problem:** `No workflows found in saved_workflows/`

**Lösung:** Erstelle zuerst einen Workflow mit:
- `notebooks/runner.ipynb` oder
- `notebooks/scenario_studio.ipynb`

---

**Problem:** Port bereits belegt

**Lösung:**
```bash
python start_dashboard.py --port 5008
```

### Dashboard lädt nicht

**Problem:** "Failed to load workflow"

**Lösung:**
- Prüfe ob `workflow.pkl` in saved_workflows/ existiert
- Prüfe ob Datei korrekt gespeichert wurde (nicht korrupt)
- Prüfe Berechtigungen (Lese-Rechte)

---

**Problem:** Plots werden nicht angezeigt

**Lösung:**
- Stelle sicher, dass Plotly installiert ist: `pip install plotly`
- Prüfe Browser-Konsole auf JavaScript-Fehler
- Aktualisiere Browser (Chrome/Firefox empfohlen)

## 📚 Architektur

### Komponenten

```
start_dashboard.py
    ↓
energis/io/workflow_browser.py
    ↓
    ├── energis/io/dashboard.py       (Dashboard-Erstellung)
    ├── energis/io/notebook_helpers.py (Workflow-Laden)
    └── Panel/Plotly/Holoviews         (Visualisierung)
```

### Datenfluss

1. **Scannen**: `workflow_browser.py` scannt `saved_workflows/`
2. **Metadaten**: Lädt `metadata.json` für Preview
3. **Workflow-Auswahl**: User wählt Simulation
4. **Laden**: `notebook_helpers.load_workflow_from_saved()` lädt `workflow.pkl`
5. **Dashboard**: `dashboard.create_dashboard()` erstellt interaktive Tabs
6. **Anzeige**: Panel rendert im Browser

## 🛠️ Entwicklung

### Eigene Dashboard-Tabs hinzufügen

Editiere `energis/io/dashboard.py`:

```python
def create_custom_tab(workflow):
    """Erstelle einen Custom-Tab."""
    import panel as pn

    # Deine Visualisierung
    content = pn.pane.Markdown("# Custom Tab")

    return content

# In create_dashboard():
tabs.append(("Custom", create_custom_tab(workflow)))
```

### Dashboard als Service

Für Produktiv-Deployment:

```bash
# Mit Auto-Reload deaktiviert
panel serve start_dashboard.py --show --autoreload=False

# Als Service
nohup panel serve start_dashboard.py --port 5007 &
```

## 📖 Weitere Ressourcen

- **Panel Docs**: https://panel.holoviz.org/
- **Plotly Docs**: https://plotly.com/python/
- **EnerGIS Docs**: `README.md`, `ARCHITECTURE_V2.md`

## 🎓 Best Practices

### Workflow-Organisation

```
saved_workflows/
├── baseline_runs/           # Standard-Konfigurationen
├── sensitivity_studies/     # Sensitivitätsanalysen
└── production_scenarios/    # Produktions-Szenarien
```

Nutze `--dir` um verschiedene Verzeichnisse zu durchsuchen.

### Performance

- Das Dashboard lädt Workflows on-demand (nicht beim Start)
- CSV-Dateien werden lazy geladen
- Große Datensätze (>100k Zeilen) werden automatisch downsampled

### Export

Nutze die Export-Funktionen in den Notebooks:
- **CSV**: Automatisch in `saved_workflows/`
- **PDF/SVG**: Hochwertige Plots für Publikationen
- **JSON**: Metadaten und Design-Spezifikation

---

**Happy Analyzing! 🎉**
