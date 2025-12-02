# 📚 Archived Documentation

**Letztes Update:** 2025-12-02
**Grund:** Beschreiben veraltete Workflows, Prozess-Dokumentation, oder obsolete Features

---

## ⚠️ Diese Dokumentation ist VERALTET oder ARCHIVIERT

Dieses Verzeichnis enthält:
1. **Alte Dashboard-Workflows** (Mock-Daten, alte Shell-Scripts) - überholt durch Standalone Dashboard
2. **Prozess-Dokumentation** (Merge-Reports, Validierungsberichte) - historisch relevant, aber nicht für Benutzer
3. **Legacy Features** - Features die entfernt oder ersetzt wurden

---

## 📋 Archivierte Dokumente

### 📁 `process_docs/` - Entwicklungs-Prozess-Dokumentation

Diese Dokumente dokumentieren den Entwicklungsprozess, Merges, Refactorings und Validierungen. Sie sind für die Nachvollziehbarkeit archiviert, aber nicht für Endbenutzer relevant.

**Merge & Integration Reports:**
- `CONFLICT_RESOLUTION_GUIDE.md` - Merge-Konflikt-Dokumentation
- `MERGE_IMPACT_ANALYSIS.md` - Merge Impact Analyse
- `MAIN_BRANCH_COMPATIBILITY_REPORT.md` - Kompatibilitätsbericht
- `FINAL_MAIN_COMPATIBILITY_CHECK.md` - Main Branch Kompatibilitätsprüfung
- `FINAL_INTEGRATION_REVIEW.md` - Finale Integration Review

**Validation & Test Reports:**
- `DATATYPE_COMPATIBILITY_REPORT.md` - Datentyp-Kompatibilitätsbericht
- `DESIGN_AND_COST_VALIDATION.md` - Design- und Kosten-Validierung
- `ERROR_ANALYSIS_AND_FIXES.md` - Fehleranalyse und Fixes
- `MPC_TEST_REPORT.md` - MPC Test Report
- `RUNNER_EXPORT_SENSITIVITY_COMPATIBILITY.md` - Runner Export Kompatibilität

**Refactoring & Migration:**
- `REFACTORING_DECISIONS.md` - Refactoring Entscheidungen
- `ANLEITUNG.md` - Alte Framework-Anleitung (überholt durch README.md)
- `CLEANUP_SUMMARY.md` - Cleanup-Zusammenfassung
- `NOTEBOOK_UPDATE_GUIDE.md` - Notebook Update Guide
- `PR_DESCRIPTION.md` - Pull Request Beschreibungen

**Status:** Historisch relevant für Entwickler, aber nicht für Endbenutzer

---

### 📁 `dashboard_legacy/` - Alte Dashboard-Dokumentation

Diese Dokumente beschreiben den alten Dashboard-Workflow und spezifische Bugfixes. Überholt durch `DASHBOARD.md` (Standalone Dashboard) im Projekt-Root.

**Quickstart Guides:**
- `DASHBOARD_QUICKSTART.md` - Alte Dashboard Schnellanleitung (nutzt create_and_display_dashboard, entfernt)

**Fix Documentation:**
- `DASHBOARD_FIX_DOCUMENTATION.md` - Dashboard Robustness Fix Dokumentation
- `DASHBOARD_KERNEL_FIX.md` - Dashboard Kernel Cache Fix
- `DASHBOARD_VALIDATION_REPORT.md` - Dashboard Validierungsbericht

**Installation:**
- `DASHBOARD_INSTALL.md` - Alte Dashboard Installation (Mock-Daten basiert)

**Status:** Überholt durch **DASHBOARD.md** im Projekt-Root (Standalone Dashboard mit start_dashboard.py)

---

### 📁 Root Archive Files - Legacy Features

### DASHBOARD_QUICKSTART.md

**Original-Zweck:** Schnellanleitung für Dashboard-Setup
**Beschrieb:**
- `install_dashboard.sh` - Installation + Mock-Daten
- `start_dashboard.sh` - Dashboard starten
- `stop_dashboard.sh` - Dashboard stoppen

