# 🔧 Dashboard Robustness Fix - Dokumentation

## 📋 Zusammenfassung

Dieses Dokument beschreibt die Verbesserungen am Dashboard (`energis/io/dashboard.py`), um Probleme mit fehlenden oder unvollständigen Daten zu beheben.

**Branch:** `claude/fix-dashboard-display-01F7xZRVF9viC62xR9ouC96U`

---

## 🐛 Identifizierte Probleme

### 1. **Hardcodierte Spaltennamen**
- **Problem:** Das Dashboard suchte nur nach `'waermebedarf_MWth'`
- **Auswirkung:** Bei anderen Namenskonventionen wurden keine Daten angezeigt
- **Beispiele für fehlende Namen:** `Waermebedarf_MWth`, `heat_demand_MW`, `demand_MW`, `Q_demand_MW`

### 2. **Fehlende Validierung von result.series**
- **Problem:** Keine Prüfung ob `result.series` leer ist
- **Auswirkung:** Leeres DataFrame, keine Zeitreihen-Anzeige
- **Keine aussagekräftige Fehlermeldung**

### 3. **Unzureichende Längenprüfung**
- **Problem:** Keine Validierung ob series-Längen mit DataFrame-Länge übereinstimmen
- **Auswirkung:** Potenzielle Pandas-Fehler bei Längen-Mismatch

### 4. **Leere Kosten-Daten**
- **Problem:** Wenn `result.costs` leer/None ist, nur generische Meldung
- **Auswirkung:** Benutzer weiß nicht, warum Kosten fehlen

### 5. **Fehlendes Design**
- **Problem:** Keine klare Anleitung wenn `workflow.design` None ist
- **Auswirkung:** Benutzer versteht nicht, wie Design-Daten entstehen

### 6. **Keine Komponenten-Erkennung**
- **Problem:** Wenn keine `_Q_th_MW` oder `_Pel_MW` Spalten gefunden werden
- **Auswirkung:** Zeitreihen-Tab zeigt keine Daten

---

## ✅ Implementierte Lösungen

### 1. **Flexible Demand-Spalten-Erkennung**

```python
# Versuche multiple gebräuchliche Namen
demand_col_names = [
    'waermebedarf_MWth',
    'Waermebedarf_MWth',
    'heat_demand_MW',
    'demand_MW',
    'Q_demand_MW'
]

for col_name in demand_col_names:
    if col_name in result.table.data:
        demand_values = result.table.data[col_name]
        demand_col_found = col_name
        break

# Fallback mit Logging
if demand_values is None:
    demand_values = [0.0] * len(result.table.index)
    logging.warning(
        f"Dashboard: No demand column found. Tried: {demand_col_names}. "
        f"Available: {list(result.table.data.keys())}"
    )
```

**Vorteile:**
- ✅ Funktioniert mit verschiedenen Namenskonventionen
- ✅ Zeigt verfügbare Spalten im Log
- ✅ Stürzt nicht ab bei fehlendem Demand

### 2. **Series-Validierung mit Längenprüfung**

```python
# Prüfe ob series leer ist
if result.series:
    for key, values in result.series.items():
        # Stelle sicher, dass Längen übereinstimmen
        if len(values) == len(self.df):
            self.df[key] = values
        else:
            logging.warning(
                f"Dashboard: Skipping series '{key}' - length mismatch "
                f"(expected {len(self.df)}, got {len(values)})"
            )
else:
    logging.warning("Dashboard: result.series is empty - no timeseries data")
```

**Vorteile:**
- ✅ Verhindert Pandas-Fehler bei Längen-Mismatch
- ✅ Loggt welche Series übersprungen werden
- ✅ Dashboard funktioniert trotz teilweise fehlender Daten

### 3. **Komponenten-Erkennung mit Logging**

```python
# Identifiziere Komponenten
self.heat_components = [col for col in self.df.columns if col.endswith('_Q_th_MW')]
self.elec_components = [col for col in self.df.columns if col.endswith('_Pel_MW')]

# Warne wenn keine Komponenten gefunden
if not self.heat_components and not self.elec_components:
    logging.warning(
        f"Dashboard: No components detected. "
        f"Available columns: {list(self.df.columns)}"
    )
```

**Vorteile:**
- ✅ Zeigt verfügbare Spalten im Log
- ✅ Hilft beim Debugging von Namenskonventionen

### 4. **Verbesserte Kosten-Validierung**

