# 📚 Archived Documentation

**Archiviert am:** 2024-11-30
**Grund:** Beschreiben veraltete Workflows (Mock-Daten, alte Shell-Scripts)

---

## ⚠️ Diese Dokumentation ist VERALTET

Die hier archivierten Dokumente beschreiben den **alten Dashboard-Workflow** mit Mock-Daten und Shell-Scripts. Diese Methode wurde durch die **notebook_helpers Integration** ersetzt.

---

## 📋 Archivierte Dokumente

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

### Für Dashboard-Setup:

📖 **docs/SERVER_SETUP.md** (NEU!)
- Vollständige Server-Anleitung
- 3 Deployment-Optionen (JupyterLab, Headless, Panel Server)
- Headless/Server-Betrieb
- Troubleshooting
- Best Practices

### Für Framework-Nutzung:

📖 **README.md** - Haupt-Dokumentation
📖 **ARCHITECTURE_V2.md** - Architektur-Übersicht
📖 **ROLLING_HORIZON_EXPLANATION.md** - RH Methodologie

### Für Cleanup/Migration:

📖 **CLEANUP_STATUS.md** - Cleanup-Report (was ist veraltet?)

---

## 🚀 Quick Start (Neu)

### Dashboard lokal starten:

```bash
# Option 1: JupyterLab
jupyter lab notebooks/interactive_dashboard.ipynb

# Option 2: Panel Server
panel serve notebooks/interactive_dashboard.ipynb --show
```

### Workflow erstellen und speichern:

```python
# In runner.ipynb oder scenario_studio.ipynb
from energis.run.rolling_horizon import run_workflow
from energis.io.notebook_helpers import save_workflow_run

# Optimierung ausführen
workflow = run_workflow(config_paths)

# Automatisch speichern mit Metadaten
workflow_dir = save_workflow_run(
    workflow,
    name="Mein Test",
    description="Baseline mit optimierten Parametern"
)
```

### Dashboard anzeigen:

```python
# Direkt im Notebook
from energis.io.notebook_helpers import create_and_display_dashboard

dashboard = create_and_display_dashboard(workflow, title="Mein Dashboard")
dashboard  # Zeigt Dashboard an
```

---

## 🔄 Migration von alter zu neuer Dokumentation

| Alt (Archiviert) | Neu (Aktuell) | Abschnitt |
|------------------|---------------|-----------|
| DASHBOARD_QUICKSTART.md | docs/SERVER_SETUP.md | Quick Start |
| DASHBOARD_INSTALL.md | docs/SERVER_SETUP.md | Installation & Setup |
| REAL_DATA_GUIDE.md | - | Nicht mehr nötig |
| install_dashboard.sh | `pip install panel holoviews bokeh plotly` | Installation |
| start_dashboard.sh | `jupyter lab` oder `panel serve` | Dashboard starten |
| create_mock_simulations.py | `save_workflow_run()` | Workflows speichern |

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

```python
# 1. In runner.ipynb: Optimierung ausführen
workflow = rh.run_workflow(config_paths)

# 2. Automatisch speichern
save_workflow_run(workflow, name="Baseline")

# 3. Dashboard im Notebook anzeigen
dashboard = create_and_display_dashboard(workflow)
dashboard
```

**Vorteile:**
- ✅ Echte Workflow-Ergebnisse
- ✅ Alles in Notebooks
- ✅ Einfacher zu verstehen
- ✅ Wartbar & erweiterbar
- ✅ Konsistent mit workflow_manager.ipynb, comparison_dashboard.ipynb

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
**Migration abgeschlossen:** 2024-11-30
**Ersetzt durch:** notebook_helpers Integration + docs/SERVER_SETUP.md
