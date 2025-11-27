# 🎛️ EnerGIS Interactive Dashboard

Vollständiges interaktives Dashboard für die Analyse von EnerGIS Optimierungsergebnissen.

## 🎯 Features

### **Tab 1: 📊 Overview**
- **KPI-Cards**: Farbcodierte Kennzahlen (Kosten, CAPEX, Wärmebedarf, Spitzenlast)
- **Zusammenfassung**: Workflow-Info, aktive Komponenten, Zeitraum
- **Mini-Plot**: Jahresverlauf Wärmebedarf als Übersicht

### **Tab 2: 📈 Zeitreihen (INTERAKTIV)**
- **Komponenten-Auswahl**: Multi-Select für thermische Erzeuger
- **Zeitbereich-Slider**: Dynamische Zeitfenster-Selektion (Stunde bis Jahr)
- **Plot-Typen**: Stacked Area, Lines, Stacked Bar
- **Wärmebilanz**: Interaktiv mit Zoom, Pan, Hover-Details
- **Elektrische Bilanz**: Netzbezug, Einspeisung, Verbraucher
- **Speicher-Operation**: SOC, Beladung, Entladung (dual y-axis)

### **Tab 3: 💰 Kosten**
- **Breakdown-Chart**: Top-10 Kostenblöcke als horizontales Balkendiagramm
- **Interaktive Tabelle**: Sortierbar, filterbar, formatiert
  - Kosten in EUR (mit Tausender-Trennung)
  - Prozentuale Anteile (mit Progress-Bar)
- **Zusammenfassung**: Top-3 Kostenblöcke, Gesamtkosten

### **Tab 4: 🏭 Anlagen-Design**
- **Kapazitäts-Plot**: Balkendiagramm für WP und Speicher
- **Design-Tabelle**: Übersicht alle Komponenten
- **JSON-Export**: Vollständige Design-Daten

### **Tab 5: 🔀 Vergleich** (nur bei PF+RH/MPC)
- **Cost-Comparison**: PF vs RH/MPC Balkendiagramm
- **Optimality Gap**: Automatische Berechnung und Interpretation
- **Empfehlungen**: Basierend auf Gap-Größe

---

## 🚀 Quick Start

### Installation

```bash
# Erforderliche Dependencies
pip install panel holoviews bokeh plotly

# Optional für erweiterte Features
pip install jupyter-bokeh jupyterlab
```

### Verwendung im Notebook

```python
from energis.run import rolling_horizon as rh
from energis.io.dashboard import create_dashboard

# 1. Workflow ausführen
workflow = rh.run_workflow(CONFIG_PATHS)

# 2. Dashboard erstellen
dashboard = create_dashboard(workflow, title="Mein Dashboard")

# 3. In Jupyter anzeigen
dashboard  # Oder: dashboard.show()
```

### Als Webapp starten

```bash
# Starte Dashboard-Server
panel serve notebooks/interactive_dashboard.ipynb --show

# Custom Port
panel serve notebooks/interactive_dashboard.ipynb --port 5007

# Externe Verbindungen erlauben
panel serve notebooks/interactive_dashboard.ipynb --address 0.0.0.0
```

---

## 📸 Screenshots