**Warum veraltet:**
- Shell-Scripts wurden durch Notebooks ersetzt
- Mock-Daten nicht mehr nötig (echte Workflows)
- Komplizierter als neue Lösung

### DASHBOARD_INSTALL.md

**Original-Zweck:** Detaillierte Installations-Anleitung
**Beschrieb:**
- Python-Dependencies installieren
- Mock-Simulationen erstellen
- Dashboard-Server konfigurieren

**Warum veraltet:**
- Mock-Setup nicht mehr nötig
- Standard pip install ausreichend
- Server-Setup ist jetzt anders

### REAL_DATA_GUIDE.md

**Original-Zweck:** Migration von Mock zu echten Daten
**Beschrieb:**
- Mock-Simulationen erkennen
- Echte Workflows erstellen
- Dashboard aktualisieren

**Warum veraltet:**
- Neue Integration nutzt nur echte Workflows
- Keine Mock→Real Migration mehr nötig
- save_workflow_run() macht das automatisch

---

## ✅ Aktuelle Dokumentation

### Haupt-Dokumentation (Projekt-Root)
- **README.md** - Haupt-Dokumentation & CLI-Nutzung
- **ARCHITECTURE_V2.md** - Framework-Architektur & Plugin-System
- **MIGRATION_GUIDE_V2.md** - Migration zu V2
- **DASHBOARD.md** - Standalone Dashboard Dokumentation (NEU - ersetzt alte Dashboard-Docs)

### Dashboard-Setup:

📖 **DASHBOARD.md** - Standalone Dashboard Anleitung
- Starten mit `python start_dashboard.py`
- Workflow-Auswahl und Visualisierung
- Troubleshooting
- Best Practices

📖 **docs/SERVER_SETUP.md**
- Server Deployment
- JupyterLab, Headless, Panel Server Optionen

### Benutzer-Guides (docs/)
- **APPLIED_ENERGIES_GUIDE.md** - Export für Applied Energies Journal
- **BENCHMARK_RUNNER_GUIDE.md** - Benchmark Runner
- **MODEL_EXPORT.md** - Model Export Features
- **MODEL_PLOTS.md** - Plotting Features
- **MPC_USAGE_EXAMPLES.md** - MPC Verwendungsbeispiele
- **PUBLICATION_EXPORTS.md** - Publikations-Exports
- **PUBLICATION_FEATURES_README.md** - Publikations-Features
- **PUBLICATION_READY_METHODS.md** - Publikationsfertige Methoden
- **RUN_METHODS_COMPARISON.md** - Vergleich der Run-Methoden
- **STORAGE_CONFIGURATION_GUIDE.md** - Speicher-Konfiguration
- **STRATIFIED_STORAGE_INTEGRATION.md** - Stratified Storage Integration

### Notebook-Dokumentation
- **notebooks/README.md** - Notebook-Übersicht & Entscheidungsbaum

### Technische Dokumentation (docs/)
- **methodology.md** - MILP-Modell-Methodik
- **stratified_storage.md** - Stratified Storage Details
- **data_availability.md** - Datenverfügbarkeit
- **paper_outline.md** - Paper Outline

---

## 🚀 Quick Start (Aktuell)

### 1. Simulation ausführen (in Notebooks):

```python
# In runner.ipynb oder scenario_studio.ipynb
from energis.run import rolling_horizon as rh
from energis.io.notebook_helpers import save_workflow_run

# Optimierung ausführen
workflow = rh.run_workflow(config_paths)

# Automatisch speichern mit Metadaten
workflow_dir = save_workflow_run(
    workflow,
    name="Mein Test",
    description="Baseline mit optimierten Parametern"
)
```

### 2. Dashboard starten (Standalone):

```bash
# Standalone Dashboard (empfohlen)
python start_dashboard.py

# Oder mit Workflow Browser Notebook
panel serve notebooks/workflow_browser.ipynb --show
```