```python
# Erstelle Liste von Kosteneinträgen
cost_entries = []
for key, value in result.costs.items():
    if isinstance(value, (int, float)) and key.endswith('_EUR'):
        cost_entries.append({...})

# Prüfe ob Einträge gefunden wurden
if cost_entries:
    self.costs_df = pd.DataFrame(cost_entries)
    # ... Berechne Prozente ...
else:
    self.costs_df = pd.DataFrame()
    logging.warning("Dashboard: No valid cost entries found")
```

**Vorteile:**
- ✅ Unterscheidet zwischen "keine Kosten" und "ungültige Kosten"
- ✅ Loggt spezifisch was fehlt

### 5. **Aussagekräftige Tab-Fehlermeldungen**

#### **Zeitreihen-Tab:**

```markdown
## ⚠️ Keine Zeitreihendaten verfügbar

Das Workflow-Ergebnis enthält keine Zeitreihendaten. Mögliche Ursachen:
- Die Optimierung ist fehlgeschlagen
- Das result.series Dictionary ist leer
- Es gibt ein Datenformat-Problem

Bitte prüfe die Logs für weitere Details.
```

#### **Kosten-Tab:**

```markdown
## ⚠️ Keine Kostendaten verfügbar

Das Workflow-Ergebnis enthält keine Kostendaten. Mögliche Ursachen:
- Die Optimierung ist fehlgeschlagen
- result.costs ist leer oder None
- Keine Kosteneinträge mit '_EUR' Endung gefunden

Prüfe ob die Optimierung erfolgreich durchgelaufen ist und ob
Kostenkomponenten in der Konfiguration aktiviert sind.
```

#### **Design-Tab:**

```markdown
## ⚠️ Kein Anlagen-Design verfügbar

Das Workflow enthält keine Design-Informationen. Mögliche Ursachen:
- Kein PF-Schritt wurde ausgeführt (Design wird in PF erstellt)
- Die PF-Optimierung ist fehlgeschlagen
- RH-Only Modus ohne vorheriges PF

Um Design-Daten zu erhalten:
- Führe einen PF-Schritt aus (z.B. PF_THEN_RH)
- Oder lade ein bestehendes Design mit `pf_design_json`
```

**Vorteile:**
- ✅ Benutzerfreundliche Fehlermeldungen
- ✅ Konkrete Ursachen aufgelistet
- ✅ Handlungsempfehlungen gegeben
- ✅ Kein Absturz, nur Info-Anzeige

### 6. **Design-Komponenten-Validierung**

```python
# Prüfe ob Design Komponenten hat
if not hp_data:
    return pn.Column(
        pn.pane.Markdown(
            "## ⚠️ Keine Komponenten im Design gefunden\n\n"
            "Das Design-Objekt existiert, aber enthält keine WP oder Speicher.\n\n"
            "Dies kann passieren wenn:\n"
            "- Alle Komponenten deaktiviert sind\n"
            "- Kapazitäten auf 0 gesetzt wurden\n"
            "- Problem beim Extrahieren des Designs"
        )
    )
```

**Vorteile:**
- ✅ Unterscheidet zwischen "kein Design" und "leeres Design"
- ✅ Spezifische Hinweise zur Ursache

---

## 🎯 Wie das Dashboard jetzt mit verschiedenen Szenarien umgeht

### **Szenario 1: PF_ONLY**
- ✅ Zeigt PF-Ergebnisse
- ✅ Zeigt Design-Tab mit PF-Design
- ✅ Kein Vergleichs-Tab (normal)

### **Szenario 2: RH_ONLY (ohne PF)**
- ✅ Zeigt RH-Ergebnisse
- ⚠️ Design-Tab zeigt hilfreiche Meldung
- ✅ Keine Abstürze

### **Szenario 3: PF_THEN_RH**
- ✅ Zeigt RH-Ergebnisse (als primary)
- ✅ Zeigt Design aus PF
- ✅ Zeigt Vergleichs-Tab (PF vs RH)

### **Szenario 4: Fehlgeschlagene Optimierung**
- ✅ Zeigt klare Fehlermeldungen in jedem Tab
- ✅ Loggt Warnungen mit Details
- ✅ Kein Absturz, sondern Info-Anzeige

### **Szenario 5: Teilweise Daten**
- ✅ Zeigt verfügbare Tabs
- ⚠️ Fehlende Tabs zeigen Erklärung
- ✅ Lengt-Mismatches werden behandelt