### Tab 1: Overview
```
┌─────────────────────────────────────────────────────────────┐
│  EnerGIS Interactive Dashboard 🔥                           │
│  Workflow: PF → RH  |  Zeitschritte: 8,760                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 💰 Gesamt    │  │ ⚡ Strom     │  │ 🔥 Brennstoff│     │
│  │ 1,234,567 €  │  │  345,678 €   │  │  123,456 €   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 🏗️ CAPEX    │  │ 📊 Bedarf    │  │ 🔝 Spitze    │     │
│  │  456,789 €   │  │ 45,678 MWh   │  │  12.3 MW     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  📋 Zusammenfassung         📊 Wärmebedarf                  │
│  ┌─────────────────────┐   ┌──────────────────────┐        │
│  │ Zeitraum: 2023      │   │                      │        │
│  │ Schritte: 8,760     │   │  [Jahresdauerlinie]  │        │
│  │ WP: 4 | Gen: 2      │   │                      │        │
│  │ Speicher: Ja        │   │                      │        │
│  └─────────────────────┘   └──────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Tab 2: Zeitreihen (INTERAKTIV!)
```
┌─────────────────────────────────────────────────────────────┐
│  ⚙️ Steuerung                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🔥 Thermische Komponenten                           │   │
│  │  ☑ HP1    ☑ HP2    ☑ HP3    ☐ HKW    ☐ BMHKW      │   │
│  │                                                      │   │
│  │ 📅 Zeitbereich (Stunden)                            │   │
│  │  [====|=====================>              ] 0-168  │   │
│  │                                                      │   │
│  │ Plot-Typ: [Stacked Area ▼]                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  🔥 Wärmebilanz                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 15 MW │                    /\                        │   │
│  │       │                   /  \         /\           │   │
│  │ 10 MW │    /\            |    |       /  \          │   │
│  │       │   |  |          |      |     |    |         │   │
│  │  5 MW │  |    |        |        |   |      |        │   │
│  │       │ |      |      |          | |        |       │   │
│  │  0 MW └─┴──────┴─────┴───────────┴──────────┴──>   │   │
│  │        Jan   Feb   Mar   Apr   Mai   Jun   Jul     │   │
│  │                                                      │   │
│  │  Legend: ▬ HP1  ▬ HP2  ▬ HP3  -- Bedarf            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ⚡ Elektrische Bilanz                                      │
│  [Ähnlicher Plot für elektrische Leistung]                  │
│                                                              │
│  🔋 Thermischer Speicher                                    │
│  [SOC + Charge/Discharge Plot mit dual y-axis]              │
└─────────────────────────────────────────────────────────────┘
```

### Tab 3: Kosten
```
┌─────────────────────────────────────────────────────────────┐
│  📊 Kostenaufteilung               📋 Zusammenfassung       │
│  ┌───────────────────────────┐    ┌─────────────────────┐  │
│  │ Electricity Base      ████│    │ Gesamtkosten:       │  │
│  │                    456,789│    │   1,234,567 €       │  │
│  │ Grid Fee          ███     │    │                     │  │
│  │                    234,567│    │ Top 3:              │  │
│  │ Fuel Cost        ██       │    │  1. Elec: 456,789 € │  │
│  │                    123,456│    │  2. Grid: 234,567 € │  │
│  │ Demand Charge    █        │    │  3. Fuel: 123,456 € │  │
│  │                     89,012│    │                     │  │
│  └───────────────────────────┘    └─────────────────────┘  │
│                                                              │
│  📄 Detaillierte Kostentabelle                              │
│  ┌────────────────────┬──────────────┬────────────┐        │
│  │ Category           │ Value [EUR]  │ Percentage │        │
│  ├────────────────────┼──────────────┼────────────┤        │
│  │ Electricity Base   │   456,789.00 │ ████ 37%   │  ◀─ Sortierbar!
│  │ Grid Fee           │   234,567.00 │ ███  19%   │        │
│  │ Fuel Cost Natural  │   123,456.00 │ ██   10%   │        │
│  │ Demand Charge      │    89,012.00 │ █     7%   │        │
│  │ ...                │          ... │        ... │        │
│  └────────────────────┴──────────────┴────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Tab 4: Anlagen-Design
```
┌─────────────────────────────────────────────────────────────┐
│  🏭 Anlagenauslegung                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │     HP1    HP2    HP3    HP4     TES                │   │
│  │ 15 │  █      █      █      █       █                │   │
│  │ MW │  █      █      █      █       █                │   │
│  │ 10 │  █      █      █      █       █                │   │
│  │    │  █      █      █      █       █                │   │
│  │  5 │  █      █      █      █       █                │   │
│  │    └─────────────────────────────────────>          │   │
│  │      3.5MW  2.8MW  4.2MW  1.5MW  50MWh              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  📋 Kapazitätstabelle                                       │
│  ┌────────────────────┬──────────────┬──────────┐          │
│  │ Komponente         │ Kapazität    │ Typ      │          │
│  ├────────────────────┼──────────────┼──────────┤          │
│  │ HP1                │      3.50 MW │ WP       │          │
│  │ HP2                │      2.80 MW │ WP       │          │
│  │ HP3                │      4.20 MW │ WP       │          │
│  │ HP4                │      1.50 MW │ WP       │          │
│  │ TES                │     50.00 MW │ Speicher │          │
│  └────────────────────┴──────────────┴──────────┘          │
│                                                              │
│  📄 Design-Details (JSON)                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ {                                                    │   │
│  │   "heat_pumps": {                                    │   │
│  │     "HP1": {"capacity_mw": 3.5, ...},                │   │
│  │     "HP2": {"capacity_mw": 2.8, ...}                 │   │
│  │   },                                                 │   │
│  │   "storage": {"capacity_mwh": 50.0}                  │   │
│  │ }                                                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Tab 5: Vergleich
```
┌─────────────────────────────────────────────────────────────┐
│  🔀 PF vs RH Vergleich                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Kostenvergleich                              │   │
│  │ 1.5M │                                               │   │
│  │  €   │       █                  █                    │   │
│  │ 1.0M │       █                  █                    │   │
│  │      │       █                  █                    │   │
│  │ 0.5M │       █                  █                    │   │
│  │      └───────█──────────────────█────────>          │   │
│  │              PF               RH                     │   │
│  │        1,234,567 €       1,289,456 €                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  📊 Kennzahlen                                              │
│  ┌────────────────────┬──────────────┬──────────────┐      │
│  │ Metrik             │ PF           │ RH           │      │
│  ├────────────────────┼──────────────┼──────────────┤      │
│  │ Gesamtkosten       │ 1,234,567 €  │ 1,289,456 €  │      │
│  │ Optimality Gap     │ -            │ 4.45 %       │      │
│  └────────────────────┴──────────────┴──────────────┘      │
│                                                              │
│  💡 Interpretation                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ✅ Gut: Gap < 5% - akzeptable operative Planung    │   │
│  │                                                      │   │
│  │  Der Rolling Horizon erreicht eine gute Näherung    │   │
│  │  an die optimale PF-Lösung. Die Abweichung von      │   │
│  │  4.45% liegt im akzeptablen Bereich.                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 Interaktive Features

