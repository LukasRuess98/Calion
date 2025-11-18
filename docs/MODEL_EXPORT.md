# Pyomo Model Export - Dokumentation

## Überblick

Das Heat Planning Framework exportiert nun automatisch die vollständige Struktur des Pyomo-Optimierungsmodells **vor der Solver-Ausführung**. Dies ermöglicht eine detaillierte Kontrolle und Validierung des Modells, bevor die Optimierung gestartet wird.

## Export-Formate

Der Export erstellt drei Dateien:

1. **Excel (.xlsx)** - Strukturierte Tabellen für einfache Analyse
2. **Markdown (.md)** - Lesbare Dokumentation mit Formatierung
3. **JSON (.json)** - Maschinenlesbare Vollständige Daten

## Exportierte Informationen

### 1. Zusammenfassung (Summary)
- Modellname
- Anzahl der Sets
- Anzahl der Parameter
- Anzahl der Variablen (gesamt und nach Typ)
- Anzahl der Constraints (gesamt und nach Typ)
- Anzahl der Zielfunktionen

### 2. Sets
- Set-Namen
- Set-Größen
- Set-Elemente (für kleine Sets)

### 3. Parameter
- Name
- Typ (indexiert oder skalar)
- Größe
- Domain
- Werte oder Beispielwerte

**Beispiele:**
- `strompreis_EUR_MWh[t]` - Strompreise für jeden Zeitschritt
- `waermebedarf_MWth[t]` - Wärmebedarf für jeden Zeitschritt
- `Leistungspreis` - Leistungspreis in EUR/MW

### 4. Variablen
- Name
- Typ (indexiert oder skalar)
- Größe
- Domain (NonNegativeReals, Binary, Reals, etc.)
- Unter- und Obergrenzen (Bounds)

**Beispiele:**
- `P_buy[t]` - Strombezug aus dem Netz (≥ 0)
- `HP_Q[i,t]` - Wärmeleistung der Wärmepumpe i zum Zeitpunkt t
- `storage_capacity` - Speicherkapazität in MWh (z.B. 0 bis 50000)
- `HP_build[i]` - Binäre Investitionsentscheidung für Wärmepumpe i

### 5. Constraints (Nebenbedingungen)
- Name
- Typ (indexiert oder skalar)
- Anzahl der Constraints
- Beispiel-Ausdrücke (für kleine Constraint-Sets)

**Beispiele:**
- `el_balance[t]` - Elektrische Leistungsbilanz für jeden Zeitschritt
- `ht_balance[t]` - Thermische Energiebilanz für jeden Zeitschritt
- `HP_cap_con[i,t]` - Kapazitätsgrenzen für Wärmepumpen
- `storage_level_max[t]` - Maximaler Speicherfüllstand

### 6. Zielfunktion (Objective)
- Name
- Richtung (minimize/maximize)
- Ausdruck (vereinfachte Darstellung)

**Beispiel:**
```
minimize: energy_cost + dump_cost + fuel_costs + co2_term + demand_term + capex_total + ...
```

## Verwendung

### Automatischer Export

Der Export wird automatisch ausgeführt, wenn ein Optimierungslauf gestartet wird:

```python
from energis.run.orchestrator import run_all

# Der Export wird automatisch vor der Solver-Ausführung erstellt
results = run_all(config_paths=["configs/base.yaml", "configs/systems/baseline.system.yaml"])
```

Die exportierten Dateien befinden sich in:
```
exports/
  └── YYYYMMDD_HHMMSS_<scenario_tag>/
      └── model_structure/
          ├── pyomo_model_before_solve.xlsx
          ├── pyomo_model_before_solve.md
          └── pyomo_model_before_solve.json
```

### Export deaktivieren

Falls gewünscht, kann der Export in der Run-Konfiguration deaktiviert werden:

```yaml
# In der Config-Datei (z.B. configs/base.yaml)
run:
  export_model_structure: false
```

### Manueller Export

Der Export kann auch manuell für ein beliebiges Pyomo-Modell durchgeführt werden:

```python
from energis.io.model_inspector import export_model_structure
from energis.models.system_builder import build_model

# Modell erstellen
model = build_model(table, cfg, dt_h=1.0)

# Modell exportieren
paths = export_model_structure(
    model,
    output_dir="custom_export",
    prefix="my_model"
)

print(f"Excel: {paths['excel_path']}")
print(f"Markdown: {paths['markdown_path']}")
print(f"JSON: {paths['json_path']}")
```

## Excel-Export Details

Das Excel-File enthält folgende Sheets:

1. **Summary** - Modell-Übersicht
2. **Parameters** - Alle Parameter mit Werten
3. **Variables** - Alle Variablen mit Bounds
4. **Constraints** - Alle Constraints mit Ausdrücken
5. **Objectives** - Zielfunktionen

