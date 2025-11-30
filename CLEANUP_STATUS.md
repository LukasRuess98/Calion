# 🧹 Cleanup & Migration Status

**Stand:** 2024-11-30
**Context:** Dashboard-Integration mit notebook_helpers abgeschlossen

---

## ✅ Status der Haupt-Notebooks

### **Aktuelle, gepflegte Notebooks:**

| Notebook | Status | notebook_helpers? | Zweck |
|----------|--------|-------------------|-------|
| **runner.ipynb** | ✅ Aktuell | ✅ Ja | Haupteinstieg für Optimierungen |
| **scenario_studio.ipynb** | ✅ Aktuell | ✅ Ja | Szenario-Analyse + wissenschaftliche Plots |
| **interactive_dashboard.ipynb** | ✅ Aktuell | ✅ Ja | Einzelne Workflows visualisieren |
| **comparison_dashboard.ipynb** | ✅ Neu | ✅ Ja | Mehrere Workflows vergleichen |
| **workflow_manager.ipynb** | ✅ Neu | ✅ Ja | Workflow-Verwaltung |

### **Andere Notebooks (behalten):**

| Notebook | Status | Zweck |
|----------|--------|-------|
| validation.ipynb | 🔧 Spezifisch | Modell-Validierung |
| rolling_horizon_validation.ipynb | 🔧 Spezifisch | RH-Tests |
| synthetic_example.ipynb | 🔧 Spezifisch | Synthetische Beispiele |
| test_runner.ipynb | 🔧 Test | Schnelle Tests |

---

## 📋 Veraltete/Zu migrierende Dateien

### **🗑️ VERALTET - Können gelöscht werden:**

Diese Dateien wurden durch die neue notebook_helpers Integration ersetzt:

```
❌ load_dashboard.py              → Ersetzt durch: interactive_dashboard.ipynb
❌ demo_dashboard_mock.py          → Ersetzt durch: echte Workflows
❌ create_mock_simulations.py      → Nicht mehr nötig (echte Workflows)
❌ install_dashboard.sh            → Veraltet (alte Mock-Installation)
❌ start_dashboard.sh              → Veraltet (nutzt load_dashboard.py)
❌ stop_dashboard.sh               → Veraltet (für load_dashboard.py)
```

**Begründung:**
- Alte Scripts nutzten Mock-Daten
- Neue Integration nutzt echte gespeicherte Workflows
- Notebooks sind jetzt der empfohlene Weg

### **📝 VERALTET - Dokumentation aktualisieren:**

Diese Markdown-Dateien beschreiben den alten Workflow:

```
⚠️  DASHBOARD_QUICKSTART.md        → Veraltete Anleitung (Shell-Scripts)
⚠️  DASHBOARD_INSTALL.md           → Veraltete Installation
⚠️  REAL_DATA_GUIDE.md             → Veraltete Anleitung (Mock→Real Migration)
```

**Empfehlung:**
- Löschen oder
- In `docs/archive/` verschieben oder
- Mit Warnung versehen: "⚠️ VERALTET - Siehe docs/SERVER_SETUP.md"

### **✅ BEHALTEN - Noch relevant:**

Migration Tools (können hilfreich sein):

```
✅ convert_old_exports.py          → Tool für alte Exports
✅ generate_missing_metadata.py    → Tool für Metadata-Migration
✅ energis/mock_workflow.py        → Für Deserialisierung alter Pickles
```

**Begründung:**
- Könnten für alte gespeicherte Workflows nötig sein
- Für Migrations-Zwecke behalten

---

## 📚 Dokumentations-Struktur

### **Aktuelle Dokumentation:**

```
docs/
├── SERVER_SETUP.md              ✅ NEU - Vollständige Server-Anleitung
├── methodology.md               ✅ Behalten
├── architecture/                ✅ Behalten
└── archive/                     📦 Für veraltete Docs
    ├── DASHBOARD_QUICKSTART.md  (verschoben)
    ├── DASHBOARD_INSTALL.md     (verschoben)
    └── REAL_DATA_GUIDE.md       (verschoben)
```

