# 🚀 Thermal Network - Schnellstart-Anleitung

**Datum**: 2025-12-10
**Status**: Production-Ready ✅
**Zielgruppe**: Entwickler und Anwender

---

## ✅ Was ist bereits fertig

Das thermische Netzwerk ist **vollständig integriert**:

- ✅ Core MIQP-Modell (Temperatur-abhängige Verluste, bilineare Terme)
- ✅ Alle Workflows (PF, RH, MPC)
- ✅ CLI Runner (`python -m energis.run`)
- ✅ Jupyter Notebooks mit Visualisierung
- ✅ Automatische CSV/JSON Exports
- ✅ Stadtbach-Netzwerk konfiguriert (12 Knoten, 11 Rohre)

---

## 🎯 3 Wege zum Loslegen

### **Option 1: Jupyter Notebook (Empfohlen)** 🎨

Öffne `notebooks/runner.ipynb` und ändere Zelle 5:

```python
CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/systems/test_simple_with_network.system.yaml',  # Hat thermal_network bereits
]
```

**Wichtig**: Passe die Demand-Daten an oder nutze ein kleineres Zeitfenster:
```python
OVERRIDES = {
    'scenario': {
        'horizon': {
            'start': '2023-01-01 00:00',
            'end': '2023-01-01 06:00'  # Nur 6 Stunden für Schnelltest
        }
    }
}
```

Dann: **Run All** → Sektion 7 zeigt Network Results! 🎉

---

### **Option 2: Command Line Interface** 💻

```bash
# Erstelle custom scenario mit kleinerer Demand
python -c "
import yaml

config = {
    'scenario': {
        'run_mode': 'PF_ONLY',
        'title': 'Thermal Network Demo',
        'horizon': {
            'type': 'date_range',
            'start': '2023-01-01 00:00',
            'end': '2023-01-01 06:00'  # 6h test
        }
    },
    'system_file': 'test_simple_with_network.system.yaml',
    'run': {'dt_h': 1.0, 'solver': 'gurobi'}
}

with open('configs/scenarios/demo_6h.scenario.yaml', 'w') as f:
    yaml.dump(config, f)
"

# Run
python -m energis.run \
  configs/base.yaml \
  configs/tech_catalog.yaml \
  configs/scenarios/demo_6h.scenario.yaml
```

**Ergebnis**:
```
exports/20251210_123456_thermal-network-demo/
├── pf_network_timeseries.csv    # ⭐ Network time series
├── pf_network_summary.csv       # ⭐ Network KPIs
└── ...
```

---

### **Option 3: Direkt mit echten Stadtbach-Daten** 🏭

**Voraussetzung**: Echte Demand-Daten in `data/stadtbach_input_2023.xlsx`

```bash
# Siehe: docs/STADTBACH_REAL_DATA_OPTIMIZATION.md
python scripts/prepare_stadtbach_data.py  # Daten vorbereiten

# Run 1 Woche
python -m energis.run \
  configs/base.yaml \
  configs/tech_catalog.yaml \
  configs/scenarios/stadtbach_1week.scenario.yaml
```

**Erwartung**:
- Runtime: ~5-30 Sekunden (je nach Netzgröße)
- Output: 12 Knoten, 11 Rohre
- Verluste: ~0.5-0.8%

---

## 📊 Export-Struktur

Jeder Lauf mit `thermal_network.enabled: true` erstellt:

```
exports/20251210_183045_stadtbach-1week/
│
├── pf_timeseries.csv                    # Alle Optimierungs-Variablen
│   ├─ P_buy_MW, Q_dump_MWth, HP1_Q_th_MW, ...
│
├── pf_network_timeseries.csv            # ⭐ THERMAL NETWORK TIME SERIES
│   ├─ NET_plant_test_T_supply_C         # Vorlauftemperatur Knoten
│   ├─ NET_plant_test_T_return_C         # Rücklauftemperatur Knoten
│   ├─ NET_consumer_test_Q_demand_MW     # Wärmebedarf Knoten
│   ├─ NET_pipe_test_flow_kg_s           # Massenstrom Rohr
│   ├─ NET_pipe_test_T_supply_in_C       # Vorlauf Eintritt
│   ├─ NET_pipe_test_T_supply_out_C      # Vorlauf Austritt
│   ├─ NET_pipe_test_Q_loss_supply_kW    # Vorlauf-Verluste
│   └─ NET_pipe_test_Q_loss_return_kW    # Rücklauf-Verluste
│
├── pf_network_summary.csv               # ⭐ NETWORK KPIs
│   ├─ Total_heat_delivered_MWh          # Gesamte Lieferung
│   ├─ Total_heat_loss_MWh               # Gesamtverluste
│   ├─ Heat_loss_percentage              # Verlustrate [%]
│   ├─ Total_pipe_length_m               # Netzlänge
│   ├─ Number_of_nodes                   # Anzahl Knoten
│   └─ Number_of_pipes                   # Anzahl Rohre
│
├── design.json                          # Heat Pump Dimensionierung
└── manifest.json                        # Run Metadata
```

---

## 📈 Notebooks für Analyse

### **runner.ipynb** - Haupt-Workflow
- Sektion 7: Automatische Network Results Anzeige
- Interaktive Plotly-Charts
- Efficiency Rating

### **thermal_network_analysis.ipynb** - Detaillierte Analyse
```jupyter
# Öffne notebook
jupyter notebook notebooks/thermal_network_analysis.ipynb

# Oder in Jupyter Lab
jupyter lab notebooks/thermal_network_analysis.ipynb
```