Das Dashboard lädt automatisch alle gespeicherten Workflows aus `saved_workflows/` und bietet eine Dropdown-Auswahl zur Visualisierung.

---

## 🔄 Migration von alter zu neuer Dokumentation

| Alt (Archiviert) | Neu (Aktuell) | Abschnitt |
|------------------|---------------|-----------|
| DASHBOARD_QUICKSTART.md | **DASHBOARD.md** (Root) | Quick Start |
| DASHBOARD_INSTALL.md | **DASHBOARD.md** (Root) | Installation & Setup |
| DASHBOARD_FIX_DOCUMENTATION.md | - | Feature integriert |
| REAL_DATA_GUIDE.md | - | Nicht mehr nötig |
| ANLEITUNG.md | **README.md** | Framework-Nutzung |
| install_dashboard.sh | `pip install panel holoviews bokeh plotly` | Installation |
| start_dashboard.sh | `python start_dashboard.py` | Dashboard starten |
| create_mock_simulations.py | `save_workflow_run()` | Workflows speichern |
| create_and_display_dashboard() | start_dashboard.py | Dashboard unabhängig von Notebooks |

---

## 📊 Vergleich: Alt vs. Neu

### Alter Workflow (Archiviert)

```bash
# 1. Installation mit Mock-Daten
./install_dashboard.sh

# 2. Dashboard starten
./start_dashboard.sh

# 3. Browser: http://localhost:5006/load_dashboard
# 4. Mock-Daten werden angezeigt
```

**Probleme:**
- ❌ Mock-Daten, keine echten Ergebnisse
- ❌ Komplizierte Shell-Scripts
- ❌ Separate Python-Dateien nötig
- ❌ Schwer zu warten

### Neuer Workflow (Aktuell)

```bash
# 1. In runner.ipynb: Optimierung ausführen und speichern
# workflow = rh.run_workflow(config_paths)
# save_workflow_run(workflow, name="Baseline")

# 2. Dashboard standalone starten
python start_dashboard.py

# 3. Im Dashboard: Workflow aus Dropdown auswählen
# 4. Ergebnisse werden automatisch visualisiert
```

**Vorteile:**
- ✅ Echte Workflow-Ergebnisse
- ✅ Saubere Trennung: Simulation vs. Visualisierung
- ✅ Dashboard läuft unabhängig von Notebooks
- ✅ Einfacher zu verstehen
- ✅ Wartbar & erweiterbar
- ✅ Mehrere Workflows können verglichen werden
- ✅ Deployment-ready (kann als Web-Service laufen)

---

## ❓ Häufige Fragen

### Kann ich die alten Scripts noch verwenden?

**Technisch:** Ja, sie sind archiviert aber nicht gelöscht.
**Empfohlen:** Nein, nutze die neuen Notebooks.

### Was passiert mit alten saved_workflows/?

Die neuen Notebooks können alte Workflows laden (solange `workflow.pkl` existiert).

### Muss ich alte Workflows migrieren?

Nein, aber du kannst:
```bash
# Falls metadata.json fehlt:
python generate_missing_metadata.py

# Dann funktionieren alte Workflows in neuen Notebooks
```

### Wo finde ich die Shell-Scripts?

In `archive/old_dashboard_scripts/` - aber besser nicht verwenden!

---

## 📚 Weitere Ressourcen

- **Notebook-Übersicht:** Siehe `notebooks/` Verzeichnis
- **Helper-Funktionen:** Siehe `energis/io/notebook_helpers.py`
- **Tests:** Siehe `tests/test_notebook_helpers.py`
- **Git-Historie:** Commits zeigen Evolution des Systems

---

**Status:** Archiviert, nicht zur Verwendung empfohlen
**Letzte Archivierung:** 2025-12-02
**Ersetzt durch:**
- Dashboard: **DASHBOARD.md** + **start_dashboard.py** (Standalone Dashboard)
- Framework: **README.md** + **ARCHITECTURE_V2.md**
- Prozess-Docs: Archiviert für historische Referenz