### **Root-Level Dokumentation (OK):**

```
✅ README.md                      → Haupt-Readme
✅ ARCHITECTURE_V2.md             → Architektur-Übersicht
✅ MIGRATION_GUIDE_V2.md          → V2 Migration
✅ ROLLING_HORIZON_EXPLANATION.md → RH Methodologie
```

---

## 🎯 Empfohlene Actions

### **Option 1: Archivieren (Empfohlen)**

Veraltete Dateien in Archive verschieben:

```bash
# Archive-Verzeichnis erstellen
mkdir -p archive/old_dashboard_scripts

# Veraltete Scripts verschieben
mv load_dashboard.py archive/old_dashboard_scripts/
mv demo_dashboard_mock.py archive/old_dashboard_scripts/
mv create_mock_simulations.py archive/old_dashboard_scripts/
mv install_dashboard.sh archive/old_dashboard_scripts/
mv start_dashboard.sh archive/old_dashboard_scripts/
mv stop_dashboard.sh archive/old_dashboard_scripts/

# Veraltete Docs verschieben
mkdir -p docs/archive
mv DASHBOARD_QUICKSTART.md docs/archive/
mv DASHBOARD_INSTALL.md docs/archive/
mv REAL_DATA_GUIDE.md docs/archive/

# README in Archive erstellen
echo "# Archived Dashboard Scripts

These files are from the old dashboard implementation (pre notebook_helpers).

**They have been replaced by:**
- interactive_dashboard.ipynb
- comparison_dashboard.ipynb
- workflow_manager.ipynb

See docs/SERVER_SETUP.md for current setup instructions.
" > archive/old_dashboard_scripts/README.md
```

### **Option 2: Direkt löschen (Aggressiv)**

Wenn Git-Historie ausreicht:

```bash
git rm load_dashboard.py demo_dashboard_mock.py create_mock_simulations.py
git rm install_dashboard.sh start_dashboard.sh stop_dashboard.sh
git rm DASHBOARD_QUICKSTART.md DASHBOARD_INSTALL.md REAL_DATA_GUIDE.md
git commit -m "Remove obsolete dashboard scripts (replaced by notebook_helpers)"
```

### **Option 3: Behalten mit Warnung (Konservativ)**

Warnung zu veralteten Dateien hinzufügen:

```bash
# In jede veraltete Datei am Anfang:
echo "⚠️ WARNING: This file is obsolete. See docs/SERVER_SETUP.md" | cat - old_file.py > temp && mv temp old_file.py
```

---

## 🔍 Migration Tools - Entscheidung

### **energis/mock_workflow.py**

**Status:** ⚠️ Unklar
**Verwendung:**
- Wird in load_dashboard.py importiert (veraltet)
- Könnte für Deserialisierung alter Pickles nötig sein

**Empfehlung:**
```python
# Test ob alte Workflows es brauchen:
cd saved_workflows/
for dir in */; do
    python -c "import pickle; pickle.load(open('$dir/workflow.pkl', 'rb'))"
done

# Falls Fehler → behalten
# Falls OK → kann gelöscht werden
```

### **convert_old_exports.py / generate_missing_metadata.py**

**Status:** ✅ Behalten (vorerst)
**Begründung:** Nützlich für Migration alter Daten

---

## ✅ Zusammenfassung

**Was ist sauber:**
- ✅ Alle 5 Haupt-Notebooks nutzen notebook_helpers
- ✅ Konsistente Workflow-Speicherung
- ✅ Neue SERVER_SETUP.md Dokumentation

**Was sollte aufgeräumt werden:**
- ⚠️ 6 veraltete Python-Scripts (Dashboard-bezogen)
- ⚠️ 3 veraltete Shell-Scripts
- ⚠️ 3 veraltete Markdown-Docs

**Empfehlung:**
1. Veraltete Dateien nach `archive/` verschieben
2. README in Archive mit Migration-Hinweisen
3. Migration Tools vorerst behalten
4. `energis/mock_workflow.py` nur löschen wenn definitiv nicht gebraucht

---

**Next Steps:** User entscheiden lassen welche Option (1, 2, oder 3).