**Features**:
- Lädt automatisch neueste Ergebnisse
- Temperaturprofile aller Knoten
- Verluste pro Rohrleitung
- Durchfluss-Statistiken
- Export als TXT-Report

---

## 🔧 Troubleshooting

### Problem 1: "Thermische Maximalleistung zu gering"

**Ursache**: Standard-Testdaten haben zu hohen Demand für kleine Netze

**Lösung A - Kleinerer Zeitraum**:
```yaml
# In scenario.yaml
scenario:
  horizon:
    start: "2023-01-01 00:00"
    end: "2023-01-01 06:00"  # Nur 6 Stunden statt 7 Tage
```

**Lösung B - Höhere Kapazität**:
```yaml
# In system.yaml
system:
  heat_pump_defaults:
    max_th_mw: 100.0  # Erhöhen von 50 auf 100 MW
```

**Lösung C - Investment aktivieren**:
```yaml
system:
  heat_pump_defaults:
    investment:
      enabled: true
      capacity_max_mw: 200.0
```

### Problem 2: "Model contains nonlinear terms"

**Ursache**: CBC/GLPK können MIQP nicht lösen

**Lösung**: Gurobi nutzen (kommerziell, ~10k€/Jahr)
```yaml
run:
  solver: gurobi  # Nicht cbc oder glpk!
```

**Hintergrund**: Bilineare Terme `m_dot * (T_in - T_out)` erfordern MIQP-Solver
**Siehe**: `docs/THERMAL_NETWORK_SOLVER_REQUIREMENTS.md`

### Problem 3: Keine Network Results in Exports

**Check 1**: Ist thermal_network aktiviert?
```yaml
# In system.yaml oder scenario.yaml
thermal_network:
  enabled: true  # ← Muss true sein!
  topology_file: networks/test_simple_network.yaml
```

**Check 2**: Wurde Gurobi genutzt?
```bash
# In Output suchen nach:
grep "Solving with gurobi" /tmp/test_output.log
```

**Check 3**: Export-Verzeichnis checken
```bash
ls -lh exports/$(ls -t exports/ | head -1)/
# Sollte pf_network_*.csv enthalten
```

---

## 🎨 Visualisierung in Notebooks

### Temperaturprofile visualisieren:

```python
import pandas as pd
import plotly.graph_objects as go

# Load network results
df = pd.read_csv('exports/.../pf_network_timeseries.csv',
                 index_col=0, parse_dates=True)

# Plot temperatures
fig = go.Figure()
for col in df.columns:
    if '_T_supply_C' in col:
        node = col.replace('NET_', '').replace('_T_supply_C', '')
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=node))

fig.update_layout(title="Supply Temperatures",
                  yaxis_title="Temperature [°C]")
fig.show()
```

### Verluste analysieren:

```python
# Load summary
summary = pd.read_csv('exports/.../pf_network_summary.csv',
                      index_col=0, squeeze=True).to_dict()

print(f"Heat Loss: {summary['Total_heat_loss_MWh']:.1f} MWh")
print(f"Loss Rate: {summary['Heat_loss_percentage']:.2f}%")

# Efficiency rating
if summary['Heat_loss_percentage'] < 0.5:
    print("⭐⭐⭐ Excellent!")
elif summary['Heat_loss_percentage'] < 1.5:
    print("✅ Good - typical for modern DH networks")
else:
    print("⚠️ High losses - check insulation")
```

---

## 📚 Weitere Dokumentation

| Dokument | Zweck |
|----------|-------|
| `THERMAL_NETWORK_FINAL_STATUS.md` | Vollständiger System-Überblick |
| `THERMAL_NETWORK_SOLVER_REQUIREMENTS.md` | MIQP-Erklärung, Solver-Anforderungen |
| `PERFORMANCE_OPTIMIZATION_THERMAL_NETWORKS.md` | Performance-Tuning, Multi-Threading |
| `DASHBOARD_PREPARATION.md` | Dashboard-Visualisierung (Streamlit/React) |
| `STADTBACH_REAL_DATA_OPTIMIZATION.md` | Reale Daten vorbereiten und nutzen |

---

## 🚀 Production Checklist

Bevor du mit echten Daten produktiv gehst:

- [ ] Gurobi-Lizenz verfügbar
- [ ] Test-Lauf mit Stadtbach-Topologie erfolgreich
- [ ] Network results in exports verifiziert
- [ ] Notebook-Visualisierung getestet
- [ ] Verluste im erwarteten Bereich (0.5-1.5%)
- [ ] Temperaturen realistisch (90-105°C Vorlauf, 50-70°C Rücklauf)
- [ ] Echte Demand-Daten vorbereitet (siehe STADTBACH_REAL_DATA_OPTIMIZATION.md)
- [ ] Performance-Parameter optimiert (siehe PERFORMANCE_OPTIMIZATION.md)

---

## ✨ Quick Wins

**5 Minuten**:
- Öffne `runner.ipynb`
- Ändere CONFIG_PATHS auf test_simple_with_network
- Setze horizon auf 6 Stunden
- Run All → Sehe Network Results!

**30 Minuten**:
- Öffne `thermal_network_analysis.ipynb`
- Run All → Detaillierte Analyse mit Charts
- Export TXT-Report

**2 Stunden**:
- Bereite echte Stadtbach-Daten vor
- Laufe 1-Woche Optimierung
- Vergleiche mit Baseline-Betrieb
- Kalkuliere Einsparungen

---

**🎉 Viel Erfolg mit dem thermischen Netzwerk!**

Bei Fragen:
- Siehe Dokumentation in `docs/`
- Check Test-Scripts in `scripts/`
- Review Beispiel-Configs in `configs/`