### **Szenario 6: Verschiedene Systeme**
- ✅ Flexible Spaltennamen-Erkennung
- ✅ Loggt verfügbare Spalten bei Problemen
- ✅ Funktioniert mit verschiedenen Namenskonventionen

---

## 📊 Verbesserungsvorschläge für die Zukunft

### **1. Erweiterte Namens-Erkennung**

Implementiere Pattern-Matching für Spalten:

```python
import re

def find_demand_column(data_columns):
    """Find demand column using patterns."""
    patterns = [
        r'.*waermebedarf.*',  # Case-insensitive matching
        r'.*demand.*',
        r'.*heat.*load.*',
    ]

    for pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        matches = [col for col in data_columns if regex.match(col)]
        if matches:
            return matches[0]

    return None
```

**Vorteil:** Noch flexibler bei verschiedenen Namenskonventionen

### **2. Dashboard-Validierungs-Funktion**

```python
def validate_workflow_for_dashboard(workflow):
    """
    Validate that workflow has minimum required data for dashboard.

    Returns:
        tuple: (is_valid, warnings, errors)
    """
    warnings = []
    errors = []

    # Check for at least one result
    if not any([workflow.pf_result, workflow.rh_result, workflow.mpc_result]):
        errors.append("No optimization results found")
        return False, warnings, errors

    # Check primary result
    primary = workflow.rh_result or workflow.mpc_result or workflow.pf_result

    # Check for timeseries
    if not primary.series or len(primary.series) == 0:
        warnings.append("No timeseries data in result.series")

    # Check for costs
    if not primary.costs or len(primary.costs) == 0:
        warnings.append("No cost data in result.costs")

    # Check for design
    if not workflow.design:
        warnings.append("No design data available")

    return True, warnings, errors
```

**Vorteil:** Proaktive Validierung vor Dashboard-Erstellung

### **3. Konfigurierbares Dashboard**

```python
@dataclass
class DashboardConfig:
    """Configuration for dashboard behavior."""

    demand_column_names: List[str] = field(default_factory=lambda: [
        'waermebedarf_MWth', 'heat_demand_MW', 'demand_MW'
    ])

    heat_component_suffixes: List[str] = field(default_factory=lambda: [
        '_Q_th_MW', '_thermal_MW', '_heat_MW'
    ])

    elec_component_suffixes: List[str] = field(default_factory=lambda: [
        '_Pel_MW', '_electric_MW', '_power_MW'
    ])

    show_empty_tabs: bool = True  # Show tabs with warnings vs hide them
    strict_mode: bool = False      # Raise errors vs show warnings


def create_dashboard(workflow, title="Dashboard", config=None):
    """Create dashboard with optional configuration."""
    if config is None:
        config = DashboardConfig()

    dashboard = EnerGISDashboard(workflow, title, config)
    return dashboard.create()
```

**Vorteil:** Anpassbar an verschiedene Projektanforderungen

### **4. Diagnostik-Modus**

```python
def create_diagnostic_dashboard(workflow):
    """
    Create a diagnostic dashboard that shows detailed info about
    data structure and availability.
    """

    # Add diagnostic tab showing:
    # - All available columns in result.table.data
    # - All keys in result.series
    # - All keys in result.costs
    # - Design structure
    # - Detected component types
    # - Validation results
```

**Vorteil:** Hilft beim Debugging von Dashboard-Problemen

### **5. Export-Funktion für fehlende Daten**

```python
def export_dashboard_diagnostics(workflow, output_path):
    """
    Export detailed diagnostics about what data is available/missing.
    """

    diagnostics = {
        'workflow_steps': list(workflow.plan.steps),
        'available_results': {
            'pf': workflow.pf_result is not None,
            'rh': workflow.rh_result is not None,
            'mpc': workflow.mpc_result is not None,
        },
        'data_availability': {},
        'detected_columns': {},
        'warnings': [],
    }

    # Fill in details...

    with open(output_path, 'w') as f:
        json.dump(diagnostics, f, indent=2)
```

**Vorteil:** Dokumentiert Probleme für Support/Debugging

### **6. Multi-Szenario Dashboard**

```python
def create_multi_scenario_dashboard(workflows: List[WorkflowResult],
                                    labels: List[str]):
    """
    Create dashboard that compares multiple scenarios side-by-side.

    Parameters:
        workflows: List of WorkflowResult objects
        labels: List of scenario names
    """

    # Add comparison features:
    # - Side-by-side plots
    # - Cost comparison across scenarios
    # - Design comparison
    # - Sensitivity analysis views
```

