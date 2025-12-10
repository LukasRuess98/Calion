# Dashboard Integration - Thermisches Netzwerk

## ✅ Integration abgeschlossen

Das thermische Netzwerk ist vollständig in das interaktive Dashboard (`workflow_browser.ipynb`) integriert.

---

## 🎯 Features

### Neuer Tab: "🌡️ Thermisches Netzwerk"

Der Dashboard-Tab wird **automatisch angezeigt**, wenn ein Workflow thermische Netzwerkdaten enthält.

**Inhalt:**

1. **Key Performance Indicators (KPIs)**
   - Wärme geliefert [MWh]
   - Wärmeverluste [MWh] und Verlustrate [%]
   - Netzeffizienz [%] mit Bewertung (🟢 Exzellent / 🟡 Gut / 🔴 Optimierung empfohlen)
   - Netzwerk-Topologie (Anzahl Knoten & Rohrleitungen)

2. **Temperaturprofile**
   - Interaktive Plotly-Grafik
   - Vorlauf- und Rücklauftemperaturen für alle Netzknoten
   - Zeitlicher Verlauf mit Hover-Informationen

3. **Wärmeverluste pro Rohrleitung**
   - Gestackte Darstellung aller Rohrverluste
   - Identifikation der verlustreichsten Rohre

4. **Massenströme**
   - Alle Rohrleitungsströme im zeitlichen Verlauf
   - Visualisierung von Lastverteilungen

5. **Statistik-Zusammenfassung**
   - Gesamt-KPIs (Wärme, Verluste, Effizienz)
   - Temperatur-Statistiken pro Knoten (Min/Max/Mittelwert)
   - Top 5 verlustreichste Rohrleitungen

---

## 🚀 Verwendung

### Im Workflow Browser

```python
# In notebooks/workflow_browser.ipynb
from energis.io.workflow_browser import create_workflow_browser

browser = create_workflow_browser(saved_workflows_dir="saved_workflows")
browser
```

1. Wähle eine Simulation mit thermischem Netzwerk aus dem Dropdown
2. Der Tab "🌡️ Thermisches Netzwerk" erscheint automatisch
3. Erkunde KPIs, Temperaturprofile, Verluste und Statistiken

---

### Direkt im Dashboard

```python
from energis.workflows.run_workflow import run_workflow
from energis.io.dashboard import create_dashboard

# Optimierung mit Netzwerk durchführen
workflow = run_workflow(
    scenario_config_path='configs/scenarios/stadtbach_1week.scenario.yaml',
    save=True
)

# Dashboard erstellen
dashboard = create_dashboard(workflow)
dashboard
```

---

## 🔍 Automatische Erkennung

Das Dashboard erkennt automatisch, ob thermische Netzwerkdaten verfügbar sind:

```python
# In energis/io/dashboard.py (Zeile ~420-428)

# Identify thermal network components
self.network_node_cols = [col for col in self.df.columns if col.startswith('NET_') and '_T_supply' in col]
self.network_pipe_cols = [col for col in self.df.columns if col.startswith('NET_') and '_flow_kg_s' in col]
self.has_thermal_network = len(self.network_node_cols) > 0 or len(self.network_pipe_cols) > 0

# Extract thermal network summary if available
self.network_summary = {}
if hasattr(result, 'summary') and result.summary and 'thermal_network' in result.summary:
    self.network_summary = result.summary['thermal_network']
```

**Der Tab wird nur angezeigt, wenn:**
- `thermal_network.enabled: true` in der Szenario-Konfiguration
- Netzwerk-Zeitreihen (`NET_*`) in `result.series` vorhanden sind
- ODER Netzwerk-Summary in `result.summary['thermal_network']` vorhanden ist

---

## 📊 Datenquellen

### Zeitreihen (aus `result.series`)

**Knoten (Nodes):**
- `NET_{node_id}_T_supply_C` - Vorlauftemperatur [°C]
- `NET_{node_id}_T_return_C` - Rücklauftemperatur [°C]
- `NET_{node_id}_Q_demand_kW` - Wärmebedarf [kW]

**Rohrleitungen (Pipes):**
- `NET_{pipe_id}_flow_kg_s` - Massenstrom [kg/s]
- `NET_{pipe_id}_T_supply_C` - Vorlauftemperatur [°C]
- `NET_{pipe_id}_T_return_C` - Rücklauftemperatur [°C]
- `NET_{pipe_id}_Q_loss_kW` - Wärmeverlust [kW]

### Summary (aus `result.summary['thermal_network']`)

```python
{
    'Total_heat_delivered_MWh': 120.5,
    'Total_heat_losses_MWh': 0.8,
    'Loss_percentage': 0.66,
    'Avg_supply_temp_C': 75.2,
    'Avg_return_temp_C': 45.8,
    'Number_of_nodes': 12,
    'Number_of_pipes': 11
}
```

---

## 🎨 Visualisierungen

### 1. KPI-Karten

Farbcodierte Karten mit:
- 🟢 Grün: Wärme geliefert, Netzeffizienz
- 🟡/🔴: Wärmeverluste (abhängig von Verlustrate)
- 🟣 Lila: Topologie-Informationen

### 2. Temperaturprofile

- **Vorlauf**: Durchgezogene Linien, kräftige Farben
- **Rücklauf**: Gestrichelte Linien, gleiche Farbkodierung
- **Interaktiv**: Hover zeigt exakte Werte
- **Legende**: Rechts neben dem Graphen

### 3. Wärmeverluste (Stacked Area)

- Gestackte Darstellung für einfache Identifikation dominanter Verlustquellen
- Summe aller Verluste sichtbar
- Farbcodierung pro Rohrleitung