### **Alle Plots unterstützen:**
- 🔍 **Zoom**: Box-Select oder Scroll-Zoom
- 🖱️ **Pan**: Drag zum Verschieben
- ℹ️ **Hover**: Detaillierte Werte beim Mouse-Over
- 📸 **Screenshot**: Download als PNG
- 🔄 **Reset**: Zurück zur Originalansicht
- 📊 **Legend-Click**: Ein/Ausblenden von Serien

### **Zeitreihen-Tab zusätzlich:**
- ✅ **Multi-Select**: Mehrere Komponenten gleichzeitig
- 📅 **Range-Slider**: Dynamische Zeitfenster-Auswahl
- 🎨 **Plot-Type-Switch**: Umschalten zwischen Visualisierungen

### **Kosten-Tab zusätzlich:**
- 🔀 **Sortierung**: Klick auf Spaltenköpfe
- 🔍 **Suche**: Filter in Tabulator
- 📋 **Copy**: Daten in Zwischenablage

---

## 🌐 Als Webapp deployen

### Lokal (Entwicklung)
```bash
panel serve notebooks/interactive_dashboard.ipynb --show
```

### Production (z.B. mit Docker)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

EXPOSE 5006

CMD ["panel", "serve", "notebooks/interactive_dashboard.ipynb", \
     "--address", "0.0.0.0", "--port", "5006", "--allow-websocket-origin=*"]
```

```bash
docker build -t energis-dashboard .
docker run -p 5006:5006 energis-dashboard
```

### Cloud Deployment

#### **Heroku**
```bash
# Procfile
web: panel serve notebooks/interactive_dashboard.ipynb --port=$PORT --address=0.0.0.0 --allow-websocket-origin=*
```

#### **AWS / Azure / GCP**
- Nutze Container-Services (ECS, Container Apps, Cloud Run)
- Oder: VM mit Panel Server

---

## 🔧 Anpassungen

### Eigene Plots hinzufügen

```python
# In energis/io/dashboard.py

def _create_custom_plot(self):
    """Eigener Plot."""

    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    fig = go.Figure()

    # Dein Plot-Code hier
    fig.add_trace(...)

    fig.update_layout(...)

    return pn.pane.Plotly(fig, sizing_mode='stretch_width')

