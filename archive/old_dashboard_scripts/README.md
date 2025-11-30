# 📦 Archived Dashboard Scripts

**Archiviert am:** 2024-11-30
**Grund:** Ersetzt durch notebook_helpers Integration

---

## ⚠️ Diese Dateien sind VERALTET

Die hier archivierten Scripts wurden durch die neue **notebook_helpers** Integration ersetzt und sollten **nicht mehr verwendet** werden.

---

## 📋 Archivierte Dateien

### Python Scripts

- **load_dashboard.py** (322 Zeilen)
  - *Zweck:* Multi-Workflow Dashboard mit Panel
  - *Ersetzt durch:* `notebooks/interactive_dashboard.ipynb`
  - *Warum veraltet:* Nutzte Mock-Workflow Deserialisierung, komplizierter als Notebook

- **demo_dashboard_mock.py**
  - *Zweck:* Demo-Dashboard mit Mock-Daten
  - *Ersetzt durch:* Echte Workflows in `saved_workflows/`
  - *Warum veraltet:* Mock-Daten nicht mehr nötig

- **create_mock_simulations.py**
  - *Zweck:* Erstellt 3 Mock-Simulationen für Dashboard-Demo
  - *Ersetzt durch:* Echte Workflow-Speicherung via `save_workflow_run()`
  - *Warum veraltet:* Mock-Daten nicht mehr nötig

### Shell Scripts

- **install_dashboard.sh** (88 Zeilen)
  - *Zweck:* Installation + Erstellung von Mock-Daten
  - *Ersetzt durch:* Standard pip install + echte Workflows
  - *Warum veraltet:* Mock-Setup nicht mehr nötig

- **start_dashboard.sh** (76 Zeilen)
  - *Zweck:* Startet `load_dashboard.py` als Panel Server
  - *Ersetzt durch:* `jupyter lab` oder `panel serve notebook.ipynb`
  - *Warum veraltet:* load_dashboard.py ist veraltet

- **stop_dashboard.sh** (40 Zeilen)
  - *Zweck:* Stoppt laufende Dashboard-Prozesse
  - *Ersetzt durch:* Standard Strg+C oder Process-Management
  - *Warum veraltet:* start_dashboard.sh ist veraltet

---

## ✅ Neue Lösung (seit 2024-11-30)

### Notebooks verwenden (Empfohlen)

**Für einzelne Workflows:**
```bash
jupyter lab notebooks/interactive_dashboard.ipynb
```

**Für Workflow-Vergleiche:**
```bash
jupyter lab notebooks/comparison_dashboard.ipynb
```

**Für Workflow-Verwaltung:**
```bash
jupyter lab notebooks/workflow_manager.ipynb
```

### Als Panel Server (Optional)

```bash
# Dashboard als Web-App
panel serve notebooks/interactive_dashboard.ipynb --show

# Oder auf spezifischem Port
panel serve notebooks/interactive_dashboard.ipynb --port 5006 --show
```

### Server-Setup

Für Server ohne GUI siehe:
```bash
docs/SERVER_SETUP.md
```

---

## 🔧 Migration

Falls du alte `saved_workflows/` hast, die mit den alten Scripts erstellt wurden:

### Option 1: Neu erstellen (Empfohlen)
```python
# In runner.ipynb oder scenario_studio.ipynb
workflow = rh.run_workflow(config_paths)
save_workflow_run(workflow, name="Mein Workflow")
```

### Option 2: Alte Workflows verwenden
Die neuen Notebooks können auch alte Workflows laden, solange `workflow.pkl` existiert.

**Wenn Fehler auftreten:**
```python
# Möglicherweise ist energis/mock_workflow.py nötig für alte Pickles
# Diese Datei wurde NICHT archiviert und ist noch verfügbar
```

---

## 📚 Weitere Informationen

- **Neue Integration:** Siehe `energis/io/notebook_helpers.py`
- **Cleanup-Report:** Siehe `CLEANUP_STATUS.md` (Root-Verzeichnis)
- **Server-Setup:** Siehe `docs/SERVER_SETUP.md`
- **Architektur:** Siehe `ARCHITECTURE_V2.md`

---

## ❓ Warum archiviert?

Diese Dateien wurden archiviert, nicht gelöscht, weil:

1. **Referenz:** Könnte hilfreich sein um alte Workflows zu verstehen
2. **Backup:** Falls Kompatibilitätsprobleme mit alten Daten auftreten
3. **Git-Historie:** Zeigt Evolution des Dashboard-Systems
4. **Reversibilität:** Kann bei Bedarf wiederhergestellt werden

**Aber:** Für neue Projekte sollten die neuen Notebooks verwendet werden!

---

**Status:** Archiviert, nicht zur Verwendung empfohlen
**Migration abgeschlossen:** 2024-11-30
**Ersetzt durch:** notebook_helpers Integration
