# Pyomo Model Export Feature

## Schnellstart

Das Framework exportiert jetzt automatisch die vollständige Modellstruktur **vor der Solver-Ausführung** für bessere Kontrolle und Validierung.

### Was wird exportiert?

✅ **Parameter** - alle Eingabewerte mit Details
✅ **Variablen** - Entscheidungsvariablen mit Bounds und Domains
✅ **Constraints** - alle Nebenbedingungen mit Ausdrücken
✅ **Zielfunktion** - die zu minimierende/maximierende Funktion
✅ **Sets** - alle verwendeten Mengen (Zeitschritte, Komponenten, etc.)

### Export-Formate

Das Modell wird in **3 Formaten** exportiert **plus 6 Visualisierungen**:

| Format | Datei | Verwendung |
|--------|-------|------------|
| **Excel** | `pyomo_model_before_solve.xlsx` | Tabellen für einfache Analyse |
| **Markdown** | `pyomo_model_before_solve.md` | Lesbare Dokumentation |
| **JSON** | `pyomo_model_before_solve.json` | Maschinenlesbar für Automatisierung |
| **Plots (6x)** | `*_01_overview.png` bis `*_06_complexity_matrix.png` | 📊 Visuelle Analysen |

### Wo finde ich die Exporte?

Nach einem Optimierungslauf:

```
exports/
  └── YYYYMMDD_HHMMSS_<scenario_tag>/
      ├── model_structure/                                    ← NEU!
      │   ├── pyomo_model_before_solve.xlsx                  ← Excel-Tabellen
      │   ├── pyomo_model_before_solve.md                    ← Markdown-Doku
      │   ├── pyomo_model_before_solve.json                  ← JSON-Daten
      │   ├── pyomo_model_before_solve_01_overview.png       ← 📊 Modellgröße
      │   ├── pyomo_model_before_solve_02_variable_types.png ← 📊 Variablentypen
      │   ├── pyomo_model_before_solve_03_constraint_sizes.png ← 📊 Constraint-Größen
      │   ├── pyomo_model_before_solve_04_parameter_timeseries.png ← 📊 Parameter-Zeitreihen
      │   ├── pyomo_model_before_solve_05_variable_bounds.png ← 📊 Variablen-Bounds
      │   └── pyomo_model_before_solve_06_complexity_matrix.png ← 📊 Komplexitätsmatrix
      ├── scenario.xlsx
      ├── costs.json
      └── ...
```

## Beispiel: Excel-Export

Das Excel-File enthält 5 Sheets:

### 1. Summary
```
Model Name: EnerGIS_FuelBus
Sets: 5
Parameters: 18
Variables: 52,347
Constraints: 43,824
Objectives: 1
```

### 2. Parameters
| Name | Type | Size | Domain | Value/Sample |
|------|------|------|--------|--------------|
| strompreis | Parameter | 8760 | NonNegativeReals | 1=45.2, 2=48.1, ... |
| waermebedarf | Parameter | 8760 | NonNegativeReals | 1=12.5, 2=13.2, ... |
| Leistungspreis | Parameter | 1 | NonNegativeReals | 127240.0 |

### 3. Variables
| Name | Type | Size | Domain | Bounds |
|------|------|------|--------|--------|
| P_buy | Variable | 8760 | NonNegativeReals | [0, +∞] |
| HP_Q | Variable | 35040 | NonNegativeReals | [0, +∞] |
| storage_capacity | Variable | 1 | NonNegativeReals | [0, 50000] |
| HP_build | Variable | 4 | Binary | [0, 1] |

### 4. Constraints
| Name | Type | Size | Expression/Note |
|------|------|------|-----------------|
| el_balance | Constraint | 8760 | P_buy[t] + ... == ... + P_sell[t] |
| ht_balance | Constraint | 8760 | sum(HP_Q[i,t]) + ... == waermebedarf[t] + ... |
| HP_cap_con | Constraint | 35040 | HP_Q[i,t] <= HP_cap[i] |

### 5. Objectives
| Name | Sense | Expression |
|------|-------|------------|
| obj | minimize | energy_cost + dump_cost + fuel_costs + co2_term + demand_term + capex_total + ... |

## Verwendung

### Standard (automatisch aktiviert)

```python
from energis.run.orchestrator import run_all

# Export wird automatisch erstellt
results = run_all(config_paths=["configs/base.yaml", "configs/systems/baseline.system.yaml"])
```

### Export deaktivieren

In der Config-Datei:

```yaml
run:
  export_model_structure: false  # Export überspringen
```

### Manueller Export

```python
from energis.io.model_inspector import export_model_structure
from energis.models.system_builder import build_model

# Modell erstellen
model = build_model(table, cfg, dt_h=1.0)

# Modell exportieren
paths = export_model_structure(model, output_dir="my_export", prefix="my_model")

print(f"Excel: {paths['excel_path']}")
print(f"Markdown: {paths['markdown_path']}")
print(f"JSON: {paths['json_path']}")
```

## Anwendungsfälle

### ✅ Vor der Optimierung

**Kontrolle der Modellstruktur:**
- Sind alle erwarteten Parameter gesetzt?
- Haben Variablen die richtigen Bounds?
- Sind alle Constraints vorhanden?