Spaltenbreiten werden automatisch angepasst für bessere Lesbarkeit.

## Markdown-Export Details

Das Markdown-File ist optimal für:
- Dokumentation in Git-Repositories
- Review-Prozesse
- Schnelle Übersicht über Modellstruktur

Enthält formatierte Tabellen und Code-Blöcke für bessere Lesbarkeit.

## JSON-Export Details

Das JSON-File ist optimal für:
- Programmatische Weiterverarbeitung
- Versionskontrolle und Diff-Vergleiche
- Automatisierte Tests

## Anwendungsfälle

### 1. Modell-Validierung vor Optimierung

Vor einem langen Optimierungslauf kann geprüft werden:
- Sind alle Parameter korrekt gesetzt?
- Haben Variablen die richtigen Bounds?
- Sind alle erwarteten Constraints vorhanden?
- Ist die Zielfunktion korrekt formuliert?

### 2. Debugging

Bei unerwarteten Solver-Ergebnissen:
- Welche Constraints wurden tatsächlich erzeugt?
- Welche Variablen sind im Modell enthalten?
- Sind die Parameter-Werte plausibel?

### 3. Dokumentation

Für Berichte und Präsentationen:
- Übersichtliche Darstellung der Modellstruktur
- Transparenz über verwendete Annahmen
- Nachvollziehbarkeit der Optimierung

### 4. Modellvergleiche

Beim Vergleich verschiedener Szenarien:
- Welche Parameter unterscheiden sich?
- Wurden neue Constraints hinzugefügt?
- Hat sich die Modellgröße geändert?

## Beispiel: Typische Modellstruktur

Ein typisches Heat Planning Modell enthält:

**Sets:**
- `t` (Zeitschritte): 1...8760 (ein Jahr, stündlich)
- `HP` (Wärmepumpen): {1, 2, 3, 4}

**Parameter (~10-20):**
- Zeitreihen: `strompreis[t]`, `waermebedarf[t]`, `grid_co2[t]`
- Kosten: `Leistungspreis`, `Gaspreis`, `CO2_price`
- Technische: `COP_series[i,t]`, `storage_eff_charge`

**Variablen (~50-100 Typen, ~500k gesamt):**
- Leistungsflüsse: `P_buy[t]`, `P_sell[t]`, `HP_Q[i,t]`
- Speicher: `storage_level[t]`, `storage_charge[t]`
- Investition: `HP_cap[i]`, `storage_capacity`, `HP_build[i]`

**Constraints (~30-50 Typen, ~100k gesamt):**
- Bilanzen: `el_balance[t]`, `ht_balance[t]`
- Grenzen: `HP_cap_con[i,t]`, `storage_level_max[t]`
- Dynamik: `storage_dynamics[t]`

**Objective (1):**
- Minimierung der Gesamtkosten (Energie + Investition + CO2 + ...)

## Tipps

1. **Vor großen Optimierungsläufen**: Prüfen Sie den Export, um sicherzustellen, dass das Modell korrekt aufgebaut wurde.

2. **Bei Solver-Fehlern**: Schauen Sie sich die Constraint-Ausdrücke an, um Inkonsistenzen zu identifizieren.

3. **Für Dokumentation**: Nutzen Sie die Markdown-Datei als Basis für technische Berichte.

4. **Versionskontrolle**: Committen Sie die JSON-Datei, um Modelländerungen nachvollziehbar zu machen.

## Technische Details

Die Export-Funktion verwendet die Pyomo-API, um:
- `model.component_objects(pyo.Set)` - Alle Sets zu extrahieren
- `model.component_objects(pyo.Param)` - Alle Parameter zu extrahieren
- `model.component_objects(pyo.Var)` - Alle Variablen zu extrahieren
- `model.component_objects(pyo.Constraint)` - Alle Constraints zu extrahieren
- `model.component_objects(pyo.Objective)` - Alle Zielfunktionen zu extrahieren

Für große indexierte Komponenten werden Beispielwerte exportiert, um die Dateigröße überschaubar zu halten.

## Fehlerbehebung

**Problem**: Export-Dateien werden nicht erstellt
- **Lösung**: Prüfen Sie, ob Pyomo installiert ist: `pip list | grep pyomo`

**Problem**: Excel-Datei zu groß / zu langsam
- **Lösung**: Die Funktion begrenzt automatisch die Anzahl der exportierten Beispielwerte

**Problem**: Constraint-Ausdrücke nicht lesbar
- **Lösung**: Die Ausdrücke werden auf 200 Zeichen gekürzt. Schauen Sie in die JSON-Datei für vollständige Ausdrücke

## Support

Bei Fragen oder Problemen:
1. Prüfen Sie diese Dokumentation
2. Schauen Sie sich die Beispiel-Exporte an
3. Kontaktieren Sie das Framework-Team