# Dann in create():
tabs.append(('🎨 Custom', self._create_custom_plot()))
```

### Eigene KPI-Cards

```python
# In _create_kpi_cards()
custom_kpi = self._create_kpi_card(
    "🔥 Meine KPI",
    "1,234",
    "success"
)
```

### Eigene Farbschemata

```python
# In _get_component_color()
color_map = {
    'HP1': '#YOUR_COLOR',
    # ...
}
```

---

## 📚 API-Referenz

### `create_dashboard(workflow, title)`
**Parameter:**
- `workflow`: WorkflowResult von `run_workflow()`
- `title`: str, Dashboard-Titel (optional)

**Returns:** `pn.Tabs` - Panel Dashboard

### `EnerGISDashboard` Klasse
Hauptklasse für Dashboard-Erstellung.

**Attribute:**
- `workflow`: WorkflowResult
- `df`: pandas.DataFrame mit Zeitreihen
- `costs_df`: pandas.DataFrame mit Kosten
- `has_pf`, `has_rh`, `has_mpc`: bool Flags

**Methoden:**
- `create()`: Erstellt vollständiges Dashboard
- `_create_overview_tab()`: Overview-Tab
- `_create_timeseries_tab()`: Zeitreihen-Tab
- `_create_costs_tab()`: Kosten-Tab
- `_create_design_tab()`: Design-Tab
- `_create_comparison_tab()`: Vergleichs-Tab

---

## 🐛 Troubleshooting

### Problem: Dashboard wird nicht angezeigt
**Lösung:**
```bash
# In JupyterLab:
jupyter labextension install @pyviz/jupyterlab_pyviz

# Kernel neu starten
```

### Problem: Plots sind leer
**Lösung:**
- Überprüfe `workflow.pf_result` oder `workflow.rh_result`
- Prüfe ob Optimierung erfolgreich war
- Schaue in die Logs

### Problem: "Panel not found"
**Lösung:**
```bash
pip install panel holoviews bokeh plotly
```

### Problem: Webapp startet nicht
**Lösung:**
```bash
# Prüfe ob Port frei ist
lsof -i :5006

# Nutze anderen Port
panel serve ... --port 5007
```

---

## 🎓 Best Practices

1. **Performance**: Für große Datensätze (>100k Zeitschritte):
   - Nutze `head_limit` und `offset` in Zeitreihen-Tab
   - Aggregiere Daten vorab (z.B. stündlich → täglich)

2. **Responsiveness**: Dashboard für verschiedene Bildschirmgrößen:
   - Nutze `sizing_mode='stretch_width'`
   - Teste auf Tablet/Mobile

3. **Export**: Für Präsentationen:
   - Nutze Plotly's `fig.write_image()` für statische Exports
   - Oder: Screenshot-Tool im Dashboard

4. **Sicherheit**: Für öffentliches Deployment:
   - Aktiviere Authentication (z.B. mit `panel.io.server`)
   - Nutze HTTPS
   - Rate-Limiting implementieren

---

## 📊 Vergleich: Dashboard vs. Statische Plots

| Feature | Statische Plots | Dashboard |
|---------|----------------|-----------|
| **Interaktivität** | ❌ Keine | ✅ Voll interaktiv |
| **Komponenten-Auswahl** | ❌ Fixiert | ✅ Multi-Select |
| **Zeitbereich** | ❌ Fixiert | ✅ Dynamischer Slider |
| **Zoom/Pan** | ❌ Nein | ✅ Ja |
| **Tabellen** | ❌ Statisch | ✅ Sortierbar, filterbar |
| **Export** | ✅ PDF/SVG | ✅ PNG + HTML |
| **Webapp** | ❌ Nein | ✅ Ja |
| **Komplexität** | 🟢 Niedrig | 🟡 Mittel |
| **Dependencies** | matplotlib | panel, plotly, bokeh |

---

## 🚀 Roadmap

### Geplante Features
- [ ] Vergleich mehrerer Szenarien (Side-by-Side)
- [ ] CSV-Download aus Dashboard
- [ ] Automatische Reports (PDF-Generation)
- [ ] Dark Mode
- [ ] Custom Themes
- [ ] Mobile-optimierte Ansicht
- [ ] Real-time Updates (für MPC)
- [ ] Authentication & User Management
- [ ] Multi-User Support

---

## 🤝 Contributing

Verbesserungsvorschläge und Pull Requests willkommen!

**Besonders gesucht:**
- Neue Plot-Typen
- Performance-Optimierungen
- Mobile UI/UX Verbesserungen
- Dokumentation

---

## 📄 Lizenz

Siehe `../LICENSE`

---

**Viel Erfolg mit dem Dashboard! 🎉**