**Beispiel:**
```
# Im Excel-Export prüfen:
1. Sheet "Parameters" → sind alle Zeitreihen vollständig?
2. Sheet "Variables" → sind die Kapazitätsgrenzen korrekt?
3. Sheet "Constraints" → fehlen Constraints?
```

### 🐛 Debugging

**Bei unerwarteten Solver-Ergebnissen:**
- Welche Constraints wurden tatsächlich erzeugt?
- Welche Bounds haben die Variablen?
- Ist die Zielfunktion korrekt?

**Beispiel:**
```
# Solver meldet "infeasible"
1. Öffne Excel-Export → Sheet "Constraints"
2. Prüfe Constraint-Ausdrücke
3. Finde widersprüchliche Bedingungen
```

### 📊 Dokumentation

**Für Berichte und Präsentationen:**
- Modellgröße und Komplexität dokumentieren
- Transparenz über verwendete Annahmen
- Nachvollziehbarkeit der Optimierung

**Beispiel:**
```
# Markdown-Export in Bericht einbinden:
- Anzahl Variablen: 52.347
- Anzahl Constraints: 43.824
- Zeithorizont: 8.760 Stunden (1 Jahr)
```

### 🔍 Modellvergleiche

**Beim Vergleich verschiedener Szenarien:**
- Welche Parameter unterscheiden sich?
- Wurden neue Constraints hinzugefügt?
- Hat sich die Modellgröße geändert?

**Beispiel:**
```bash
# JSON-Exporte vergleichen
diff scenario1/model_structure/pyomo_model_before_solve.json \
     scenario2/model_structure/pyomo_model_before_solve.json
```

## Typische Modellstruktur

Ein Heat Planning Modell für ein Jahr (stündlich) enthält typischerweise:

| Komponente | Anzahl | Beispiele |
|------------|--------|-----------|
| **Sets** | 2-5 | `t` (Zeitschritte: 8760), `HP` (Wärmepumpen: 4) |
| **Parameter** | 10-20 | `strompreis[t]`, `waermebedarf[t]`, `CO2_price` |
| **Variablen** | 50-100 Typen | `P_buy[t]`, `HP_Q[i,t]`, `storage_capacity` |
| | **~500k gesamt** | 8760 × (Anzahl Zeitreihen-Variablen) + ... |
| **Constraints** | 30-50 Typen | `el_balance[t]`, `ht_balance[t]`, `HP_cap_con[i,t]` |
| | **~100k gesamt** | 8760 × (Anzahl Zeitreihen-Constraints) + ... |
| **Objective** | 1 | Minimierung: Energie + Invest + CO2 + ... |

## Vorteile

✅ **Transparenz** - vollständige Einsicht in Modellstruktur
✅ **Qualitätssicherung** - Fehler vor Optimierung erkennen
✅ **Dokumentation** - automatische Modell-Dokumentation
✅ **Debugging** - schnellere Fehlersuche
✅ **Reproduzierbarkeit** - Modell-Versionen nachvollziehbar

## Performance

- **Export-Zeit**: ~5-10 Sekunden für typisches Modell (8760 Zeitschritte)
- **Dateigröße**:
  - Excel: ~1-5 MB
  - Markdown: ~100-500 KB
  - JSON: ~500 KB - 2 MB
- **Overhead**: Minimal, da nur vor Solver-Ausführung

## 📊 Visualisierungen

Zusätzlich zu den Daten-Exporten werden **6 professionelle Plots** automatisch erstellt:

1. **Model Structure Overview** - Modellgröße auf einen Blick
2. **Variable Types Distribution** - Verteilung der Variablentypen
3. **Constraint Sizes** - Top 20 größte Constraint-Gruppen
4. **Parameter Time Series** - Zeitreihen (Strompreis, Wärmebedarf, CO2)
5. **Variable Bounds Overview** - Variablengrenzen und Bounded/Unbounded
6. **Model Complexity Matrix** - Komplexitäts-Heatmap

📖 **Detaillierte Plot-Dokumentation**: [`docs/MODEL_PLOTS.md`](docs/MODEL_PLOTS.md)

### Beispiel-Plots

Die Plots helfen dir:
- ✅ **Vor Optimierung**: Modell schnell validieren
- ✅ **Beim Debugging**: Probleme visuell identifizieren
- ✅ **Für Dokumentation**: Professionelle Präsentationen
- ✅ **Beim Vergleich**: Szenarien visuell gegenüberstellen

## Weitere Informationen

📖 **Vollständige Dokumentation**: [`docs/MODEL_EXPORT.md`](docs/MODEL_EXPORT.md)

📊 **Plot-Dokumentation**: [`docs/MODEL_PLOTS.md`](docs/MODEL_PLOTS.md)

🔧 **Implementierung**: [`energis/io/model_inspector.py`](energis/io/model_inspector.py)

🧪 **Test-Skript**: [`test_model_export.py`](test_model_export.py)

## Support

Bei Fragen oder Problemen:
1. Lesen Sie die [vollständige Dokumentation](docs/MODEL_EXPORT.md)
2. Prüfen Sie die [Beispiel-Exporte](test_exports/)
3. Kontaktieren Sie das Entwicklungsteam