**Vorteil:** Ermöglicht Szenario-Vergleiche direkt im Dashboard

### **7. Robustere Datentyp-Behandlung**

```python
def safe_float_conversion(value, default=0.0):
    """Safely convert value to float with fallback."""
    try:
        if value is None or value != value:  # None or NaN
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

# Verwenden in allen numerischen Konversionen
capacity = safe_float_conversion(hp_info.get('capacity_mw'), 0.0)
```

**Vorteil:** Verhindert Abstürze bei unerwarteten Datentypen

---

## 🔍 Testing-Empfehlungen

### **Test 1: Leeres result.series**
```python
# Simuliere leere Ergebnisse
from collections import OrderedDict
result.series = OrderedDict()  # Leer

# Erwartung: Dashboard zeigt Warnung in Zeitreihen-Tab
```

### **Test 2: Fehlende Demand-Spalte**
```python
# Entferne demand aus table.data
del result.table.data['waermebedarf_MWth']

# Erwartung: Log-Warning, Dashboard verwendet Fallback (zeros)
```

### **Test 3: Längen-Mismatch**
```python
# Ungültige Series-Länge
result.series['test_column'] = [1.0, 2.0]  # Zu kurz

# Erwartung: Series wird übersprungen, Log-Warning
```

### **Test 4: Fehlende Kosten**
```python
result.costs = {}  # Leer

# Erwartung: Kosten-Tab zeigt hilfreiche Meldung
```

### **Test 5: Fehlendes Design**
```python
workflow.design = None

# Erwartung: Design-Tab zeigt Anleitung zum Erhalt von Design-Daten
```

### **Test 6: RH_ONLY ohne PF**
```python
# Workflow mit nur RH-Schritt
workflow = rh.run_workflow(configs, overrides={'scenario': {'run_mode': 'RH_ONLY'}})

# Erwartung: Funktioniert, Design-Tab zeigt Info-Meldung
```

---

## 📝 Zusammenfassung der Änderungen

### **Geänderte Dateien:**
- `energis/io/dashboard.py` - Hauptfixes

### **Neue Dateien:**
- `test_dashboard_fix.py` - Test-Skript
- `DASHBOARD_FIX_DOCUMENTATION.md` - Diese Dokumentation

### **Zeilen geändert:**
- `_prepare_data()`: ~90 Zeilen (erweitert und robuster)
- `_create_timeseries_tab()`: +18 Zeilen (Validierung)
- `_create_costs_tab()`: +12 Zeilen (bessere Fehlermeldung)
- `_create_design_tab()`: +24 Zeilen (bessere Validierung)

### **Backward Compatibility:**
- ✅ Alle bestehenden Funktionalitäten bleiben erhalten
- ✅ Funktioniert mit bestehenden Workflows
- ✅ Nur zusätzliche Robustheit, keine Breaking Changes

---

## 🚀 Nächste Schritte

1. **Testen Sie das Dashboard** mit verschiedenen Szenarien:
   ```python
   from energis.run import rolling_horizon as rh
   from energis.io.dashboard import create_dashboard

   # Test mit verschiedenen Workflows
   workflow = rh.run_workflow(config_paths)
   dashboard = create_dashboard(workflow)
   dashboard.show()  # In Jupyter
   ```

2. **Prüfen Sie die Logs** auf Warnungen:
   ```python
   import logging
   logging.basicConfig(level=logging.WARNING)
   ```

3. **Testen Sie Edge Cases**:
   - RH_ONLY (ohne PF)
   - Fehlgeschlagene Optimierung
   - Verschiedene Systeme mit anderen Spaltennamen

4. **Feedback geben**:
   - Welche Fehlermeldungen sind hilfreich?
   - Welche zusätzlichen Validierungen wären nützlich?
   - Gibt es weitere Edge Cases?

---

## 📧 Support

Bei Fragen oder Problemen:
1. Prüfe die Logs (Level: WARNING oder höher)
2. Schaue in diese Dokumentation
3. Erstelle ein Issue mit:
   - Verwendetem Workflow (PF/RH/MPC)
   - Fehlermeldung oder unerwartetes Verhalten
   - Relevante Log-Ausgaben

---

**Datum:** 2025-12-01
**Branch:** `claude/fix-dashboard-display-01F7xZRVF9viC62xR9ouC96U`
**Status:** ✅ Implementiert, bereit für Testing