### 4. Massenströme (Line Chart)

- Alle Rohre in einer Grafik
- Identifikation von Haupt-Transportstrecken
- Lastverteilung über Zeit sichtbar

---

## ⚙️ Konfiguration

### Effizienz-Bewertung anpassen

In `energis/io/dashboard.py`, Zeile ~2841-2849:

```python
# Efficiency rating
if loss_percent < 0.5:
    rating = "🟢 Exzellent"
    color = '#c8e6c9'
elif loss_percent < 1.5:
    rating = "🟡 Gut"
    color = '#fff9c4'
else:
    rating = "🔴 Optimierung empfohlen"
    color = '#ffcdd2'
```

**Empfohlene Grenzwerte:**
- **< 0.5%**: Exzellente Effizienz (typisch für moderne, gut isolierte Netze)
- **0.5 - 1.5%**: Gute Effizienz (Standard bei Fernwärmenetzen)
- **> 1.5%**: Optimierungsbedarf (alte Rohrleitungen, schlechte Isolation)

---

## 🧪 Test-Beispiel: Stadtbach

```bash
# 1. Synthetische Daten generieren (bereits vorhanden)
python scripts/generate_stadtbach_synthetic_data.py

# 2. Optimierung mit Netzwerk durchführen
# In runner.ipynb oder Python:
from energis.workflows.run_workflow import run_workflow

workflow = run_workflow(
    scenario_config_path='configs/scenarios/stadtbach_1week.scenario.yaml',
    save=True,
    display=True
)

# 3. Dashboard öffnen
from energis.io.dashboard import create_dashboard
dashboard = create_dashboard(workflow)
dashboard

# Oder: Workflow Browser verwenden
from energis.io.workflow_browser import create_workflow_browser
browser = create_workflow_browser()
browser
```

**Erwartete Ergebnisse (Stadtbach 1 Woche, synthetisch):**
- Wärme geliefert: ~120 MWh
- Wärmeverluste: ~0.8 MWh (0.66%)
- Bewertung: 🟢 Exzellent
- Vorlauf: ~75°C, Rücklauf: ~45°C

---

## 📁 Relevante Dateien

### Dashboard-Integration
- `energis/io/dashboard.py` (Zeile 420-428, 597-598, 2798-3048)
  - `_prepare_data()`: Netzwerk-Komponenten identifizieren
  - `create()`: Tab hinzufügen
  - `_create_thermal_network_tab()`: Tab-Inhalt erstellen

### Workflow Browser
- `energis/io/workflow_browser.py` (Zeile 404-415)
  - Lädt Dashboard automatisch, inkl. Netzwerk-Tab

### Netzwerk-Ergebnisse
- `energis/run/rolling_horizon.py` (Zeile 1118-1196, 2430-2463)
  - Extrahiert Netzwerk-Zeitreihen (`NET_*` prefix)
  - Erstellt Netzwerk-Summary

---

## 🆘 Troubleshooting

### Tab wird nicht angezeigt

**Ursache 1:** Netzwerk nicht aktiviert
```yaml
# In scenario.yaml
thermal_network:
  enabled: true  # Muss true sein!
  topology_file: stadtbach_network.yaml
```

**Ursache 2:** Keine Netzwerkdaten in Ergebnissen
```python
# Prüfen
result = workflow.rh_result or workflow.pf_result
print("Network series:", [k for k in result.series.keys() if k.startswith('NET_')])
print("Network summary:", result.summary.get('thermal_network', 'MISSING'))
```

---

### Leere Grafiken / Keine Daten

**Ursache:** Optimierung fehlgeschlagen oder Solver-Fehler

**Lösung:**
1. Prüfe Solver-Log auf Fehler
2. Stelle sicher, dass Gurobi installiert ist (MIQP erforderlich!)
3. Validiere Netzwerk-Topologie (`stadtbach_network.yaml`)

```python
# Optimierungsstatus prüfen
workflow = run_workflow(...)
print("PF success:", workflow.pf_result is not None)
print("RH success:", workflow.rh_result is not None)
```

---

### Dashboard lädt sehr lange

**Ursache:** Zu viele Datenpunkte (> 20.000)

**Automatisches Downsampling** ist bereits implementiert (dashboard.py, Zeile 387-412):
- Bei > 20.000 Zeitschritten wird automatisch downsampled
- KPIs werden auf Originaldaten berechnet (korrekt!)
- Plots verwenden downsampled Daten (Performance)

**Hinweis:** Für detaillierte Analysen nutzen Sie die CSV-Exports:
```bash
saved_workflows/YOUR_SIMULATION/pf_network_timeseries.csv
saved_workflows/YOUR_SIMULATION/pf_network_summary.csv
```

---

## 📌 Nächste Schritte

1. **Echte Daten integrieren**
   - Siehe: `docs/STADTBACH_REAL_DATA_REQUIREMENTS.md`
   - Ersetze `stadtbach_synthetic_2023_1week.csv` durch echte Betriebsdaten

2. **Netzwerk-Topologie verfeinern**
   - Füge weitere Knoten/Rohre hinzu in `configs/topology/stadtbach_network.yaml`
   - Passe Rohrlängen und U-Werte an echte Daten an

3. **Optimierung erweitern**
   - Teste Rolling Horizon für lange Zeiträume (1 Jahr)
   - Integriere zusätzliche Wärmequellen (Solarthermie, BHKW)

---

**Letzte Aktualisierung**: 2025-12-10
**Version**: 1.0
**Status**: ✅ Vollständig integriert und getestet
